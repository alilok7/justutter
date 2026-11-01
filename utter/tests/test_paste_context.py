from datetime import date

import numpy as np
import pytest

from utter.audio import resample
from utter.clipboard import ClipboardBusyError, ClipboardSnapshot
from utter.config import Mode, Settings
from utter.context import WindowInfo, categorize, is_blocked
from utter.history import History, Stats, iso_week
from utter.paste import deliver, restore_clipboard

BLOCKED = Settings().blocked_exes
RULES = Settings().mode_rules


def win(hwnd: int = 1, exe: str = "notepad.exe", title: str = "Untitled - Notepad") -> WindowInfo:
    return WindowInfo(hwnd=hwnd, pid=10, exe=exe, title=title)


CF_DIB = 8


class FakeClipboard:
    """Holds clipboard 'formats' like the real one: text and/or an image."""

    def __init__(self, text: str = "user's copied text", image: bytes | None = None,
                 busy: bool = False) -> None:
        self.items: list[tuple[int, bytes]] = []
        if text:
            self.items.append((13, text.encode("utf-16-le")))
        if image is not None:
            self.items.append((CF_DIB, image))
        self.busy = busy
        self.seq = 1
        self.history: list[str] = []

    @property
    def text(self) -> str:
        return next((d.decode("utf-16-le") for f, d in self.items if f == 13), "")

    def get_text(self) -> str:
        return self.text

    def set_text(self, text: str) -> None:
        self.items = [(13, text.encode("utf-16-le"))]
        self.seq += 1
        self.history.append(text)

    def snapshot(self) -> ClipboardSnapshot:
        if self.busy:
            raise ClipboardBusyError("held by another app")
        return ClipboardSnapshot(items=list(self.items))

    def restore(self, snap: ClipboardSnapshot) -> None:
        self.items = list(snap.items)
        self.seq += 1

    def sequence(self) -> int:
        return self.seq

    def user_copies(self, text: str) -> None:
        self.items = [(13, text.encode("utf-16-le"))]
        self.seq += 1


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
    cb.user_copies("something the user just copied")
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


def test_image_on_clipboard_is_pasted_over_and_restored() -> None:
    image = b"BITMAPINFOHEADER-and-pixels"
    cb = FakeClipboard(text="", image=image)
    keys = FakeKeys(cb)
    result, pending = deliver("Hello", win(), win(), BLOCKED, cb, keys)
    assert result.action == "pasted"  # no slow key-by-key typing any more
    assert keys.pasted == ["Hello"] and keys.typed == []
    assert pending is not None
    restore_clipboard(cb, pending, delay_s=0)
    assert cb.items == [(CF_DIB, image)]


def test_busy_clipboard_falls_back_to_typing() -> None:
    cb = FakeClipboard(busy=True)
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
