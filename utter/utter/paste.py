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
RESTORE_DELAY_S = 0.8


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


class PendingRestore(BaseModel):
    """Clipboard text to put back once the target app has read our paste."""

    inserted: str
    previous: str


def deliver(text: str, start: WindowInfo, now: WindowInfo, blocked_exes: Sequence[str],
            clipboard: Clipboard, keys: Keys) -> tuple[DeliveryResult, PendingRestore | None]:
    """Insert text; returns the result immediately plus any clipboard restore still owed.

    Call ``restore_clipboard`` with the second value after reporting success to the user.
    """
    if not text:
        return DeliveryResult(action="skipped", reason="nothing to insert"), None
    if is_blocked(now, blocked_exes) or is_blocked(start, blocked_exes):
        app = now.exe or start.exe
        return DeliveryResult(action="blocked", reason=f"{app} is on the blocklist"), None
    if now.hwnd != start.hwnd:
        clipboard.set_text(text)
        log.info("window changed (%s -> %s); copied instead of pasting", start.exe, now.exe)
        return DeliveryResult(action="copied", reason="window changed; press Ctrl+V to paste"), None
    if clipboard.holds_non_text():
        keys.write(text)
        return DeliveryResult(action="typed", reason="clipboard holds non-text data; kept it"), None
    previous = clipboard.get_text()
    clipboard.set_text(text)
    try:
        keys.send("ctrl+v")
    except Exception:
        clipboard.set_text(previous)
        raise
    result = DeliveryResult(action="pasted", reason=f"into {now.exe or 'focused window'}")
    return result, PendingRestore(inserted=text, previous=previous)


def restore_clipboard(clipboard: Clipboard, pending: PendingRestore,
                      delay_s: float = RESTORE_DELAY_S) -> bool:
    """Put the user's clipboard back, unless they copied something new in the meantime."""
    time.sleep(delay_s)  # the target app reads the clipboard asynchronously
    if clipboard.get_text() != pending.inserted:
        log.info("clipboard changed since paste; not restoring")
        return False
    clipboard.set_text(pending.previous)
    return True
