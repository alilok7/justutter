"""Wires hotkey -> recorder -> transcriber -> clean-up -> paste. Tk owns the main thread."""

from __future__ import annotations

import ctypes
import logging
import queue
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import messagebox
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel

from utter import APP_NAME
from utter.audio import Recorder, find_split
from utter.cleanup import clean, format_for_mode
from utter.config import (
    GlossaryEntry,
    Mode,
    Settings,
    app_dir,
    load_settings,
    models_dir,
    save_settings,
)
from utter.context import WindowInfo, categorize, foreground_window
from utter.history import Dictation, History, load_stats, save_stats
from utter.hotkey import HotkeyListener
from utter.netguard import NetGuard
from utter.paste import PendingRestore, SystemClipboard, SystemKeys, deliver, restore_clipboard
from utter.personal import (
    CorrectionProposal,
    PersonalMemory,
    add_style_example,
    hotwords,
    load_memory,
    propose_corrections,
    record_dictation,
    save_memory,
)
from utter.polish import Polisher, should_polish
from utter.transcriber import SAMPLE_RATE, ModelMissingError, Transcriber
from utter.ui import Dashboard, Pill

log = logging.getLogger(__name__)

_ERROR_ALREADY_EXISTS = 183
_mutex: Any = None


CHUNK_S = 20.0  # long recordings are transcribed in chunks of about this length while recording


class Session:
    """One recording. Chunk texts are filled in by the worker while the user keeps talking."""

    def __init__(self, window: WindowInfo) -> None:
        self.window = window
        self.consumed = 0  # 16 kHz samples already sent as chunks
        self.chunks = 0
        self.texts: dict[int, str] = {}
        self.cancelled = False


class ChunkJob(BaseModel, arbitrary_types_allowed=True):
    session: Session
    index: int
    audio: np.ndarray


class Job(BaseModel, arbitrary_types_allowed=True):
    audio: np.ndarray
    window: WindowInfo
    released_at: float
    session: Session | None = None


class Outcome(BaseModel):
    state: Literal["done", "warn", "error"]
    text: str


class UtterApp:
    def __init__(self, settings: Settings, warning: str | None, transcriber: Transcriber,
                 guard: NetGuard) -> None:
        self.settings = settings
        self.transcriber = transcriber
        self.model_name = transcriber.name
        self.guard = guard
        self.config_dir = str(app_dir())
        self.events: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.jobs: queue.Queue[Job | ChunkJob | Literal["undo", "learn"] | None] = queue.Queue()
        self.memory_path = app_dir() / "personal.json"
        self.memory = load_memory(self.memory_path)
        self._memory_lock = threading.Lock()
        self._session: Session | None = None
        self._chunk_check_at = 0.0
        self.polisher = Polisher(settings.polish_model, settings.polish_timeout_s)
        self.polisher_ready = False
        self._polish_warned = False
        self.recorder = Recorder()
        self.history = History()
        self.stats_path = app_dir() / "stats.json"
        self.stats = load_stats(self.stats_path)
        self.clipboard = SystemClipboard()
        self.keys = SystemKeys()
        self._settings_lock = threading.Lock()
        self._start_window: WindowInfo | None = None
        self._recording_since: float | None = None
        self._pending_restore: PendingRestore | None = None
        self._last_timer_text = ""
        self._watchdog_at = 0.0
        self.hotkeys = HotkeyListener(
            settings.hotkey, self.events,
            {"undo": settings.undo_hotkey, "dashboard": settings.dashboard_hotkey,
             "learn": settings.correction_hotkey},
        )
        self.root = tk.Tk()
        self.root.withdraw()
        chord = "+".join(k.title() for k in settings.hotkey).replace("Windows", "Win")
        self.pill = Pill(self.root, f"{APP_NAME} · hold {chord} to dictate", self.toggle_dashboard)
        self.dashboard = Dashboard(self.root, self)
        if warning:
            self.pill.set("warn", warning, revert_ms=6000)

    # --- main-thread loop --------------------------------------------------------------------
    def run(self) -> None:
        worker = threading.Thread(target=self._worker, name="utter-worker", daemon=True)
        worker.start()
        threading.Thread(target=self._check_polisher, name="utter-polish-check",
                         daemon=True).start()
        self.hotkeys.start()
        self.root.after(30, self._poll)
        self.root.after(1000, self._tick)
        log.info("%s ready", APP_NAME)
        try:
            self.root.mainloop()
        finally:
            self._shutdown()

    def _tick(self) -> None:
        self.dashboard.tick()
        self.root.after(1000, self._tick)

    def _poll(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                self._handle(kind, payload)
        except queue.Empty:
            pass
        self._supervise_recording()
        self.root.after(30, self._poll)

    def _supervise_recording(self) -> None:
        """Watchdog for lost key-ups, the recording time limit and the hands-free timer."""
        if self._recording_since is None:
            return
        now = time.perf_counter()
        if now - self._watchdog_at >= 0.1:
            self._watchdog_at = now
            if self.hotkeys.check_stuck():
                self._handle("stop", (now, None))
                return
        elapsed = now - self._recording_since
        if elapsed >= self.settings.max_recording_s:
            log.warning("recording hit the %.0fs limit; stopping", self.settings.max_recording_s)
            self.hotkeys.force_stop()
            self._handle("stop", (now, None))
            return
        if now - self._chunk_check_at >= 1.0:
            self._chunk_check_at = now
            self._queue_ready_chunk()
        if self.hotkeys.mode == "handsfree":
            text = (f"● Hands-free {int(elapsed) // 60}:{int(elapsed) % 60:02d}"
                    "  ·  Ctrl+Win to finish  ·  Esc cancels")
            if text != self._last_timer_text:
                self._last_timer_text = text
                self.pill.set("listening", text)

    def _queue_ready_chunk(self) -> None:
        """Send the next ~20 s of a long recording to the worker, cut at a pause between words."""
        session = self._session
        if session is None:
            return
        audio = self.recorder.peek()
        pending = audio[session.consumed:]
        if pending.size < CHUNK_S * SAMPLE_RATE:
            return
        cut = session.consumed + find_split(pending)
        self.jobs.put(ChunkJob(session=session, index=session.chunks,
                               audio=audio[session.consumed:cut]))
        log.info("queued chunk %d (%.1fs) for background transcription", session.chunks,
                 (cut - session.consumed) / SAMPLE_RATE)
        session.chunks += 1
        session.consumed = cut

    def _handle(self, kind: str, payload: Any) -> None:
        if kind == "start":
            window = self._start_window = foreground_window()
            try:
                self.recorder.start()
            except Exception as exc:  # PortAudio raises several error types for device issues
                log.exception("microphone failed to start")
                self.hotkeys.force_stop()
                self.pill.set("error", f"Microphone error: {exc}", revert_ms=4000)
                return
            self._recording_since = time.perf_counter()
            self._session = Session(window)
            self.pill.set("listening", "● Listening…  (Space: hands-free · Esc: cancel)")
        elif kind == "handsfree":
            self._last_timer_text = ""
            log.info("switched to hands-free dictation")
        elif kind == "cancel":
            self.recorder.stop()
            self._recording_since = None
            if self._session is not None:
                self._session.cancelled = True
                self._session = None
            reason = payload[1] if payload else None
            log.info("dictation cancelled (%s)", reason)
            self.pill.set("warn", f"Cancelled ({reason}) — nothing inserted", revert_ms=3000)
        elif kind == "stop":
            audio = self.recorder.stop()
            self._recording_since = None
            session, self._session = self._session, None
            target = self._start_window
            if target is None or audio.size < self.settings.min_recording_s * SAMPLE_RATE:
                self.pill.set("warn", "Too short — hold the keys while you speak", revert_ms=2000)
                return
            consumed = session.consumed if session else 0
            self.jobs.put(Job(audio=audio[consumed:], window=target,
                              released_at=float(payload[0]), session=session))
            seconds = audio.size / SAMPLE_RATE
            self.pill.set("transcribing", f"Transcribing {seconds:.0f}s on-device…")
        elif kind == "outcome":
            outcome: Outcome = payload
            self.pill.set(outcome.state, outcome.text, revert_ms=2500)
            self.dashboard.refresh_history()
        elif kind == "notice":
            if self._recording_since is None:
                self.pill.set("warn", str(payload), revert_ms=4000)
            log.info("notice: %s", payload)
        elif kind == "learn":
            self.jobs.put("learn")
        elif kind == "confirm_learn":
            self._confirm_learn(payload)
        elif kind == "undo":
            self.jobs.put("undo")
        elif kind == "dashboard":
            self.toggle_dashboard()

    def toggle_dashboard(self) -> None:
        self.dashboard.toggle()

    def quit(self) -> None:
        self.root.quit()

    # --- worker thread -----------------------------------------------------------------------
    def _worker(self) -> None:
        while (job := self.jobs.get()) is not None:
            if isinstance(job, ChunkJob):
                self._transcribe_chunk(job)
                continue
            try:
                if job == "undo":
                    outcome = self._undo()
                elif job == "learn":
                    outcome = self._learn_from_selection()
                else:
                    outcome = self._process(job)
            except Exception:  # keep the worker alive; the user sees the error and the log has it
                log.exception("dictation failed")
                outcome = Outcome(state="error", text="Something went wrong — see utter.log")
            self.events.put(("outcome", outcome))
            pending, self._pending_restore = self._pending_restore, None
            if pending is not None:
                try:
                    restore_clipboard(self.clipboard, pending)
                except Exception:  # clipboard can be locked by another app; never crash the worker
                    log.exception("clipboard restore failed")

    def _transcribe_chunk(self, job: ChunkJob) -> None:
        if job.session.cancelled:
            return
        with self._settings_lock:
            s = self.settings
        try:
            tr = self.transcriber.transcribe(job.audio, self._hotwords(s),
                                             s.no_speech_threshold, s.logprob_threshold)
        except Exception:  # a failed chunk loses only its own text; the rest still arrives
            log.exception("chunk %d failed", job.index)
            return
        job.session.texts[job.index] = tr.text if tr.confident else ""

    def _process(self, job: Job) -> Outcome:
        with self._settings_lock:
            s = self.settings
        hotwords = self._hotwords(s)
        texts = [job.session.texts.get(i, "") for i in range(job.session.chunks)] \
            if job.session else []
        if job.audio.size >= s.min_recording_s * SAMPLE_RATE:
            tr = self.transcriber.transcribe(job.audio, hotwords, s.no_speech_threshold,
                                             s.logprob_threshold)
            texts.append(tr.text if tr.confident else "")
        raw = " ".join(t for t in texts if t).strip()
        if not raw:
            return Outcome(state="warn", text="Didn't catch that — nothing inserted")
        mode = categorize(job.window, s.mode_rules)
        cleaned = clean(raw, mode, s.glossary, s.snippets)
        if not cleaned.clean:
            return Outcome(state="warn", text="Nothing left to insert")
        final, rules = self._maybe_polish(cleaned.clean, mode, s)
        rules = cleaned.applied_rules + rules
        self.hotkeys.wait_for_release()
        result, self._pending_restore = deliver(final, job.window, foreground_window(),
                                                s.blocked_exes, self.clipboard, self.keys)
        latency = time.perf_counter() - job.released_at
        self.history.add(Dictation(
            at=datetime.now(), app=job.window.exe, mode=mode, raw=raw, clean=final,
            rules=rules, latency_s=latency, action=result.action,
        ))
        log.info("delivered: %s (%s) mode=%s latency=%.2fs rules=%s", result.action,
                 result.reason, mode.value, latency, rules)
        if result.action in ("pasted", "typed", "copied"):
            self.stats.record(len(final.split()), latency)
            if s.learn_enabled:
                with self._memory_lock:
                    record_dictation(self.memory, final)
                    save_memory(self.memory, self.memory_path)
            save_stats(self.stats, self.stats_path)
        labels = {"pasted": "✓ Inserted", "typed": "✓ Typed", "copied": "Copied — window changed",
                  "blocked": "Blocked app — nothing inserted", "skipped": "Nothing to insert"}
        state: Literal["done", "warn"] = "done" if result.action in ("pasted", "typed") else "warn"
        return Outcome(state=state, text=f"{labels[result.action]} · {mode.value} · "
                                         f"{latency:.1f}s")

    def _maybe_polish(self, text: str, mode: Mode, s: Settings) -> tuple[str, list[str]]:
        if not (s.polish_enabled and self.polisher_ready and
                should_polish(text, mode, s.polish_min_words)):
            return text, []
        protected = self._hotwords(s) + [sn.text for sn in s.snippets]
        with self._memory_lock:
            examples = self.memory.style_examples[-3:] if s.learn_enabled else []
            self.polisher.extra_shots = [(e.before, e.after) for e in examples]
        result = self.polisher.polish(text, protected)
        if not result.used:
            if not self._polish_warned:
                self._polish_warned = True
                self.events.put(("notice", f"AI polish skipped: {result.reason[:60]}"))
            return text, [f"ai polish skipped: {result.reason}"]
        polished, mode_rules = format_for_mode(result.text, mode)
        return polished, [f"ai polish: {self.polisher.model} ({result.latency_s:.2f}s)",
                          *mode_rules]

    def _check_polisher(self) -> None:
        """Background: confirm Ollama + model are present and load the model into memory."""
        if not self.settings.polish_enabled:
            return
        problem = self.polisher.available()
        if problem:
            self.events.put(("notice", f"AI polish off: {problem}"))
            return
        self.polisher.warmup()
        self.polisher_ready = True
        log.info("ai polish ready (%s)", self.polisher.model)

    def set_polish(self, enabled: bool) -> None:
        with self._settings_lock:
            self.settings = self.settings.model_copy(update={"polish_enabled": enabled})
            save_settings(self.settings)
        if enabled and not self.polisher_ready:
            threading.Thread(target=self._check_polisher, daemon=True).start()

    # --- personal memory ---------------------------------------------------------------------
    def _hotwords(self, s: Settings) -> list[str]:
        glossary_terms = [g.written for g in s.glossary]
        if not s.learn_enabled:
            return glossary_terms
        with self._memory_lock:
            return hotwords(self.memory, glossary_terms)

    def _learn_from_selection(self) -> Outcome:
        """Ctrl+Alt+L: diff the user's corrected selection against the last dictation."""
        last = self.history.last()
        if last is None:
            return Outcome(state="warn", text="Dictate something first, then fix it and press "
                                              "Ctrl+Alt+L")
        if not self.settings.learn_enabled:
            return Outcome(state="warn", text="Learning is off (dashboard → Glossary)")
        if not self.hotkeys.wait_for_release(["ctrl", "alt", "l"]):
            return Outcome(state="warn", text="Release Ctrl+Alt+L to learn")
        if self.clipboard.holds_non_text():
            return Outcome(state="warn", text="Clipboard holds an image — copy text first")
        previous = self.clipboard.get_text()
        marker = f"utter-selection-marker-{time.monotonic()}"
        self.clipboard.set_text(marker)
        try:
            self.keys.send("ctrl+c")
            time.sleep(0.3)
            selection = self.clipboard.get_text()
        finally:
            self.clipboard.set_text(previous)
        if not selection.strip() or selection == marker:
            return Outcome(state="warn", text="Select your corrected text, then press Ctrl+Alt+L")
        proposal = propose_corrections(last.clean, selection.strip())
        if not proposal.pairs and proposal.style_example is None:
            return Outcome(state="warn", text="No differences from the last dictation")
        self.events.put(("confirm_learn", proposal))
        return Outcome(state="done", text="Review what to learn…")

    def _confirm_learn(self, proposal: CorrectionProposal) -> None:
        lines = [f"  '{h}'  →  '{w}'" for h, w in proposal.pairs]
        question = ("Learn these corrections?\n\n" + "\n".join(lines)) if lines else ""
        if proposal.style_example is not None:
            question += ("\n\n" if question else "") + \
                "Also remember your rewrite as a style example for AI polish?"
        if not messagebox.askyesno(APP_NAME, question):
            log.info("user declined to learn %d corrections", len(proposal.pairs))
            return
        existing = {g.heard.lower() for g in self.settings.glossary}
        for heard, written in proposal.pairs:
            if heard.lower() not in existing:
                self.add_glossary(heard, written)
        with self._memory_lock:
            for _heard, written in proposal.pairs:
                self.memory.vocab[written] = self.memory.vocab.get(written, 0) + 2
            if proposal.style_example is not None:
                add_style_example(self.memory, proposal.style_example)
            self.memory.corrections_learned += len(proposal.pairs)
            save_memory(self.memory, self.memory_path)
        self.pill.set("done", f"✓ Learned {len(proposal.pairs)} correction(s)", revert_ms=2500)
        self.dashboard.refresh_glossary()

    def set_learning(self, enabled: bool) -> None:
        with self._settings_lock:
            self.settings = self.settings.model_copy(update={"learn_enabled": enabled})
            save_settings(self.settings)

    def forget_memory(self) -> None:
        with self._memory_lock:
            self.memory = PersonalMemory()
            save_memory(self.memory, self.memory_path)
        log.info("personal memory cleared by user")

    def _undo(self) -> Outcome:
        last = self.history.last()
        if last is None or last.action not in ("pasted", "typed"):
            return Outcome(state="warn", text="Nothing to undo")
        if last.raw.strip() == last.clean:
            return Outcome(state="warn", text="No AI edit to undo")
        if not self.hotkeys.wait_for_release(["alt", "ctrl", "z"]):
            return Outcome(state="warn", text="Release Ctrl+Alt+Z to undo")
        now = foreground_window()
        self.keys.send("ctrl+z")
        time.sleep(0.15)
        result, self._pending_restore = deliver(last.raw.strip(), now, now,
                                                self.settings.blocked_exes, self.clipboard,
                                                self.keys)
        last.action = "undone"
        log.info("undo AI edit: %s", result.action)
        return Outcome(state="done", text="↶ Raw transcript restored")

    # --- glossary edits (main thread) --------------------------------------------------------
    def add_glossary(self, heard: str, written: str) -> None:
        with self._settings_lock:
            entries = [*self.settings.glossary, GlossaryEntry(heard=heard, written=written)]
            self.settings = self.settings.model_copy(update={"glossary": entries})
            save_settings(self.settings)
        log.info("glossary: added '%s' -> '%s'", heard, written)

    def remove_glossary(self, index: int) -> None:
        with self._settings_lock:
            entries = [g for i, g in enumerate(self.settings.glossary) if i != index]
            self.settings = self.settings.model_copy(update={"glossary": entries})
            save_settings(self.settings)

    def _shutdown(self) -> None:
        log.info("shutting down")
        self.hotkeys.stop()
        self.jobs.put(None)
        self.recorder.stop()
        save_stats(self.stats, self.stats_path)
        self.guard.uninstall()


def _single_instance() -> bool:
    global _mutex
    kernel32 = ctypes.windll.kernel32
    _mutex = kernel32.CreateMutexW(None, False, "Local\\UtterDictationApp")
    return int(kernel32.GetLastError()) != _ERROR_ALREADY_EXISTS


def _error_box(text: str) -> None:
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(APP_NAME, text)
    root.destroy()


def main() -> int:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except OSError:
        log.info("DPI awareness not available")
    if not _single_instance():
        _error_box(f"{APP_NAME} is already running.")
        return 1
    settings, warning = load_settings()
    guard = NetGuard()
    guard.install()
    try:
        transcriber = Transcriber(settings.model, models_dir())
    except ModelMissingError as exc:
        _error_box(str(exc))
        return 1
    transcriber.warmup()
    UtterApp(settings, warning, transcriber, guard).run()
    return 0
