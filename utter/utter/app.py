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
from utter.audio import Recorder
from utter.cleanup import clean
from utter.config import GlossaryEntry, Settings, app_dir, load_settings, models_dir, save_settings
from utter.context import WindowInfo, categorize, foreground_window
from utter.history import Dictation, History, load_stats, save_stats
from utter.hotkey import HotkeyListener
from utter.netguard import NetGuard
from utter.paste import SystemClipboard, SystemKeys, deliver
from utter.transcriber import SAMPLE_RATE, ModelMissingError, Transcriber
from utter.ui import Dashboard, Pill

log = logging.getLogger(__name__)

_ERROR_ALREADY_EXISTS = 183
_mutex: Any = None


class Job(BaseModel, arbitrary_types_allowed=True):
    audio: np.ndarray
    window: WindowInfo
    released_at: float


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
        self.jobs: queue.Queue[Job | Literal["undo"] | None] = queue.Queue()
        self.recorder = Recorder()
        self.history = History()
        self.stats_path = app_dir() / "stats.json"
        self.stats = load_stats(self.stats_path)
        self.clipboard = SystemClipboard()
        self.keys = SystemKeys()
        self._settings_lock = threading.Lock()
        self._start_window: WindowInfo | None = None
        self.hotkeys = HotkeyListener(
            settings.hotkey, self.events,
            {"undo": settings.undo_hotkey, "dashboard": settings.dashboard_hotkey},
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
        self.root.after(30, self._poll)

    def _handle(self, kind: str, payload: Any) -> None:
        if kind == "start":
            self._start_window = foreground_window()
            try:
                self.recorder.start()
            except Exception as exc:  # PortAudio raises several error types for device issues
                log.exception("microphone failed to start")
                self.pill.set("error", f"Microphone error: {exc}", revert_ms=4000)
                return
            self.pill.set("listening", "● Listening…")
        elif kind == "cancel":
            self.recorder.stop()
            self.pill.set("ready", self.pill.ready_text)
        elif kind == "stop":
            audio = self.recorder.stop()
            window = self._start_window
            if window is None or audio.size < self.settings.min_recording_s * SAMPLE_RATE:
                self.pill.set("warn", "Too short — hold the keys while you speak", revert_ms=2000)
                return
            self.jobs.put(Job(audio=audio, window=window, released_at=float(payload)))
            self.pill.set("transcribing", "Transcribing on-device…")
        elif kind == "outcome":
            outcome: Outcome = payload
            self.pill.set(outcome.state, outcome.text, revert_ms=2500)
            self.dashboard.refresh_history()
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
            try:
                outcome = self._undo() if job == "undo" else self._process(job)
            except Exception:  # keep the worker alive; the user sees the error and the log has it
                log.exception("dictation failed")
                outcome = Outcome(state="error", text="Something went wrong — see utter.log")
            self.events.put(("outcome", outcome))

    def _process(self, job: Job) -> Outcome:
        with self._settings_lock:
            s = self.settings
        tr = self.transcriber.transcribe(job.audio, [g.written for g in s.glossary],
                                         s.no_speech_threshold, s.logprob_threshold)
        if not tr.confident:
            return Outcome(state="warn", text="Didn't catch that — nothing inserted")
        mode = categorize(job.window, s.mode_rules)
        cleaned = clean(tr.text, mode, s.glossary, s.snippets)
        if not cleaned.clean:
            return Outcome(state="warn", text="Nothing left to insert")
        self.hotkeys.wait_for_release()
        result = deliver(cleaned.clean, job.window, foreground_window(), s.blocked_exes,
                         self.clipboard, self.keys)
        latency = time.perf_counter() - job.released_at
        self.history.add(Dictation(
            at=datetime.now(), app=job.window.exe, mode=mode, raw=tr.text, clean=cleaned.clean,
            rules=cleaned.applied_rules, latency_s=latency, action=result.action,
        ))
        log.info("delivered: %s (%s) mode=%s latency=%.2fs rules=%s", result.action,
                 result.reason, mode.value, latency, cleaned.applied_rules)
        if result.action in ("pasted", "typed", "copied"):
            self.stats.record(len(cleaned.clean.split()), latency)
            save_stats(self.stats, self.stats_path)
        labels = {"pasted": "✓ Inserted", "typed": "✓ Typed", "copied": "Copied — window changed",
                  "blocked": "Blocked app — nothing inserted", "skipped": "Nothing to insert"}
        state: Literal["done", "warn"] = "done" if result.action in ("pasted", "typed") else "warn"
        return Outcome(state=state, text=f"{labels[result.action]} · {mode.value} · "
                                         f"{latency:.1f}s")

    def _undo(self) -> Outcome:
        last = self.history.last()
        if last is None or last.action not in ("pasted", "typed"):
            return Outcome(state="warn", text="Nothing to undo")
        if last.raw.strip() == last.clean:
            return Outcome(state="warn", text="No AI edit to undo")
        import keyboard

        deadline = time.monotonic() + 2.0
        while any(keyboard.is_pressed(k) for k in ("alt", "ctrl", "z")):
            if time.monotonic() > deadline:
                return Outcome(state="warn", text="Release Ctrl+Alt+Z to undo")
            time.sleep(0.02)
        now = foreground_window()
        self.keys.send("ctrl+z")
        time.sleep(0.15)
        result = deliver(last.raw.strip(), now, now, self.settings.blocked_exes,
                         self.clipboard, self.keys)
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
