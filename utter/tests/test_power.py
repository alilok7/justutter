import ctypes
import os
from ctypes import wintypes

import pytest

from utter.power import keep_full_speed


@pytest.mark.skipif(os.name != "nt", reason="Windows-only API")
def test_opt_out_of_power_throttling_succeeds() -> None:
    assert keep_full_speed() is True
    kernel32 = ctypes.WinDLL("kernel32")
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.GetPriorityClass.argtypes = [wintypes.HANDLE]
    assert kernel32.GetPriorityClass(kernel32.GetCurrentProcess()) == 0x00008000
