"""Long dictations are processed in pieces; joining them must read like one dictation (M3)."""

from utter.app import CHUNK_S, Piece, assemble_pieces
from utter.cleanup import clean, format_for_mode
from utter.config import Mode, Settings

SNIPPETS = [s.text for s in Settings().snippets]


def piece(raw: str, mode: Mode) -> Piece:
    cleaned = clean(raw, mode, apply_mode=False)
    return Piece(raw=raw, text=cleaned.clean, rules=cleaned.applied_rules)


def test_chunk_length_is_short_enough_to_keep_release_fast() -> None:
    assert CHUNK_S <= 12.0


def test_pieces_keep_their_inner_punctuation_in_chat_mode() -> None:
    parts = [piece("Hey team, the demo went well.", Mode.CHAT),
             piece("We should push tonight.", Mode.CHAT)]
    raw, final, rules = assemble_pieces(parts, Mode.CHAT, SNIPPETS)
    assert final == "Hey team, the demo went well. We should push tonight"
    assert raw == "Hey team, the demo went well. We should push tonight."
    assert "mode chat: removed trailing period" in rules


def test_email_gets_one_final_period_after_joining() -> None:
    parts = [piece("hi professor tan.", Mode.EMAIL), piece("the report is ready", Mode.EMAIL)]
    _, final, _ = assemble_pieces(parts, Mode.EMAIL, SNIPPETS)
    assert final == "Hi professor tan. The report is ready."


def test_dev_mode_never_recases_pieces() -> None:
    parts = [piece("fix the parser.", Mode.DEV), piece("then run pytest.", Mode.DEV)]
    _, final, _ = assemble_pieces(parts, Mode.DEV, SNIPPETS)
    assert final == "fix the parser. then run pytest"


def test_missing_or_empty_pieces_are_skipped() -> None:
    parts = [piece("First part.", Mode.DEFAULT), None, Piece(raw="", text="", rules=[]),
             piece("Last part.", Mode.DEFAULT)]
    raw, final, _ = assemble_pieces(parts, Mode.DEFAULT, SNIPPETS)
    assert final == "First part. Last part."
    assert raw == "First part. Last part."


def test_nothing_heard() -> None:
    assert assemble_pieces([None], Mode.DEFAULT, SNIPPETS) == ("", "", [])


def test_snippet_ending_is_not_given_an_extra_period() -> None:
    text = "See you then. Best regards,\nThe Utter team"
    assert format_for_mode(text, Mode.EMAIL, SNIPPETS)[0] == text


def test_single_piece_matches_whole_clean() -> None:
    for mode in Mode:
        raw = "um so the meeting is at three. new line. thanks"
        _, final, _ = assemble_pieces([piece(raw, mode)], mode, SNIPPETS)
        assert final == clean(raw, mode).clean
