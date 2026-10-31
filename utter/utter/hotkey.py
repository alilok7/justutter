"""Hold-to-talk chord detection (default Ctrl+Win) on top of the `keyboard` hook.

``ChordState`` is pure logic and unit-tested; ``HotkeyListener`` wires it to real key events.
"""

from __future__ import annotations

import ctypes
import logging
import queue
import time
from collections.abc import Sequence
from typing import Any, Literal

log = logging.getLogger(__name__)

ChordEvent = Literal["start", "stop", "cancel"]

_VK_MASK = 0xE8  # unassigned virtual key; tapping it stops Win's key-up from opening Start
_KEYEVENTF_KEYUP = 0x0002


def key_matches(configured: str, event_name: str) -> bool:
    """'ctrl' matches 'ctrl', 'left ctrl' and 'right ctrl'; 'right ctrl' matches only itself."""
    name = event_name.lower()
    return name == configured or (
        not configured.startswith(("left ", "right ")) and name.endswith(" " + configured)
    )


class ChordState:
    def __init__(self, keys: Sequence[str]) -> None:
        self.keys = list(keys)
        self.down: set[str] = set()
        self.others: set[str] = set()
        self.active = False
        self.spoiled = False

    def _chord_key(self, name: str) -> str | None:
        return next((k for k in self.keys if key_matches(k, name)), None)

    def on_event(self, name: str, is_down: bool) -> ChordEvent | None:
        key = self._chord_key(name)
        if key is None:
            if is_down:
                self.others.add(name)
                if self.active:
                    self.spoiled = True  # e.g. Ctrl+Win+Right: a Windows shortcut, not dictation
            else:
                self.others.discard(name)
            return None
        if is_down:
            self.down.add(key)
            if not self.active and len(self.down) == len(self.keys) and not self.others:
                self.active, self.spoiled = True, False
                return "start"
            return None
        self.down.discard(key)
        if self.active:
            self.active = False
            return "cancel" if self.spoiled else "stop"
        return None


def tap_mask_key() -> None:
    user32 = ctypes.windll.user32
    user32.keybd_event(_VK_MASK, 0, 0, 0)
    user32.keybd_event(_VK_MASK, 0, _KEYEVENTF_KEYUP, 0)


class HotkeyListener:
    """Feeds chord events plus named shortcut events into a queue for the app loop."""

    def __init__(self, keys: Sequence[str], events: queue.Queue[tuple[str, Any]],
                 shortcuts: dict[str, str]) -> None:
        self._state = ChordState(keys)
        self._events = events
        self._shortcuts = shortcuts
        self._hook: Any = None

    def _on_key(self, event: Any) -> None:
        name = event.name
        if not name or event.scan_code == 0:  # injected keys (our own mask/paste) carry no scan
            return
        result = self._state.on_event(str(name), event.event_type == "down")
        if result == "start" and any(k.endswith("windows") for k in self._state.keys):
            tap_mask_key()
        if result is not None:
            self._events.put((result, time.perf_counter()))

    def start(self) -> None:
        import keyboard

        self._hook = keyboard.hook(self._on_key)
        for action, combo in self._shortcuts.items():
            keyboard.add_hotkey(combo, self._events.put, args=((action, None),), suppress=False)
        log.info("hotkeys active: chord=%s shortcuts=%s", self._state.keys, self._shortcuts)

    def stop(self) -> None:
        import keyboard

        keyboard.unhook_all()

    def wait_for_release(self, timeout_s: float = 2.0) -> bool:
        """Wait until no chord key is held, so a simulated Ctrl+V isn't read as Win+V."""
        import keyboard

        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if not any(keyboard.is_pressed(k) for k in self._state.keys):
                return True
            time.sleep(0.02)
        log.warning("chord keys still held after %.1fs", timeout_s)
        return False
