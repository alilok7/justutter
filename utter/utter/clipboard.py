"""Whole-clipboard snapshot and restore (images, HTML, files, text) via the Win32 API.

Only memory-based (HGLOBAL) formats are copied. GDI-handle formats (bitmaps, metafiles,
palettes) and OLE-private formats are skipped: Windows regenerates the GDI ones from the
memory formats (e.g. CF_BITMAP from CF_DIB), and OLE data only makes sense to its source app.
"""

from __future__ import annotations

import ctypes
import logging
import time
from ctypes import wintypes

from pydantic import BaseModel

log = logging.getLogger(__name__)

CF_UNICODETEXT = 13
_GMEM_MOVEABLE = 0x0002
_GDI_FORMATS = frozenset({2, 3, 9, 14, 0x0080, 0x0082, 0x0083, 0x008E})
_SKIP_NAMES = frozenset({"DataObject", "Ole Private Data", "Object Descriptor",
                         "Link Source Descriptor", "OwnerLink", "ObjectLink", "Embed Source",
                         "Link Source", "Native"})
MAX_SNAPSHOT_BYTES = 64 * 1024 * 1024


class ClipboardSnapshot(BaseModel):
    items: list[tuple[int, bytes]]

    @property
    def size(self) -> int:
        return sum(len(data) for _, data in self.items)


class ClipboardBusyError(OSError):
    """Another application kept the clipboard open."""


def _api() -> tuple[ctypes.WinDLL, ctypes.WinDLL]:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.EnumClipboardFormats.argtypes = [wintypes.UINT]
    user32.EnumClipboardFormats.restype = wintypes.UINT
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    user32.GetClipboardFormatNameW.argtypes = [wintypes.UINT, wintypes.LPWSTR, ctypes.c_int]
    user32.GetClipboardFormatNameW.restype = ctypes.c_int
    user32.GetClipboardSequenceNumber.restype = wintypes.DWORD
    kernel32.GlobalSize.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalSize.restype = ctypes.c_size_t
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = wintypes.LPVOID
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalFree.restype = wintypes.HGLOBAL
    return user32, kernel32


class _Open:
    """Context manager that opens the clipboard, retrying while another app holds it."""

    def __init__(self, user32: ctypes.WinDLL, attempts: int = 20) -> None:
        self.user32 = user32
        self.attempts = attempts

    def __enter__(self) -> None:
        for _ in range(self.attempts):
            if self.user32.OpenClipboard(None):
                return
            time.sleep(0.02)
        raise ClipboardBusyError("clipboard is held by another application")

    def __exit__(self, *_exc: object) -> None:
        self.user32.CloseClipboard()


def sequence_number() -> int:
    user32, _ = _api()
    return int(user32.GetClipboardSequenceNumber())


def snapshot(max_bytes: int = MAX_SNAPSHOT_BYTES) -> ClipboardSnapshot:
    """Copy every restorable clipboard format. Raises ClipboardBusyError or MemoryError."""
    user32, kernel32 = _api()
    items: list[tuple[int, bytes]] = []
    total = 0
    name = ctypes.create_unicode_buffer(256)
    with _Open(user32):
        fmt = 0
        while fmt := int(user32.EnumClipboardFormats(fmt)):
            if fmt in _GDI_FORMATS:
                continue
            if fmt >= 0xC000 and user32.GetClipboardFormatNameW(fmt, name, 256) \
                    and name.value in _SKIP_NAMES:
                continue
            handle = user32.GetClipboardData(fmt)
            if not handle:
                continue
            size = int(kernel32.GlobalSize(handle))
            ptr = kernel32.GlobalLock(handle)
            if not ptr:
                continue
            try:
                total += size
                if total > max_bytes:
                    raise MemoryError(f"clipboard larger than {max_bytes} bytes")
                items.append((fmt, ctypes.string_at(ptr, size)))
            finally:
                kernel32.GlobalUnlock(handle)
    return ClipboardSnapshot(items=items)


def restore(snap: ClipboardSnapshot) -> None:
    """Replace the clipboard with a snapshot (an empty snapshot clears it)."""
    user32, kernel32 = _api()
    with _Open(user32):
        user32.EmptyClipboard()
        for fmt, data in snap.items:
            handle = kernel32.GlobalAlloc(_GMEM_MOVEABLE, max(1, len(data)))
            if not handle:
                raise MemoryError("GlobalAlloc failed")
            ptr = kernel32.GlobalLock(handle)
            if not ptr:
                kernel32.GlobalFree(handle)
                raise MemoryError("GlobalLock failed")
            ctypes.memmove(ptr, data, len(data))
            kernel32.GlobalUnlock(handle)
            if not user32.SetClipboardData(fmt, handle):
                kernel32.GlobalFree(handle)  # ownership only passes on success
                log.warning("could not restore clipboard format %d", fmt)


def set_text(text: str) -> None:
    data = (text + "\0").encode("utf-16-le")
    restore(ClipboardSnapshot(items=[(CF_UNICODETEXT, data)]))


def get_text() -> str:
    user32, kernel32 = _api()
    with _Open(user32):
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return ""
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            return ""
        try:
            return ctypes.wstring_at(ptr)
        finally:
            kernel32.GlobalUnlock(handle)
