from pathlib import Path

from utter.personal import (
    MAX_STYLE_EXAMPLES,
    PersonalMemory,
    StyleExample,
    add_style_example,
    candidate_terms,
    hotwords,
    load_memory,
    propose_corrections,
    record_dictation,
    save_memory,
)


def test_candidate_terms() -> None:
    text = ("Yesterday we met Priya at NUS to test MERaLiON and GPT4 on paleontological data. "
            "I left.")
    terms = candidate_terms(text)
    assert {"Priya", "NUS", "MERaLiON", "GPT4", "paleontological"} <= set(terms)
    assert "Yesterday" not in terms  # sentence start, not a name
    assert "I" not in terms


def test_vocab_needs_two_sightings_and_glossary_comes_first() -> None:
    m = PersonalMemory()
    record_dictation(m, "We studied the Pterodactylus.")
    assert hotwords(m, ["NUS"]) == ["NUS"]
    record_dictation(m, "Another Pterodactylus bone.")
    assert hotwords(m, ["NUS"]) == ["NUS", "Pterodactylus"]


def test_hotwords_are_capped() -> None:
    m = PersonalMemory(vocab={f"Term{i}": 5 for i in range(100)})
    assert len(hotwords(m, ["A", "B"], limit=40)) == 40


def test_word_correction_is_proposed() -> None:
    p = propose_corrections("The pterodactylous fossil was found.",
                            "The Pterodactylus fossil was found.")
    assert p.pairs == [("pterodactylous", "Pterodactylus")]
    assert p.style_example is None


def test_case_only_correction() -> None:
    p = propose_corrections("Meet me at nus tomorrow.", "Meet me at NUS tomorrow.")
    assert p.pairs == [("nus", "NUS")]


def test_multi_word_correction() -> None:
    p = propose_corrections("We used mera lion today.", "We used MERaLiON today.")
    assert p.pairs == [("mera lion", "MERaLiON")]


def test_rephrase_becomes_style_example() -> None:
    p = propose_corrections("Hi, can you send the report?",
                            "Hey Sam, could you please send over the quarterly report when free?")
    assert p.style_example is not None
    assert p.style_example.after.startswith("Hey Sam")


def test_identical_text_proposes_nothing() -> None:
    p = propose_corrections("All good here.", "All good here.")
    assert p.pairs == [] and p.style_example is None


def test_style_examples_are_bounded() -> None:
    m = PersonalMemory()
    for i in range(MAX_STYLE_EXAMPLES + 3):
        add_style_example(m, StyleExample(before=str(i), after=str(i)))
    assert len(m.style_examples) == MAX_STYLE_EXAMPLES
    assert m.style_examples[-1].before == str(MAX_STYLE_EXAMPLES + 2)


def test_memory_roundtrip_and_corrupt_file(tmp_path: Path) -> None:
    path = tmp_path / "personal.json"
    m = PersonalMemory(vocab={"NUS": 3}, corrections_learned=2)
    save_memory(m, path)
    assert load_memory(path) == m
    path.write_text("{broken", encoding="utf-8")
    assert load_memory(path) == PersonalMemory()
    assert (tmp_path / "personal.invalid.json").exists()


def test_polisher_includes_style_examples() -> None:
    from utter.polish import Polisher

    p = Polisher()
    p.extra_shots = [("hi can u send it", "Hey, could you send it over?")]
    msgs = p._messages("test")
    assert {"role": "assistant", "content": "Hey, could you send it over?"} in msgs
    assert msgs[-1]["content"] == "<dictation>test</dictation>"
