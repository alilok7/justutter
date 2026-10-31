"""Validated settings, stored as JSON in %APPDATA%\\Utter (override with UTTER_HOME)."""

from __future__ import annotations

import json
import logging
import os
import time
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

log = logging.getLogger(__name__)

ModelName = Literal["base.en", "small.en"]


class Mode(StrEnum):
    CHAT = "chat"
    EMAIL = "email"
    DEV = "dev"
    DEFAULT = "default"


class GlossaryEntry(BaseModel):
    heard: str = Field(min_length=1)
    written: str = Field(min_length=1)


class Snippet(BaseModel):
    trigger: str = Field(min_length=1)
    text: str


class ModeRule(BaseModel):
    mode: Mode
    exe: list[str] = Field(default_factory=list)
    title_contains: list[str] = Field(default_factory=list)

    @field_validator("exe", "title_contains")
    @classmethod
    def _lower(cls, values: list[str]) -> list[str]:
        return [v.strip().lower() for v in values if v.strip()]


def _default_glossary() -> list[GlossaryEntry]:
    return [
        GlossaryEntry(heard="mera lion", written="MERaLiON"),
        GlossaryEntry(heard="n u s", written="NUS"),
        GlossaryEntry(heard="nus hackers", written="NUS Hackers"),
        GlossaryEntry(heard="acacia", written="Acacia"),
        GlossaryEntry(heard="git hub", written="GitHub"),
    ]


def _default_snippets() -> list[Snippet]:
    return [
        Snippet(trigger="insert my email", text="hello@example.com"),
        Snippet(trigger="insert sign off", text="Best regards,\nThe Utter team"),
    ]


CONFIG_VERSION = 2
_DEV_EXES = ["code.exe", "cursor.exe", "windowsterminal.exe", "cmd.exe", "powershell.exe",
             "pwsh.exe", "pycharm64.exe", "idea64.exe", "devenv.exe", "wt.exe", "antigravity.exe",
             "antigravity ide.exe", "windsurf.exe", "zed.exe", "sublime_text.exe"]


def _default_mode_rules() -> list[ModeRule]:
    return [
        ModeRule(
            mode=Mode.CHAT,
            exe=["slack.exe", "discord.exe", "ms-teams.exe", "teams.exe", "whatsapp.exe",
                 "telegram.exe", "signal.exe"],
            title_contains=["slack", "discord", "whatsapp", "messenger", "telegram"],
        ),
        ModeRule(
            mode=Mode.EMAIL,
            exe=["outlook.exe", "olk.exe", "thunderbird.exe"],
            title_contains=["gmail", "outlook", "inbox", "compose"],
        ),
        ModeRule(
            mode=Mode.DEV,
            exe=_DEV_EXES,
            title_contains=["visual studio code", "github"],
        ),
    ]


def _default_blocked() -> list[str]:
    return ["keepass.exe", "keepassxc.exe", "1password.exe", "bitwarden.exe", "dashlane.exe",
            "lastpass.exe", "credentialuibroker.exe"]


class Settings(BaseModel):
    config_version: int = CONFIG_VERSION
    hotkey: list[str] = Field(default_factory=lambda: ["ctrl", "windows"], min_length=1,
                              max_length=3)
    undo_hotkey: str = "ctrl+alt+z"
    dashboard_hotkey: str = "ctrl+alt+u"
    model: ModelName = "small.en"
    min_recording_s: float = Field(default=0.3, ge=0.0, le=5.0)
    max_recording_s: float = Field(default=600.0, ge=5.0, le=3600.0)
    no_speech_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    logprob_threshold: float = Field(default=-1.0, le=0.0)
    glossary: list[GlossaryEntry] = Field(default_factory=_default_glossary)
    snippets: list[Snippet] = Field(default_factory=_default_snippets)
    mode_rules: list[ModeRule] = Field(default_factory=_default_mode_rules)
    blocked_exes: list[str] = Field(default_factory=_default_blocked)
    polish_enabled: bool = True
    polish_model: str = Field(default="qwen2.5:1.5b", min_length=1)
    polish_timeout_s: float = Field(default=2.5, gt=0.0, le=30.0)
    polish_min_words: int = Field(default=6, ge=1)
    wispr_pro_monthly_usd: float = Field(default=15.0, ge=0.0)
    wispr_free_weekly_words: int = Field(default=2000, ge=0)

    @field_validator("hotkey")
    @classmethod
    def _hotkey_keys(cls, keys: list[str]) -> list[str]:
        cleaned = [k.strip().lower() for k in keys]
        if any(not k or "+" in k for k in cleaned):
            raise ValueError("hotkey must be a list of single key names, e.g. ['ctrl', 'windows']")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("hotkey keys must be unique")
        return cleaned

    @field_validator("blocked_exes")
    @classmethod
    def _lower_exes(cls, values: list[str]) -> list[str]:
        return [v.strip().lower() for v in values if v.strip()]


def app_dir() -> Path:
    base = os.environ.get("UTTER_HOME") or os.path.join(os.environ.get("APPDATA", "."), "Utter")
    path = Path(base)
    path.mkdir(parents=True, exist_ok=True)
    return path


def models_dir() -> Path:
    base = os.environ.get("UTTER_MODELS") or os.path.join(
        os.environ.get("LOCALAPPDATA", "."), "Utter", "models"
    )
    return Path(base)


def config_path() -> Path:
    return app_dir() / "config.json"


def save_settings(settings: Settings, path: Path | None = None) -> None:
    target = path or config_path()
    tmp = target.with_suffix(".tmp")
    tmp.write_text(settings.model_dump_json(indent=2), encoding="utf-8")
    tmp.replace(target)
    log.info("settings saved to %s", target)


def migrate(data: dict[str, object]) -> bool:
    """Upgrade an older config in place, keeping the user's own edits. Returns True if changed."""
    version = data.get("config_version", 1)
    if not isinstance(version, int) or version >= CONFIG_VERSION:
        return False
    if version < 2:
        if data.get("model") == "base.en":  # old default; the user chose accuracy on 31 Oct
            data["model"] = "small.en"
        rules = data.get("mode_rules")
        if isinstance(rules, list):
            for rule in rules:
                if isinstance(rule, dict) and rule.get("mode") == Mode.DEV.value:
                    exes = rule.setdefault("exe", [])
                    if isinstance(exes, list):
                        exes.extend(e for e in _DEV_EXES if e not in exes)
    data["config_version"] = CONFIG_VERSION
    log.info("migrated config from version %s to %s", version, CONFIG_VERSION)
    return True


def load_settings(path: Path | None = None) -> tuple[Settings, str | None]:
    """Load settings, creating defaults if missing.

    An unreadable or invalid file is moved aside (never deleted) and defaults are used; the
    returned warning tells the caller to show the user what happened.
    """
    target = path or config_path()
    if not target.exists():
        settings = Settings()
        save_settings(settings, target)
        return settings, None
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        migrated = migrate(data)
        settings = Settings.model_validate(data)
        if migrated:
            save_settings(settings, target)
        return settings, None
    except (json.JSONDecodeError, ValidationError, UnicodeDecodeError, TypeError) as exc:
        backup = target.with_name(f"config.invalid-{int(time.time())}.json")
        target.replace(backup)
        log.error("invalid config %s moved to %s: %s", target, backup, exc)
        settings = Settings()
        save_settings(settings, target)
        return settings, f"config.json was invalid and was moved to {backup.name}; using defaults"
