"""Deliver text into the focused app without losing the user's clipboard."""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from typing import Literal, Protocol

from pydantic import BaseModel

from utter import clipboard as winclip
from utter.clipboard import ClipboardBusyError, ClipboardSnapshot
from utter.context import WindowInfo, is_blocked

log = logging.getLogger(__name__)

RESTORE_DELAY_S = 0.8


class Clipboard(Protocol):
    def get_text(self) -> str: ...
    def set_text(self, text: str) -> None: ...
    def snapshot(self) -> ClipboardSnapshot: ...
    def restore(self, snap: ClipboardSnapshot) -> None: ...
    def sequence(self) -> int: ...


class Keys(Protocol):
    def send(self, combo: str) -> None: ...
    def write(self, text: str) -> None: ...


class DeliveryResult(BaseModel):
    action: Literal["pasted", "typed", "copied", "blocked", "skipped"]
    reason: str


class SystemClipboard:
    def get_text(self) -> str:
        return winclip.get_text()

    def set_text(self, text: str) -> None:
        winclip.set_text(text)

    def snapshot(self) -> ClipboardSnapshot:
        return winclip.snapshot()

    def restore(self, snap: ClipboardSnapshot) -> None:
        winclip.restore(snap)

    def sequence(self) -> int:
        return winclip.sequence_number()


class SystemKeys:
    def send(self, combo: str) -> None:
        import keyboard

        keyboard.send(combo)

    def write(self, text: str) -> None:
        import keyboard

        keyboard.write(text, delay=0.002)


class PendingRestore(BaseModel):
    """The user's whole clipboard, to put back once the target app has read our paste."""

    snapshot: ClipboardSnapshot
    sequence: int  # clipboard sequence number right after we set our text


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
    try:
        saved = clipboard.snapshot()
    except (ClipboardBusyError, MemoryError, OSError) as exc:
        log.warning("clipboard snapshot failed (%s); typing instead", exc)
        keys.write(text)
        return DeliveryResult(action="typed", reason=f"clipboard unavailable ({exc})"), None
    clipboard.set_text(text)
    sequence = clipboard.sequence()
    try:
        keys.send("ctrl+v")
    except Exception:
        clipboard.restore(saved)
        raise
    result = DeliveryResult(action="pasted", reason=f"into {now.exe or 'focused window'}")
    return result, PendingRestore(snapshot=saved, sequence=sequence)


def restore_clipboard(clipboard: Clipboard, pending: PendingRestore,
                      delay_s: float = RESTORE_DELAY_S) -> bool:
    """Put the user's clipboard back, unless they copied something new in the meantime."""
    time.sleep(delay_s)  # the target app reads the clipboard asynchronously
    if clipboard.sequence() != pending.sequence:
        log.info("clipboard changed since paste; not restoring")
        return False
    clipboard.restore(pending.snapshot)
    return True
