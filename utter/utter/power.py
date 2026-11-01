"""Keep transcription fast on battery: opt this process out of Windows power throttling.

Windows 11 runs background processes (JustUtter has no foreground window) in "EcoQoS" on
battery: efficiency cores at low clock speed. Dictation is latency-sensitive, so we ask for
normal execution speed. This uses the documented SetProcessInformation(ProcessPowerThrottling)
API; it does not change the system power plan.
"""

from __future__ import annotations

import ctypes
import logging
import os
from ctypes import wintypes

log = logging.getLogger(__name__)

_PROCESS_POWER_THROTTLING = 4  # PROCESS_INFORMATION_CLASS.ProcessPowerThrottling
_THROTTLING_CURRENT_VERSION = 1
_THROTTLING_EXECUTION_SPEED = 0x1
_ABOVE_NORMAL_PRIORITY_CLASS = 0x00008000


class _ThrottlingState(ctypes.Structure):
    _fields_ = [("Version", wintypes.ULONG), ("ControlMask", wintypes.ULONG),
                ("StateMask", wintypes.ULONG)]


def keep_full_speed() -> bool:
    """Disable execution-speed throttling and raise priority slightly. Returns success."""
    if os.name != "nt":
        return False
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.SetProcessInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                               wintypes.DWORD]
    kernel32.SetProcessInformation.restype = wintypes.BOOL
    kernel32.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.SetPriorityClass.restype = wintypes.BOOL
    process = kernel32.GetCurrentProcess()
    # ControlMask selects the policy we manage; StateMask 0 means "do not throttle".
    state = _ThrottlingState(_THROTTLING_CURRENT_VERSION, _THROTTLING_EXECUTION_SPEED, 0)
    ok = bool(kernel32.SetProcessInformation(process, _PROCESS_POWER_THROTTLING,
                                             ctypes.byref(state), ctypes.sizeof(state)))
    if not ok:
        log.warning("could not opt out of power throttling (error %d)", ctypes.get_last_error())
    if not kernel32.SetPriorityClass(process, _ABOVE_NORMAL_PRIORITY_CLASS):
        log.warning("could not raise process priority (error %d)", ctypes.get_last_error())
    log.info("power throttling opt-out: %s", "ok" if ok else "failed")
    return ok
