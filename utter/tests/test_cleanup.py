import json
from pathlib import Path

import pytest

from utter.cleanup import clean
from utter.config import GlossaryEntry, Mode, Settings

CASES = json.loads((Path(__file__).parent.parent / "evals" / "cleanup_cases.json").read_text())
DEFAULTS = Settings()


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_cleanup_eval_case(case: dict[str, str]) -> None:
    result = clean(case["raw"], Mode(case["mode"]), DEFAULTS.glossary, DEFAULTS.snippets)
    assert result.clean == case["expected"]


def test_raw_is_always_kept() -> None:
    raw = "Um, the Mera Lion demo."
    result = clean(raw, Mode.DEFAULT, DEFAULTS.glossary)
    assert result.raw == raw
    assert result.clean == "The MERaLiON demo."


def test_every_change_is_explained() -> None:
    result = clean("Um, see the Mera Lion repo. Scratch that.", Mode.CHAT, DEFAULTS.glossary)
    rules = " | ".join(result.applied_rules)
    assert "fillers removed" in rules
    assert "backtrack: removed" in rules
    assert result.clean == ""


def test_glossary_rule_lists_original_and_replacement() -> None:
    result = clean("ship to git hub", Mode.DEV, [GlossaryEntry(heard="git hub", written="GitHub")])
    assert result.clean == "ship to GitHub"
    assert result.applied_rules == ["glossary: 'git hub' -> 'GitHub'"]


def test_glossary_does_not_match_inside_words() -> None:
    result = clean("The bonus is ready.", Mode.DEFAULT, [GlossaryEntry(heard="nus", written="NUS")])
    assert result.clean == "The bonus is ready."


def test_glossary_already_correct_records_no_rule() -> None:
    result = clean("NUS rocks", Mode.DEV, [GlossaryEntry(heard="nus", written="NUS")])
    assert result.applied_rules == []


def test_snippet_text_is_not_recased_or_cleaned() -> None:
    from utter.config import Snippet

    snip = Snippet(trigger="insert code", text="um.lower() , x")
    result = clean("insert code", Mode.DEFAULT, snippets=[snip])
    assert result.clean == "um.lower() , x"


def test_empty_input() -> None:
    assert clean("", Mode.DEFAULT).clean == ""
    assert clean("   ", Mode.EMAIL).clean == ""


def test_null_bytes_cannot_forge_placeholders() -> None:
    result = clean("a\x000\x00b", Mode.DEV)
    assert "\x00" not in result.clean
