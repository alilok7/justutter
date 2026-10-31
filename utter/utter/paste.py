"""Deliver text into the focused app without losing the user's clipboard."""

from __future__ import annotations

import ctypes
import logging
import time
from collections.abc import Sequence
from typing import Literal, Protocol

from pydantic import BaseModel

from utter.context import WindowInfo, is_blocked

log = logging.getLogger(__name__)

_CF_UNICODETEXT = 13
RESTORE_DELAY_S = 0.4


class Clipboard(Protocol):
    def get_text(self) -> str: ...
    def set_text(self, text: str) -> None: ...
    def holds_non_text(self) -> bool: ...


class Keys(Protocol):
    def send(self, combo: str) -> None: ...
    def write(self, text: str) -> None: ...


class DeliveryResult(BaseModel):
    action: Literal["pasted", "typed", "copied", "blocked", "skipped"]
    reason: str


class SystemClipboard:
    def get_text(self) -> str:
        import pyperclip

        return str(pyperclip.paste() or "")

    def set_text(self, text: str) -> None:
        import pyperclip

        pyperclip.copy(text)

    def holds_non_text(self) -> bool:
        user32 = ctypes.windll.user32
        has_formats = int(user32.CountClipboardFormats()) > 0
        return has_formats and not user32.IsClipboardFormatAvailable(_CF_UNICODETEXT)


class SystemKeys:
    def send(self, combo: str) -> None:
        import keyboard

        keyboard.send(combo)

    def write(self, text: str) -> None:
        import keyboard

        keyboard.write(text, delay=0.002)


def deliver(text: str, start: WindowInfo, now: WindowInfo, blocked_exes: Sequence[str],
            clipboard: Clipboard, keys: Keys, sleep: float = RESTORE_DELAY_S) -> DeliveryResult:
    if not text:
        return DeliveryResult(action="skipped", reason="nothing to insert")
    if is_blocked(now, blocked_exes) or is_blocked(start, blocked_exes):
        app = now.exe or start.exe
        return DeliveryResult(action="blocked", reason=f"{app} is on the blocklist")
    if now.hwnd != start.hwnd:
        clipboard.set_text(text)
        log.info("window changed (%s -> %s); copied instead of pasting", start.exe, now.exe)
        return DeliveryResult(action="copied", reason="window changed; press Ctrl+V to paste")
    if clipboard.holds_non_text():
        keys.write(text)
        return DeliveryResult(action="typed", reason="clipboard holds non-text data; kept it")
    previous = clipboard.get_text()
    clipboard.set_text(text)
    try:
        keys.send("ctrl+v")
        time.sleep(sleep)  # the target app reads the clipboard asynchronously
    finally:
        clipboard.set_text(previous)
    return DeliveryResult(action="pasted", reason=f"into {now.exe or 'focused window'}")
