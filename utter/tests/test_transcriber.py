from pathlib import Path

import pytest

from utter.config import models_dir
from utter.evaluate import normalise, word_error_rate
from utter.transcriber import ModelMissingError, Transcriber, is_confident


def test_missing_model_gives_actionable_error(tmp_path: Path) -> None:
    with pytest.raises(ModelMissingError, match="download-model"):
        Transcriber("base.en", tmp_path)


@pytest.mark.parametrize(
    ("text", "logprob", "no_speech", "expected"),
    [
        ("hello there", -0.3, 0.1, True),
        ("", -0.3, 0.1, False),
        ("   ", -0.3, 0.1, False),
        ("hello", -0.3, 0.9, False),
        ("hello", -1.5, 0.1, False),
    ],
)
def test_confidence_gate(text: str, logprob: float, no_speech: float, expected: bool) -> None:
    assert is_confident(text, logprob, no_speech, 0.6, -1.0) is expected


def test_wer() -> None:
    assert word_error_rate("the cat sat", "the cat sat") == 0.0
    assert word_error_rate("the cat sat", "the dog sat") == pytest.approx(1 / 3)
    assert word_error_rate("the cat sat", "The, cat sat!") == 0.0
    assert word_error_rate("", "") == 0.0
    assert normalise("Git-Hub's API") == ["git", "hub's", "api"]


needs_model = pytest.mark.skipif(
    not (models_dir() / "base.en" / "model.bin").exists(), reason="base.en model not downloaded"
)


@needs_model
def test_silence_is_not_confident() -> None:
    import numpy as np

    t = Transcriber("base.en", models_dir())
    result = t.transcribe(np.zeros(16000 * 2, dtype=np.float32))
    assert result.confident is False


def test_vad_retry_only_for_audible_audio() -> None:
    import numpy as np

    from utter.transcriber import needs_vad_retry

    assert not needs_vad_retry(np.zeros(16000, dtype=np.float32))
    assert not needs_vad_retry(np.full(16000, 0.001, dtype=np.float32))
    assert needs_vad_retry(np.full(16000, 0.01, dtype=np.float32))


@needs_model
def test_quiet_speech_is_still_transcribed() -> None:
    from utter.evaluate import EVALS_DIR, read_wav, word_error_rate

    clip = EVALS_DIR / "audio" / "s01-plain.wav"
    if not clip.exists():
        pytest.skip("eval audio missing")
    t = Transcriber("base.en", models_dir())
    quiet = read_wav(clip) * 0.02  # roughly a soft voice far from a laptop mic
    result = t.transcribe(quiet.astype("float32"))
    assert word_error_rate("hey team the design review is moved to tomorrow afternoon",
                           result.text) < 0.2


@needs_model
def test_rejects_wrong_audio_format() -> None:
    import numpy as np

    t = Transcriber("base.en", models_dir())
    with pytest.raises(ValueError):
        t.transcribe(np.zeros((2, 100), dtype=np.float32))
