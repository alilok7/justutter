"""Real Windows clipboard round-trip. Opt-in, because it briefly replaces your clipboard
(it puts the original back afterwards): set UTTER_CLIPBOARD_TESTS=1 to run."""

import ctypes
import os

import pytest

from utter import clipboard

pytestmark = pytest.mark.skipif(os.environ.get("UTTER_CLIPBOARD_TESTS") != "1",
                                reason="touches the real clipboard; set UTTER_CLIPBOARD_TESTS=1")


def _register(name: str) -> int:
    fmt = int(ctypes.windll.user32.RegisterClipboardFormatW(name))
    assert fmt
    return fmt


def test_snapshot_restore_keeps_image_html_and_text() -> None:
    original = clipboard.snapshot()
    try:
        html = _register("HTML Format")
        dib = (b"\x28\x00\x00\x00" + b"\x02\x00\x00\x00" * 2 + b"\x01\x00\x20\x00"
               + b"\x00" * 24 + b"\xff\x00\x00\xff" * 4)  # 2x2 32-bit DIB
        payload = clipboard.ClipboardSnapshot(items=[
            (8, dib), (html, b"Version:0.9\r\n<b>hi</b>\x00"),
            (clipboard.CF_UNICODETEXT, "café 你好\0".encode("utf-16-le")),
        ])
        clipboard.restore(payload)
        snap = clipboard.snapshot()
        formats = dict(snap.items)
        assert formats[8][: len(dib)] == dib
        assert formats[html].startswith(b"Version:0.9")
        assert clipboard.get_text() == "café 你好"

        clipboard.set_text("dictated text")
        assert clipboard.get_text() == "dictated text"
        before = clipboard.sequence_number()
        clipboard.restore(snap)
        assert clipboard.sequence_number() != before
        assert dict(clipboard.snapshot().items)[8][: len(dib)] == dib
    finally:
        clipboard.restore(original)
