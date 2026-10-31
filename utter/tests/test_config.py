import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from utter.config import Mode, Settings, load_settings, save_settings


def test_defaults_are_valid() -> None:
    s = Settings()
    assert s.hotkey == ["ctrl", "windows"]
    assert s.model == "small.en"
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


def test_v1_config_is_migrated_keeping_user_edits(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    old = Settings().model_dump(mode="json")
    old.pop("config_version")
    old["model"] = "base.en"
    old["glossary"] = [{"heard": "ptero", "written": "Pterodactylus"}]
    for rule in old["mode_rules"]:
        if rule["mode"] == "dev":
            rule["exe"] = ["code.exe", "my-editor.exe"]
    path.write_text(json.dumps(old), encoding="utf-8")

    settings, warning = load_settings(path)
    assert warning is None
    assert settings.config_version == 2
    assert settings.model == "small.en"
    assert [g.written for g in settings.glossary] == ["Pterodactylus"]
    dev = next(r for r in settings.mode_rules if r.mode is Mode.DEV)
    assert "my-editor.exe" in dev.exe and "antigravity ide.exe" in dev.exe
    assert json.loads(path.read_text())["config_version"] == 2


def test_v1_config_with_user_chosen_model_is_kept(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"model": "small.en", "hotkey": ["right ctrl"]}), encoding="utf-8")
    settings, _ = load_settings(path)
    assert settings.model == "small.en" and settings.hotkey == ["right ctrl"]


def test_exe_names_are_normalised() -> None:
    s = Settings.model_validate({"blocked_exes": ["  KeePass.EXE ", ""]})
    assert s.blocked_exes == ["keepass.exe"]
