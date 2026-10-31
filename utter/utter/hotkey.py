"""Hold-to-talk and hands-free chord detection (default Ctrl+Win, Ctrl+Win+Space).

``ChordState`` is pure logic and unit-tested; ``HotkeyListener`` wires it to real key events and
adds a watchdog that reads the physical key state, so a lost key-up can't leave it recording.
"""

from __future__ import annotations

import ctypes
import logging
import queue
import threading
import time
from collections.abc import Sequence
from typing import Any, Literal

log = logging.getLogger(__name__)

ChordEvent = Literal["start", "stop", "cancel", "handsfree"]
Mode = Literal["idle", "hold", "handsfree"]

_VK_MASK = 0xE8  # unassigned virtual key; tapping it stops Win's key-up from opening Start
_KEYEVENTF_KEYUP = 0x0002
STALE_OTHER_KEY_S = 10.0
_VK: dict[str, tuple[int, ...]] = {
    "ctrl": (0x11,), "left ctrl": (0xA2,), "right ctrl": (0xA3,),
    "shift": (0x10,), "left shift": (0xA0,), "right shift": (0xA1,),
    "alt": (0x12,), "left alt": (0xA4,), "right alt": (0xA5,),
    "windows": (0x5B, 0x5C), "left windows": (0x5B,), "right windows": (0x5C,),
    **{f"f{i}": (0x6F + i,) for i in range(1, 25)},
}


def key_matches(configured: str, event_name: str) -> bool:
    """'ctrl' matches 'ctrl', 'left ctrl' and 'right ctrl'; 'right ctrl' matches only itself."""
    name = event_name.lower()
    return name == configured or (
        not configured.startswith(("left ", "right ")) and name.endswith(" " + configured)
    )


class ChordState:
    def __init__(self, keys: Sequence[str], handsfree_key: str = "space",
                 cancel_key: str = "esc") -> None:
        self.keys = list(keys)
        self.handsfree_key = handsfree_key
        self.cancel_key = cancel_key
        self.down: set[str] = set()
        self.others: dict[str, float] = {}
        self.mode: Mode = "idle"
        self.await_release = False  # after a stop/cancel, ignore the chord until keys are released
        self.rearmed = False  # hands-free: chord fully released once, so the next press finishes
        self.cancel_reason: str | None = None

    def _chord_key(self, name: str) -> str | None:
        return next((k for k in self.keys if key_matches(k, name)), None)

    def _full(self) -> bool:
        return len(self.down) == len(self.keys)

    def on_event(self, name: str, is_down: bool, now: float = 0.0) -> ChordEvent | None:
        key = self._chord_key(name)
        if key is None:
            return self._other(name.lower(), is_down, now)
        if is_down:
            self.down.add(key)
            if not self._full():
                return None
            self.others = {k: t for k, t in self.others.items() if now - t < STALE_OTHER_KEY_S}
            if self.mode == "idle" and not self.others and not self.await_release:
                self.mode = "hold"
                return "start"
            if self.mode == "handsfree" and self.rearmed:
                self.mode, self.await_release = "idle", True
                return "stop"
            return None
        self.down.discard(key)
        if not self.down:
            self.await_release = False
            if self.mode == "handsfree":
                self.rearmed = True
        if self.mode == "hold":
            self.mode, self.await_release = "idle", bool(self.down)
            return "stop"
        return None

    def _other(self, name: str, is_down: bool, now: float) -> ChordEvent | None:
        if not is_down:
            self.others.pop(name, None)
            return None
        repeat = name in self.others
        self.others.setdefault(name, now)
        if repeat or self.mode == "idle":
            return None
        if self.mode == "hold" and name == self.handsfree_key:
            self.mode, self.rearmed = "handsfree", False
            return "handsfree"
        if name == self.cancel_key:
            self.mode, self.await_release = "idle", bool(self.down)
            self.cancel_reason = "Esc"
            return "cancel"
        return None  # any other key: keep recording

    def force_stop(self) -> ChordEvent | None:
        """Stop an active recording from outside the key stream (watchdog, time limit)."""
        if self.mode == "idle":
            return None
        self.mode, self.await_release = "idle", bool(self.down)
        self.down.clear()
        return "stop"


def tap_mask_key() -> None:
    user32 = ctypes.windll.user32
    user32.keybd_event(_VK_MASK, 0, 0, 0)
    user32.keybd_event(_VK_MASK, 0, _KEYEVENTF_KEYUP, 0)


def physically_down(key: str) -> bool | None:
    """Real key state from the OS (None if the key isn't in the lookup table)."""
    vks = _VK.get(key.lower())
    if vks is None:
        return None
    user32 = ctypes.windll.user32
    return any(user32.GetAsyncKeyState(vk) & 0x8000 for vk in vks)


class HotkeyListener:
    """Feeds chord events plus named shortcut events into a queue for the app loop."""

    def __init__(self, keys: Sequence[str], events: queue.Queue[tuple[str, Any]],
                 shortcuts: dict[str, str]) -> None:
        self._state = ChordState(keys)
        self._lock = threading.Lock()
        self._events = events
        self._shortcuts = shortcuts
        self._stuck_hits = 0
        self._uses_win = any(k.endswith("windows") for k in keys)

    @property
    def mode(self) -> Mode:
        return self._state.mode

    def _on_key(self, event: Any) -> None:
        name = event.name
        if not name or event.scan_code == 0:  # injected keys (our own mask/paste) carry no scan
            return
        with self._lock:
            before = self._state.mode
            result = self._state.on_event(str(name), event.event_type == "down",
                                          time.monotonic())
            reason = self._state.cancel_reason
        if self._uses_win and (result == "start" or (result == "stop" and before == "handsfree")):
            tap_mask_key()
        if result is not None:
            log.info("chord event %s (mode %s -> %s)", result, before, self._state.mode)
            self._events.put((result, (time.perf_counter(), reason)))

    def check_stuck(self) -> bool:
        """Watchdog for hold mode: True if the OS says a chord key is up but we missed it."""
        with self._lock:
            if self._state.mode != "hold":
                self._stuck_hits = 0
                return False
            if any(physically_down(k) is False for k in self._state.keys):
                self._stuck_hits += 1
            else:
                self._stuck_hits = 0
            if self._stuck_hits >= 2:
                self._stuck_hits = 0
                self._state.force_stop()
                log.warning("watchdog: chord key released without an event; stopping")
                return True
        return False

    def force_stop(self) -> None:
        with self._lock:
            self._state.force_stop()

    def start(self) -> None:
        import keyboard

        keyboard.hook(self._on_key)
        for action, combo in self._shortcuts.items():
            keyboard.add_hotkey(combo, self._events.put, args=((action, None),), suppress=False)
        log.info("hotkeys active: chord=%s shortcuts=%s", self._state.keys, self._shortcuts)

    def stop(self) -> None:
        import keyboard

        keyboard.unhook_all()

    def wait_for_release(self, keys: Sequence[str] | None = None, timeout_s: float = 2.0) -> bool:
        """Wait until the given keys (default: the chord) are physically up, so a simulated
        Ctrl+V isn't read as Win+V."""
        import keyboard

        targets = list(keys or self._state.keys)
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            states = [physically_down(k) for k in targets]
            held = [s if s is not None else keyboard.is_pressed(k) for k, s in zip(targets, states,
                                                                                   strict=True)]
            if not any(held):
                return True
            time.sleep(0.02)
        log.warning("keys %s still held after %.1fs", targets, timeout_s)
        return False
