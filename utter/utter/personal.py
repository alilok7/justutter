"""Personal memory: vocabulary hints, learned corrections and style examples (local JSON only)."""

from __future__ import annotations

import difflib
import logging
import re
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

log = logging.getLogger(__name__)

MAX_HOTWORDS = 40
MIN_TERM_COUNT = 2
MAX_STYLE_EXAMPLES = 5
_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9'\-]*[A-Za-z0-9]|[A-Za-z]")
_SENTENCE_START = re.compile(r"(?:^|[.!?]\s+|\n)$")


class StyleExample(BaseModel):
    before: str
    after: str


class PersonalMemory(BaseModel):
    vocab: dict[str, int] = Field(default_factory=dict)
    style_examples: list[StyleExample] = Field(default_factory=list)
    corrections_learned: int = 0


# Everyday words Whisper capitalises mid-sentence; biasing towards them only adds noise.
_EVERYDAY = frozenset({
    "i", "i'm", "i've", "i'll", "i'd", "ok", "okay", "you", "so", "please", "yes", "no", "yeah",
    "hey", "hi", "hello", "thanks", "thank", "also", "and", "but", "then", "the", "a", "an", "it",
    "its", "this", "that", "we", "they", "he", "she", "my", "your", "our", "oh", "well", "right",
    "sure", "just", "like", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday",
    "sunday",
})


def is_learnable(word: str) -> bool:
    """Names, acronyms and coded terms (MERaLiON, GPT4, Pterodactylus), not everyday words."""
    if len(word) < 2 or word.lower() in _EVERYDAY or "'" in word:
        return False
    mixed = any(c.isupper() for c in word[1:]) or any(c.isdigit() for c in word)
    return mixed or word[0].isupper()


def candidate_terms(text: str) -> list[str]:
    """Capitalised (not sentence-initial), mixed-case or digit-bearing terms worth learning."""
    found: list[str] = []
    for m in _TOKEN.finditer(text):
        word = m.group(0)
        mixed = any(c.isupper() for c in word[1:]) or any(c.isdigit() for c in word)
        at_start = bool(_SENTENCE_START.search(text[: m.start()]))
        if is_learnable(word) and (mixed or not at_start):
            found.append(word)
    return found


def hotwords(memory: PersonalMemory, glossary_terms: Sequence[str],
             limit: int = MAX_HOTWORDS) -> list[str]:
    terms = list(dict.fromkeys(glossary_terms))
    frequent = sorted((t for t, n in memory.vocab.items()
                       if n >= MIN_TERM_COUNT and is_learnable(t)),
                      key=lambda t: (-memory.vocab[t], t))
    for term in frequent:
        if term not in terms:
            terms.append(term)
    return terms[:limit]


def record_dictation(memory: PersonalMemory, text: str) -> None:
    for term in candidate_terms(text):
        memory.vocab[term] = memory.vocab.get(term, 0) + 1


class CorrectionProposal(BaseModel):
    pairs: list[tuple[str, str]]
    style_example: StyleExample | None


def propose_corrections(inserted: str, corrected: str, max_span: int = 4) -> CorrectionProposal:
    """Word-diff what Utter inserted against the user's fixed version."""
    a, b = inserted.split(), corrected.split()
    matcher = difflib.SequenceMatcher(a=[w.lower() for w in a], b=[w.lower() for w in b],
                                      autojunk=False)
    pairs: list[tuple[str, str]] = []
    rephrased = False
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            # Case-only changes ("pterodactylus" -> "Pterodactylus") are corrections too.
            for x, y in zip(a[i1:i2], b[j1:j2], strict=True):
                if x != y:
                    pairs.append((x.strip(".,!?;:"), y.strip(".,!?;:")))
            continue
        old, new = " ".join(a[i1:i2]), " ".join(b[j1:j2])
        if op == "replace" and i2 - i1 <= max_span and j2 - j1 <= max_span:
            heard, written = old.strip(".,!?;:"), new.strip(".,!?;:")
            if heard and written and heard != written:
                pairs.append((heard, written))
        else:
            rephrased = True
    pairs = list(dict.fromkeys(p for p in pairs if p[0] and p[1] and p[0] != p[1]))
    style = StyleExample(before=inserted, after=corrected) if rephrased else None
    return CorrectionProposal(pairs=pairs, style_example=style)


def add_style_example(memory: PersonalMemory, example: StyleExample) -> None:
    memory.style_examples = [*memory.style_examples, example][-MAX_STYLE_EXAMPLES:]


def load_memory(path: Path) -> PersonalMemory:
    if not path.exists():
        return PersonalMemory()
    try:
        return PersonalMemory.model_validate_json(path.read_text(encoding="utf-8"))
    except (ValidationError, UnicodeDecodeError) as exc:
        backup = path.with_suffix(".invalid.json")
        path.replace(backup)
        log.error("personal memory invalid; moved to %s: %s", backup, exc)
        return PersonalMemory()


def save_memory(memory: PersonalMemory, path: Path) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(memory.model_dump_json(indent=1), encoding="utf-8")
    tmp.replace(path)
