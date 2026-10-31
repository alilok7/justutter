import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from utter.config import Mode, Settings, load_settings, save_settings


def test_defaults_are_valid() -> None:
    s = Settings()
    assert s.hotkey == ["ctrl", "windows"]
    assert s.model == "base.en"
    assert {r.mode for r in s.mode_rules} == {Mode.CHAT, Mode.EMAIL, Mode.DEV}


def test_missing_file_creates_defaults(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    settings, warning = load_settings(path)
    assert warning is None
    assert path.exists()
    assert Settings.model_validate_json(path.read_text()) == settings


def test_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    original = Settings(model="small.en", hotkey=["right ctrl"])
    save_settings(original, path)
    loaded, warning = load_settings(path)
    assert warning is None
    assert loaded == original


@pytest.mark.parametrize(
    "bad",
    [
        {"hotkey": []},
        {"hotkey": ["ctrl+windows"]},
        {"hotkey": ["ctrl", "ctrl"]},
        {"model": "large-v3"},
        {"glossary": [{"heard": "", "written": "X"}]},
        {"no_speech_threshold": 2},
    ],
)
def test_invalid_values_rejected(bad: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate(bad)


def test_invalid_file_is_moved_aside_not_deleted(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"model": "nope"}), encoding="utf-8")
    settings, warning = load_settings(path)
    assert settings == Settings()
    assert warning is not None and "invalid" in warning
    backups = list(tmp_path.glob("config.invalid-*.json"))
    assert len(backups) == 1
    assert json.loads(backups[0].read_text()) == {"model": "nope"}


def test_corrupt_json_is_moved_aside(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text("{not json", encoding="utf-8")
    _, warning = load_settings(path)
    assert warning is not None
    assert len(list(tmp_path.glob("config.invalid-*.json"))) == 1


def test_exe_names_are_normalised() -> None:
    s = Settings.model_validate({"blocked_exes": ["  KeePass.EXE ", ""]})
    assert s.blocked_exes == ["keepass.exe"]
