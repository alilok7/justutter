"""Deterministic, explainable clean-up of a raw transcript.

Every change is recorded in ``CleanResult.applied_rules`` and the raw text is always kept, so the
user can see why the output differs and undo it.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from pydantic import BaseModel

from utter.config import GlossaryEntry, Mode, Snippet


class CleanResult(BaseModel):
    raw: str
    clean: str
    mode: Mode
    applied_rules: list[str]


_FILLERS = r"(?:u+m+|u+h+m*|e+r+m+|er|h+m+|m{2,})"
_FILLER_RE = re.compile(rf"[ \t]*,?[ \t]*\b{_FILLERS}\b[ \t]*,?", re.IGNORECASE)

_PARAGRAPH_RE = re.compile(
    r"[ \t]*\b(?:start a new paragraph|new paragraph)\b[ \t]*[,.;:!?]?[ \t]*", re.IGNORECASE
)
_LINE_RE = re.compile(
    r"[ \t]*\b(?:new line|next line|line break|skip a line)\b[ \t]*[,.;:!?]?[ \t]*",
    re.IGNORECASE,
)
_BACKTRACK_RE = re.compile(r"[ \t]*[,;]?[ \t]*\bscratch that\b[ \t]*[,.;:!?]?[ \t]*",
                           re.IGNORECASE)
_BOUNDARY_CHARS = ".!?\n,;"

_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
}
# A list marker must be followed by punctuation ("one, shoes" / "1. shoes"), which keeps
# ordinary prose like "two or three ideas" and decimals like "1.5" out of lists.
_MARKER_RE = re.compile(
    r"(?:^|(?<=[\s.,;:!?]))(?:number\s+)?("
    + "|".join(sorted(_NUMBER_WORDS, key=len, reverse=True))
    + r"|\d{1,2})\s*[.,:)]\s+",
    re.IGNORECASE,
)
_BULLET_RE = re.compile(r"[ \t]*\b(?:bullet point|bullet)\b[ \t]*[,.:;]?[ \t]*", re.IGNORECASE)
_LIST_LINE_RE = re.compile(r"(?m)^(?:\d{1,2}\.|-) ")

# Placeholders protect inserted text (snippets, glossary terms) from later casing/tidy steps.
_PH = "\x00{}\x00"
_PH_RE = re.compile("\x00(\\d+)\x00")


def _flexible(phrase: str) -> re.Pattern[str]:
    """Match a phrase case-insensitively, tolerating spaces, dots or hyphens between its words."""
    words = [w for w in re.split(r"[\s.\-]+", phrase.strip()) if w]
    body = r"[\s.\-]*".join(re.escape(w) for w in words)
    if all(len(w) == 1 for w in words):
        # Spelled-out acronym: absorb the dot of "N.U.S." unless it ends the sentence.
        body += r"(?:\.(?=\s+\w))?"
    return re.compile(r"(?<!\w)" + body + r"(?!\w)", re.IGNORECASE)


def _apply_snippets(text: str, snippets: Sequence[Snippet], protected: list[str],
                    rules: list[str]) -> str:
    for snip in snippets:
        pattern = _flexible(snip.trigger)

        def repl(_m: re.Match[str], s: Snippet = snip) -> str:
            protected.append(s.text)
            rules.append(f"snippet: '{s.trigger}'")
            return _PH.format(len(protected) - 1)

        text = pattern.sub(repl, text)
    return text


def _apply_commands(text: str, rules: list[str]) -> str:
    text, n_para = _PARAGRAPH_RE.subn("\n\n", text)
    if n_para:
        rules.append(f"command: new paragraph x{n_para}")
    text, n_line = _LINE_RE.subn("\n", text)
    if n_line:
        rules.append(f"command: new line x{n_line}")
    return text


def _marker_value(word: str) -> int:
    return int(word) if word.isdigit() else _NUMBER_WORDS[word.lower()]


def _capitalise(item: str) -> str:
    return item[:1].upper() + item[1:]


def _apply_numbered_list(text: str, rules: list[str]) -> str:
    taken: list[re.Match[str]] = []
    for m in _MARKER_RE.finditer(text):
        if _marker_value(m.group(1)) == len(taken) + 1:
            taken.append(m)
    if len(taken) < 2:
        return text
    intro = text[: taken[0].start()].strip().rstrip(",;:.-").strip()
    items: list[str] = []
    trailing = ""
    for i, m in enumerate(taken):
        end = taken[i + 1].start() if i + 1 < len(taken) else len(text)
        item = text[m.end():end].strip()
        if i == len(taken) - 1:  # text after the last item's sentence is not part of the list
            stop = re.search(r"[.!?]\s+(?=\S)", item)
            if stop:
                trailing, item = item[stop.end():].strip(), item[: stop.start()]
        item = item.strip().rstrip(",;:.").strip()
        if item:
            items.append(_capitalise(item))
    if len(items) < 2:
        return text
    lines = [f"{n}. {item}" for n, item in enumerate(items, 1)]
    head = f"{intro}{'' if intro[-1:] in (':', '?') else ':'}\n" if intro else ""
    rules.append(f"list: {len(items)} numbered items")
    return head + "\n".join(lines) + (f"\n{trailing}" if trailing else "")


def _apply_bullets(text: str, rules: list[str]) -> str:
    text, count = _BULLET_RE.subn("\n- ", text)
    if not count:
        return text
    lines = []
    for line in text.split("\n"):
        if line.startswith("- "):
            line = "- " + _capitalise(line[2:].strip().rstrip(",;.").strip())
        lines.append(line.rstrip(" ,;:") if not line.startswith("- ") else line)
    rules.append(f"list: {count} bullet items")
    return "\n".join(lines).strip("\n")


def _apply_lists(text: str, rules: list[str]) -> str:
    text = _apply_bullets(text, rules)
    return "\n\n".join(block if has_list(block) else _apply_numbered_list(block, rules)
                       for block in text.split("\n\n"))


def has_list(text: str) -> bool:
    return bool(_LIST_LINE_RE.search(text))


def _apply_backtrack(text: str, rules: list[str]) -> str:
    while (m := _BACKTRACK_RE.search(text)) is not None:
        before, after = text[: m.start()].rstrip(), text[m.end():]
        # "Cookies. Scratch that." refers to the whole previous sentence, so skip its own end mark.
        search_in = before[:-1] if before and before[-1] in _BOUNDARY_CHARS else before
        cut = max(search_in.rfind(c) for c in _BOUNDARY_CHARS)
        kept = before[: cut + 1] if cut >= 0 else ""
        removed = before[cut + 1:].strip()
        rules.append(
            f"backtrack: removed '{removed}'" if removed else "backtrack: nothing to remove"
        )
        joiner = " " if kept and not kept.endswith("\n") and after else ""
        text = kept + joiner + after
    return text


def _apply_fillers(text: str, rules: list[str]) -> str:
    found: list[str] = []

    def repl(m: re.Match[str]) -> str:
        found.append(m.group(0).strip(" \t,."))
        return " "

    text = _FILLER_RE.sub(repl, text)
    if found:
        rules.append("fillers removed: " + ", ".join(f"'{f}'" for f in found))
    return text


def _apply_glossary(text: str, glossary: Sequence[GlossaryEntry], protected: list[str],
                    rules: list[str]) -> str:
    # Longest phrases first so "nus hackers" wins over "n u s".
    for entry in sorted(glossary, key=lambda e: len(e.heard), reverse=True):
        pattern = _flexible(entry.heard)

        def repl(m: re.Match[str], e: GlossaryEntry = entry) -> str:
            if m.group(0) != e.written:
                rules.append(f"glossary: '{m.group(0)}' -> '{e.written}'")
            protected.append(e.written)
            return _PH.format(len(protected) - 1)

        text = pattern.sub(repl, text)
    return text


def _tidy(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" +([,.;:!?])", r"\1", text)
    text = re.sub(r"([,;:])(?:\s*[,;:])+", r"\1", text)
    text = re.sub(r"[,;:]+([.!?])", r"\1", text)
    text = re.sub(r"(^|\n)[ ,.;:]+", r"\1", text)
    text = re.sub(r"([.!?])[,;]", r"\1", text)
    text = re.sub(r"([,;])(?=[A-Za-z])", r"\1 ", text)
    return text.strip(" \t\n,;")


def _sentence_case(text: str) -> str:
    def up(m: re.Match[str]) -> str:
        return m.group(1) + m.group(2).upper()

    return re.sub(r"(^|[.!?][ \n]+|\n)([a-z])", up, text)


def _apply_mode(text: str, mode: Mode, rules: list[str]) -> str:
    if mode is Mode.DEV:
        if text.endswith(".") and not text.endswith(".."):
            rules.append("mode dev: removed trailing period")
            text = text[:-1]
        return text
    text = _sentence_case(text)
    if mode is Mode.CHAT and text.endswith(".") and not text.endswith(".."):
        rules.append("mode chat: removed trailing period")
        text = text[:-1]
    elif mode is Mode.EMAIL and text and text[-1] not in ".!?:\x00" \
            and not _LIST_LINE_RE.match(text.rsplit("\n", 1)[-1]):
        rules.append("mode email: added final period")
        text += "."
    return text


def format_for_mode(text: str, mode: Mode,
                    keep_endings: Sequence[str] = ()) -> tuple[str, list[str]]:
    """Apply per-mode formatting once to the finished text (after joining pieces and AI polish).

    Text that ends with one of ``keep_endings`` (snippet texts) keeps its ending as written.
    """
    rules: list[str] = []
    text = text.strip()
    if any(e.strip() and text.endswith(e.strip()) for e in keep_endings):
        return (text if mode is Mode.DEV else _sentence_case(text)), rules
    return _apply_mode(text, mode, rules), rules


def clean(raw: str, mode: Mode, glossary: Sequence[GlossaryEntry] = (),
          snippets: Sequence[Snippet] = (), apply_mode: bool = True) -> CleanResult:
    """Clean a transcript. With ``apply_mode=False`` (one piece of a longer dictation) the
    mode's end-of-text rules are left for ``format_for_mode`` so pieces join correctly."""
    rules: list[str] = []
    protected: list[str] = []
    text = " ".join(raw.replace("\x00", "").split(" ")).strip()
    text = _apply_snippets(text, snippets, protected, rules)
    text = _apply_commands(text, rules)
    text = _apply_lists(text, rules)
    text = _apply_backtrack(text, rules)
    text = _apply_fillers(text, rules)
    text = _apply_glossary(text, glossary, protected, rules)
    text = _tidy(text)
    if apply_mode:
        text = _apply_mode(text, mode, rules)
    elif mode is not Mode.DEV:
        text = _sentence_case(text)
    text = _PH_RE.sub(lambda m: protected[int(m.group(1))], text)
    return CleanResult(raw=raw, clean=text.strip(), mode=mode, applied_rules=rules)
