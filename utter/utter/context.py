"""Foreground app detection. Reads only the window's process name and title, never its text."""

from __future__ import annotations

import ctypes
import logging
import os
from collections.abc import Sequence
from ctypes import wintypes

from pydantic import BaseModel

from utter.config import Mode, ModeRule

log = logging.getLogger(__name__)

_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


class WindowInfo(BaseModel):
    hwnd: int
    pid: int
    exe: str
    title: str


def foreground_window() -> WindowInfo:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    hwnd = int(user32.GetForegroundWindow() or 0)
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    length = int(user32.GetWindowTextLengthW(hwnd))
    title_buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, title_buf, length + 1)
    exe = ""
    handle = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if handle:
        try:
            size = wintypes.DWORD(1024)
            path_buf = ctypes.create_unicode_buffer(size.value)
            if kernel32.QueryFullProcessImageNameW(handle, 0, path_buf, ctypes.byref(size)):
                exe = os.path.basename(path_buf.value).lower()
        finally:
            kernel32.CloseHandle(handle)
    else:
        log.info("could not open process %d (elevated or protected)", pid.value)
    return WindowInfo(hwnd=hwnd, pid=int(pid.value), exe=exe, title=title_buf.value)


def categorize(info: WindowInfo, rules: Sequence[ModeRule]) -> Mode:
    exe = info.exe.lower()
    for rule in rules:
        if exe and exe in rule.exe:
            return rule.mode
    title = info.title.lower()
    for rule in rules:
        if any(fragment in title for fragment in rule.title_contains):
            return rule.mode
    return Mode.DEFAULT


def is_blocked(info: WindowInfo, blocked_exes: Sequence[str]) -> bool:
    return info.exe.lower() in blocked_exes
