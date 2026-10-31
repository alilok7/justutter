from datetime import date

import numpy as np
import pytest

from utter.audio import resample
from utter.config import Mode, Settings
from utter.context import WindowInfo, categorize, is_blocked
from utter.history import History, Stats, iso_week
from utter.paste import deliver, restore_clipboard

BLOCKED = Settings().blocked_exes
RULES = Settings().mode_rules


def win(hwnd: int = 1, exe: str = "notepad.exe", title: str = "Untitled - Notepad") -> WindowInfo:
    return WindowInfo(hwnd=hwnd, pid=10, exe=exe, title=title)


class FakeClipboard:
    def __init__(self, text: str = "user's copied text", non_text: bool = False) -> None:
        self.text = text
        self.non_text = non_text
        self.history: list[str] = []

    def get_text(self) -> str:
        return self.text

    def set_text(self, text: str) -> None:
        self.text = text
        self.history.append(text)

    def holds_non_text(self) -> bool:
        return self.non_text


class FakeKeys:
    def __init__(self, clipboard: FakeClipboard) -> None:
        self.clipboard = clipboard
        self.pasted: list[str] = []
        self.typed: list[str] = []

    def send(self, combo: str) -> None:
        assert combo == "ctrl+v"
        self.pasted.append(self.clipboard.text)

    def write(self, text: str) -> None:
        self.typed.append(text)


def test_paste_reports_first_then_restores_clipboard() -> None:
    cb = FakeClipboard()
    keys = FakeKeys(cb)
    result, pending = deliver("Hello", win(), win(), BLOCKED, cb, keys)
    assert result.action == "pasted"
    assert keys.pasted == ["Hello"]
    assert pending is not None
    assert cb.text == "Hello"  # not restored yet: the app may still be reading it
    assert restore_clipboard(cb, pending, delay_s=0) is True
    assert cb.text == "user's copied text"


def test_restore_skipped_if_user_copied_something_new() -> None:
    cb = FakeClipboard()
    _, pending = deliver("Hello", win(), win(), BLOCKED, cb, FakeKeys(cb))
    assert pending is not None
    cb.text = "something the user just copied"
    assert restore_clipboard(cb, pending, delay_s=0) is False
    assert cb.text == "something the user just copied"


def test_unicode_roundtrip() -> None:
    cb = FakeClipboard(text="原文 🙂")
    keys = FakeKeys(cb)
    _, pending = deliver("Café — naïve 你好", win(), win(), BLOCKED, cb, keys)
    assert pending is not None
    restore_clipboard(cb, pending, delay_s=0)
    assert keys.pasted == ["Café — naïve 你好"]
    assert cb.text == "原文 🙂"


def test_window_changed_copies_instead() -> None:
    cb = FakeClipboard()
    keys = FakeKeys(cb)
    result, pending = deliver("Hello", win(hwnd=1), win(hwnd=2, exe="chrome.exe"), BLOCKED, cb,
                              keys)
    assert result.action == "copied"
    assert pending is None
    assert keys.pasted == [] and keys.typed == []
    assert cb.text == "Hello"


def test_non_text_clipboard_is_typed_and_untouched() -> None:
    cb = FakeClipboard(text="", non_text=True)
    keys = FakeKeys(cb)
    result, pending = deliver("Hello", win(), win(), BLOCKED, cb, keys)
    assert result.action == "typed"
    assert pending is None
    assert keys.typed == ["Hello"]
    assert cb.history == []


def test_blocked_app() -> None:
    cb = FakeClipboard()
    keys = FakeKeys(cb)
    pw = win(exe="keepassxc.exe", title="KeePassXC")
    result, _ = deliver("secret", pw, pw, BLOCKED, cb, keys)
    assert result.action == "blocked"
    assert cb.history == [] and keys.pasted == []


def test_empty_text_skipped() -> None:
    cb = FakeClipboard()
    assert deliver("", win(), win(), BLOCKED, cb, FakeKeys(cb))[0].action == "skipped"


def test_clipboard_restored_immediately_if_paste_fails() -> None:
    cb = FakeClipboard()

    class BrokenKeys(FakeKeys):
        def send(self, combo: str) -> None:
            raise RuntimeError("injection failed")

    with pytest.raises(RuntimeError):
        deliver("Hello", win(), win(), BLOCKED, cb, BrokenKeys(cb))
    assert cb.text == "user's copied text"


@pytest.mark.parametrize(
    ("exe", "title", "mode"),
    [
        ("slack.exe", "Slack | general", Mode.CHAT),
        ("chrome.exe", "Inbox (3) - me@gmail.com - Gmail", Mode.EMAIL),
        ("outlook.exe", "Mail", Mode.EMAIL),
        ("code.exe", "app.py - utter - Visual Studio Code", Mode.DEV),
        ("windowsterminal.exe", "PowerShell", Mode.DEV),
        ("msedge.exe", "WhatsApp", Mode.CHAT),
        ("notepad.exe", "Untitled - Notepad", Mode.DEFAULT),
        ("", "", Mode.DEFAULT),
    ],
)
def test_categorize(exe: str, title: str, mode: Mode) -> None:
    assert categorize(win(exe=exe, title=title), RULES) is mode


def test_is_blocked_case_insensitive() -> None:
    assert is_blocked(win(exe="Bitwarden.exe"), BLOCKED)
    assert not is_blocked(win(), BLOCKED)


def test_resample_length_and_dtype() -> None:
    audio = np.ones(44100, dtype=np.float32)
    out = resample(audio, 44100)
    assert out.dtype == np.float32
    assert out.size == 16000
    assert resample(np.zeros(0, np.float32), 44100).size == 0


def test_history_is_bounded_and_newest_first() -> None:
    from datetime import datetime

    h = History(size=2)
    for i in range(3):
        from utter.history import Dictation

        h.add(Dictation(at=datetime.now(), app="x", mode=Mode.DEFAULT, raw=str(i), clean=str(i),
                        rules=[], latency_s=0.1, action="pasted"))
    assert [d.raw for d in h.items()] == ["2", "1"]
    last = h.last()
    assert last is not None and last.raw == "2"


def test_stats_week_rollover() -> None:
    s = Stats(week=iso_week(date(2026, 10, 26)))
    s.record(1500, 0.5, today=date(2026, 10, 27))
    s.record(800, 0.7, today=date(2026, 10, 28))
    assert s.words_week == 2300
    assert s.words_over_free_cap(2000) == 300
    s.record(10, 0.6, today=date(2026, 11, 3))
    assert s.words_week == 10
    assert s.words_total == 2310
    assert s.median_latency() == 0.6
