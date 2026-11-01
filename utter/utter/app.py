"""Wires hotkey -> recorder -> transcriber -> clean-up -> paste. Qt owns the main thread."""

from __future__ import annotations

import ctypes
import logging
import queue
import threading
import time
from collections.abc import Sequence
from datetime import datetime
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel
from PySide6.QtCore import QTimer

from utter import APP_NAME
from utter.audio import Recorder, find_split
from utter.cleanup import clean, format_for_mode
from utter.clipboard import ClipboardBusyError
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
from utter.power import keep_full_speed
from utter.transcriber import SAMPLE_RATE, ModelMissingError, Transcriber
from utter.ui import Dashboard, FloatingBar, Tray, confirm_learn, error_box, make_app

log = logging.getLogger(__name__)

_ERROR_ALREADY_EXISTS = 183
_mutex: Any = None


CHUNK_S = 12.0  # long recordings are processed in pieces of about this length while recording


class Piece(BaseModel):
    """One processed stretch of a recording: what Whisper heard and the finished text."""

    raw: str
    text: str
    rules: list[str]


def assemble_pieces(pieces: Sequence[Piece | None], mode: Mode,
                    keep_endings: Sequence[str]) -> tuple[str, str, list[str]]:
    """Join processed pieces in order and apply the mode's end-of-text rules once.

    Returns (raw transcript, final text, applied rules). A missing piece (failed chunk) is
    skipped rather than blocking the rest.
    """
    done = [p for p in pieces if p is not None]
    raw = " ".join(p.raw for p in done if p.raw).strip()
    joined = " ".join(p.text for p in done if p.text).strip()
    if not joined:
        return raw, "", [r for p in done for r in p.rules]
    final, end_rules = format_for_mode(joined, mode, keep_endings)
    return raw, final, [r for p in done for r in p.rules] + end_rules


class Session:
    """One recording. Pieces are transcribed, cleaned and polished while the user keeps talking."""

    def __init__(self, window: WindowInfo, mode: Mode) -> None:
        self.window = window
        self.mode = mode
        self.consumed = 0  # 16 kHz samples already sent as chunks
        self.chunks = 0
        self.pieces: dict[int, Piece] = {}
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
    state: Literal["done", "warn", "error", "cancelled"]
    text: str
    detail: str = ""


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
        self._watchdog_at = 0.0
        self.hotkeys = HotkeyListener(
            settings.hotkey, self.events,
            {"undo": settings.undo_hotkey, "dashboard": settings.dashboard_hotkey,
             "learn": settings.correction_hotkey},
        )
        self.paused = False
        self.qt = make_app()
        self.pill = FloatingBar(lambda: self.recorder.level, settings.bar_scale)
        self.dashboard = Dashboard(self)
        self.tray = Tray(self)
        self._timers: list[QTimer] = []
        if warning:
            self.pill.set("warn", "Config reset", warning, revert_ms=6000)

    # --- main-thread loop --------------------------------------------------------------------
    def run(self) -> None:
        worker = threading.Thread(target=self._worker, name="utter-worker", daemon=True)
        worker.start()
        threading.Thread(target=self._check_polisher, name="utter-polish-check",
                         daemon=True).start()
        self.hotkeys.start()
        for interval, fn in ((30, self._poll), (1000, self._tick)):
            timer = QTimer()
            timer.timeout.connect(fn)
            timer.start(interval)
            self._timers.append(timer)
        self.tray.show()
        log.info("%s ready", APP_NAME)
        try:
            self.qt.exec()
        finally:
            self._shutdown()

    def _tick(self) -> None:
        self.dashboard.tick()

    def _poll(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                self._handle(kind, payload)
        except queue.Empty:
            pass
        self._supervise_recording()

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
        if self.hotkeys.mode == "handsfree" and self.pill.state != "handsfree":
            self.pill.set("handsfree", "0:00", "Ctrl+Win to finish · Esc cancels")

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
            if self.paused:
                self.hotkeys.force_stop()
                self.pill.set("paused", "Paused", "resume from the tray icon", revert_ms=1800)
                return
            window = self._start_window = foreground_window()
            try:
                self.recorder.start()
            except Exception as exc:  # PortAudio raises several error types for device issues
                log.exception("microphone failed to start")
                self.hotkeys.force_stop()
                self.pill.set("error", "Microphone error", str(exc)[:60], revert_ms=4000)
                return
            self._recording_since = time.perf_counter()
            self._session = Session(window, categorize(window, self.settings.mode_rules))
            self.pill.set("listening", "Listening", "Space hands-free · Esc cancel")
        elif kind == "handsfree":
            log.info("switched to hands-free dictation")
        elif kind == "cancel":
            self.recorder.stop()
            self._recording_since = None
            if self._session is not None:
                self._session.cancelled = True
                self._session = None
            reason = payload[1] if payload else None
            log.info("dictation cancelled (%s)", reason)
            self.pill.set("cancelled", "Cancelled", "nothing inserted", revert_ms=2500)
        elif kind == "stop":
            audio = self.recorder.stop()
            self._recording_since = None
            session, self._session = self._session, None
            target = self._start_window
            if target is None or audio.size < self.settings.min_recording_s * SAMPLE_RATE:
                self.pill.set("warn", "Too short", "hold the keys while you speak", revert_ms=2000)
                return
            consumed = session.consumed if session else 0
            self.jobs.put(Job(audio=audio[consumed:], window=target,
                              released_at=float(payload[0]), session=session))
            seconds = audio.size / SAMPLE_RATE
            self.pill.set("working", "Transcribing", f"{seconds:.0f}s · on-device")
        elif kind == "outcome":
            outcome: Outcome = payload
            self.pill.set(outcome.state, outcome.text, outcome.detail, revert_ms=2500)
            self.dashboard.refresh()
        elif kind == "phase":
            self.pill.set("working", *payload)
        elif kind == "notice":
            if self._recording_since is None:
                self.pill.set("warn", "Heads up", str(payload), revert_ms=4000)
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
        self.qt.quit()

    def set_paused(self, paused: bool) -> None:
        self.paused = paused
        log.info("dictation %s", "paused" if paused else "resumed")

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
                outcome = Outcome(state="error", text="Something went wrong",
                                  detail="see utter.log")
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
            job.session.pieces[job.index] = self._make_piece(job.audio, job.session.mode, s,
                                                             announce=False)
        except Exception:  # a failed piece loses only its own text; the rest still arrives
            log.exception("chunk %d failed", job.index)

    def _make_piece(self, audio: np.ndarray, mode: Mode, s: Settings, announce: bool) -> Piece:
        """Transcribe, clean and polish one stretch of audio (end-of-text rules come later)."""
        tr = self.transcriber.transcribe(audio, self._hotwords(s), s.no_speech_threshold,
                                         s.logprob_threshold)
        if not tr.confident:
            return Piece(raw="", text="", rules=[])
        cleaned = clean(tr.text, mode, s.glossary, s.snippets, apply_mode=False)
        if not cleaned.clean:
            return Piece(raw=tr.text, text="", rules=cleaned.applied_rules)
        text, polish_rules = self._maybe_polish(cleaned.clean, mode, s, announce)
        return Piece(raw=tr.text, text=text, rules=cleaned.applied_rules + polish_rules)

    def _process(self, job: Job) -> Outcome:
        with self._settings_lock:
            s = self.settings
        mode = job.session.mode if job.session else categorize(job.window, s.mode_rules)
        pieces = [job.session.pieces.get(i) for i in range(job.session.chunks)] \
            if job.session else []
        if job.audio.size >= s.min_recording_s * SAMPLE_RATE:
            pieces.append(self._make_piece(job.audio, mode, s, announce=True))
        raw, final, rules = assemble_pieces(pieces, mode, [sn.text for sn in s.snippets])
        if not raw:
            return Outcome(state="warn", text="Didn't catch that", detail="nothing inserted")
        if not final:
            return Outcome(state="warn", text="Nothing left to insert")
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
        labels = {"pasted": ("Inserted", f"{mode.value} · {latency:.1f}s"),
                  "typed": ("Typed", f"{mode.value} · {latency:.1f}s"),
                  "copied": ("Copied", "window changed · Ctrl+V to paste"),
                  "blocked": ("Blocked app", "nothing inserted"),
                  "skipped": ("Nothing to insert", "")}
        text, detail = labels[result.action]
        state: Literal["done", "warn"] = "done" if result.action in ("pasted", "typed") else "warn"
        return Outcome(state=state, text=text, detail=detail)

    def _maybe_polish(self, text: str, mode: Mode, s: Settings,
                      announce: bool = True) -> tuple[str, list[str]]:
        if not (s.polish_enabled and self.polisher_ready and
                should_polish(text, mode, s.polish_min_words)):
            return text, []
        protected = self._hotwords(s) + [sn.text for sn in s.snippets]
        with self._memory_lock:
            examples = self.memory.style_examples[-3:] if s.learn_enabled else []
            self.polisher.extra_shots = [(e.before, e.after) for e in examples]
        if announce:
            self.events.put(("phase", ("Polishing", "local AI")))
        result = self.polisher.polish(text, protected)
        if not result.used:
            if not self._polish_warned:
                self._polish_warned = True
                self.events.put(("notice", f"AI polish skipped: {result.reason[:60]}"))
            return text, [f"ai polish skipped: {result.reason}"]
        return result.text, [f"ai polish: {self.polisher.model} ({result.latency_s:.2f}s)"]

    def _check_polisher(self) -> None:
        """Background: confirm Ollama + model are present and load the model into memory."""
        if not self.settings.polish_enabled:
            return
        problem = self.polisher.available()
        if problem:
            self.events.put(("notice", f"AI polish off: {problem}"))
            return
        if not self.polisher.warmup():
            self.events.put(("notice", "AI polish off: model failed to load"))
            return
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
            return Outcome(state="warn", text="Nothing to learn yet",
                           detail="dictate, fix it, then press Ctrl+Alt+L")
        if not self.settings.learn_enabled:
            return Outcome(state="warn", text="Learning is off", detail="turn it on in Memory")
        if not self.hotkeys.wait_for_release(["ctrl", "alt", "l"]):
            return Outcome(state="warn", text="Release Ctrl+Alt+L", detail="then try again")
        try:
            saved = self.clipboard.snapshot()
        except (ClipboardBusyError, MemoryError, OSError) as exc:
            log.warning("clipboard snapshot failed: %s", exc)
            return Outcome(state="warn", text="Clipboard busy", detail="try again")
        marker = f"utter-selection-marker-{time.monotonic()}"
        self.clipboard.set_text(marker)
        try:
            self.keys.send("ctrl+c")
            time.sleep(0.3)
            selection = self.clipboard.get_text()
        finally:
            self.clipboard.restore(saved)
        if not selection.strip() or selection == marker:
            return Outcome(state="warn", text="Nothing selected",
                           detail="select your corrected text, then Ctrl+Alt+L")
        proposal = propose_corrections(last.clean, selection.strip())
        if not proposal.pairs and proposal.style_example is None:
            return Outcome(state="warn", text="No differences", detail="from the last dictation")
        self.events.put(("confirm_learn", proposal))
        return Outcome(state="done", text="Review what to learn")

    def _confirm_learn(self, proposal: CorrectionProposal) -> None:
        if not confirm_learn(proposal):
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
        self.pill.set("done", f"Learned {len(proposal.pairs)} correction(s)", revert_ms=2500)
        self.dashboard.refresh()

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
            return Outcome(state="warn", text="Release Ctrl+Alt+Z", detail="then try again")
        now = foreground_window()
        self.keys.send("ctrl+z")
        time.sleep(0.15)
        result, self._pending_restore = deliver(last.raw.strip(), now, now,
                                                self.settings.blocked_exes, self.clipboard,
                                                self.keys)
        last.action = "undone"
        log.info("undo AI edit: %s", result.action)
        return Outcome(state="done", text="Raw transcript restored", detail="AI edit undone")

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


def main() -> int:
    if not _single_instance():
        error_box(f"{APP_NAME} is already running.")
        return 1
    keep_full_speed()  # background apps are throttled on battery; dictation must stay fast
    settings, warning = load_settings()
    guard = NetGuard()
    guard.install()
    try:
        transcriber = Transcriber(settings.model, models_dir(),
                                  threads=settings.whisper_threads)
    except ModelMissingError as exc:
        error_box(str(exc))
        return 1
    transcriber.warmup()
    UtterApp(settings, warning, transcriber, guard).run()
    return 0
