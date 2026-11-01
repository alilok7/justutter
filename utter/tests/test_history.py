"""Saved transcription history (O2) and the paste-last default hotkey (O1)."""

from datetime import datetime
from pathlib import Path

from utter.config import Mode, Settings
from utter.history import Dictation, History


def dictation(text: str) -> Dictation:
    return Dictation(at=datetime.now(), app="notepad.exe", mode=Mode.DEFAULT, raw=text.lower(),
                     clean=text, rules=[], latency_s=1.2, action="pasted")


def test_history_survives_a_restart(tmp_path: Path) -> None:
    path = tmp_path / "history.jsonl"
    h = History(size=500, path=path)
    h.add(dictation("First note."))
    h.add(dictation("Second note."))
    reopened = History(size=500, path=path)
    assert [d.clean for d in reopened.items()] == ["Second note.", "First note."]
    last = reopened.last()
    assert last is not None and last.clean == "Second note."


def test_history_file_is_bounded(tmp_path: Path) -> None:
    path = tmp_path / "history.jsonl"
    h = History(size=3, path=path)
    for i in range(5):
        h.add(dictation(f"Note {i}."))
    reopened = History(size=3, path=path)
    assert [d.clean for d in reopened.items()] == ["Note 4.", "Note 3.", "Note 2."]
    assert len(path.read_text(encoding="utf-8").splitlines()) == 3


def test_corrupt_lines_are_skipped_not_fatal(tmp_path: Path) -> None:
    path = tmp_path / "history.jsonl"
    path.write_text(dictation("Good.").model_dump_json() + "\n{broken\n", encoding="utf-8")
    h = History(size=10, path=path)
    assert [d.clean for d in h.items()] == ["Good."]
    assert len(path.read_text(encoding="utf-8").splitlines()) == 1


def test_clear_deletes_saved_history(tmp_path: Path) -> None:
    path = tmp_path / "history.jsonl"
    h = History(size=10, path=path)
    h.add(dictation("Private."))
    h.clear()
    assert h.last() is None
    assert not path.exists()
    assert History(size=10, path=path).last() is None


def test_history_without_path_stays_in_memory(tmp_path: Path) -> None:
    h = History(size=10)
    h.add(dictation("Memory only."))
    assert h.last() is not None
    assert list(tmp_path.iterdir()) == []


def test_unicode_and_newlines_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "history.jsonl"
    History(size=10, path=path).add(dictation("Hi Tan,\n\n1. 你好\n2. café 🙂"))
    last = History(size=10, path=path).last()
    assert last is not None and last.clean == "Hi Tan,\n\n1. 你好\n2. café 🙂"


def test_defaults() -> None:
    s = Settings()
    assert s.paste_last_hotkey == "alt+shift+z"
    assert s.save_history is True
