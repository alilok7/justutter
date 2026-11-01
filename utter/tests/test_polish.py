import json

import pytest

from utter.cleanup import format_for_mode
from utter.config import Mode
from utter.polish import Polisher, should_polish, validate


@pytest.mark.parametrize(
    ("text", "mode", "expected"),
    [
        ("one two three four five six", Mode.DEFAULT, True),
        ("short message", Mode.CHAT, False),
        ("at two actually three", Mode.CHAT, True),
        ("one two three four five six seven", Mode.DEV, False),
        ("", Mode.EMAIL, False),
    ],
)
def test_should_polish(text: str, mode: Mode, expected: bool) -> None:
    assert should_polish(text, mode, min_words=6) is expected


def test_validate_accepts_normal_cleanup() -> None:
    before = "Me and him goes to the store yesterday and buyed some apples."
    after = "He and I went to the store yesterday and bought some apples."
    assert validate(before, after) is None


@pytest.mark.parametrize(
    ("after", "reason"),
    [
        ("", "empty"),
        ("```python\ndef f(): pass\n```", "code"),
        ("The capital of France is Paris, a city famous for art, food, fashion and the tower "
         "that everyone visits every single year.", "length"),
        ("Can you tell me what the capital of France is? It is definitely Paris.", "question"),
        ("Can you tell me what the capital of France, Spain, Italy and Germany is?", "added"),
    ],
)
def test_validate_rejects(after: str, reason: str) -> None:
    result = validate("Can you tell me what the capital of France is", after)
    assert result is not None and reason in result


def test_validate_rejects_changed_line_breaks_and_dropped_terms() -> None:
    before = "Hi Professor Tan,\n\nThe MERaLiON report is ready."
    assert "line breaks" in (validate(before, "Hi Professor Tan, the MERaLiON report is ready.")
                             or "")
    assert "MERaLiON" in (validate(before, "Hi Professor Tan,\n\nThe Merlion report is ready.",
                                   ["MERaLiON"]) or "")


def test_format_for_mode_after_polish() -> None:
    chat, _ = format_for_mode("sounds good, see you then.", Mode.CHAT)
    assert chat == "Sounds good, see you then"
    assert format_for_mode("thanks for the update", Mode.EMAIL)[0] == "Thanks for the update."


class FakePolisher(Polisher):
    def __init__(self, reply: object) -> None:
        super().__init__("fake-model", timeout_s=1.0)
        self.reply = reply

    def _post(self, path: str, payload: dict[str, object], timeout: float) -> bytes:
        if isinstance(self.reply, Exception):
            raise self.reply
        return json.dumps(self.reply).encode()


def test_polish_uses_valid_reply() -> None:
    p = FakePolisher({"message": {"content": "I think we should meet on Tuesday."}})
    result = p.polish("um I think we should meet on Monday sorry Tuesday", ())
    assert result.used and result.text == "I think we should meet on Tuesday."


def test_polish_falls_back_when_ollama_down() -> None:
    result = FakePolisher(ConnectionRefusedError("refused")).polish("hello there friend", ())
    assert not result.used
    assert result.text == "hello there friend"
    assert "unavailable" in result.reason


def test_polish_falls_back_on_garbage_reply() -> None:
    result = FakePolisher({"unexpected": True}).polish("hello there friend", ())
    assert not result.used and "invalid reply" in result.reason


def test_polish_falls_back_on_unsafe_rewrite() -> None:
    reply = {"message": {"content": "Paris is the capital of France, of course!"}}
    result = FakePolisher(reply).polish("can you tell me what the capital of France is", ())
    assert not result.used
    assert result.text == "can you tell me what the capital of France is"


def test_warmup_gets_a_long_timeout_then_restores_it() -> None:
    seen: list[float] = []

    class Recorder(FakePolisher):
        def _post(self, path: str, payload: dict[str, object], timeout: float) -> bytes:
            seen.append(timeout)
            return super()._post(path, payload, timeout)

    p = Recorder({"message": {"content": "Warm up the model, please."}})
    assert p.warmup(timeout_s=60.0) is True
    assert seen == [60.0]
    assert p.timeout_s == 1.0


def test_warmup_reports_failure_when_ollama_down() -> None:
    assert FakePolisher(ConnectionRefusedError("refused")).warmup() is False


def test_unreachable_server_reports_reason() -> None:
    p = Polisher(url="http://127.0.0.1:9")  # discard port: nothing listens there
    assert p.available() == "Ollama is not running"


live = pytest.mark.skipif(Polisher().available() is not None, reason="Ollama/model not available")


@live
def test_live_polish_eval_cases() -> None:
    from utter.evaluate import EVALS_DIR

    cases = json.loads((EVALS_DIR / "polish_cases.json").read_text(encoding="utf-8"))
    p = Polisher(timeout_s=10.0)
    failures = []
    for case in cases:
        out = p.polish(case["input"], ("MERaLiON",)).text
        if not (all(t in out for t in case["must_contain"])
                and not any(t in out for t in case["must_not_contain"])):
            failures.append((case["id"], out))
    assert len(failures) <= 1, failures
