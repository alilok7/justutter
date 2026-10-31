import numpy as np
import pytest

from utter.audio import find_split
from utter.config import models_dir
from utter.evaluate import EVALS_DIR, load_cases, read_wav, word_error_rate
from utter.transcriber import SAMPLE_RATE, Transcriber


def test_find_split_picks_the_pause() -> None:
    rng = np.random.default_rng(0)
    speech = rng.normal(0, 0.3, SAMPLE_RATE * 5).astype(np.float32)
    pause_at = int(SAMPLE_RATE * 3.5)
    speech[pause_at:pause_at + 2400] = 0.0  # 150 ms of silence inside the search window
    cut = find_split(speech)
    assert pause_at <= cut <= pause_at + 2400


def test_find_split_short_audio_returns_end() -> None:
    audio = np.zeros(100, dtype=np.float32)
    assert find_split(audio) == 100


needs_audio = pytest.mark.skipif(
    not (models_dir() / "base.en" / "model.bin").exists()
    or not (EVALS_DIR / "audio" / "s01-plain.wav").exists(),
    reason="model or eval audio missing",
)


@needs_audio
def test_chunked_transcription_matches_whole() -> None:
    """A long recording cut at pauses into ~8 s chunks reads the same as one pass."""
    cases = load_cases()
    gap = np.zeros(int(SAMPLE_RATE * 0.4), dtype=np.float32)
    parts = []
    for c in cases:
        parts += [read_wav(EVALS_DIR / "audio" / f"{c.id}.wav"), gap]
    audio = np.concatenate(parts)
    reference = " ".join(c.reference for c in cases)

    t = Transcriber("base.en", models_dir())
    chunk = 8 * SAMPLE_RATE
    texts, consumed = [], 0
    while audio.size - consumed >= chunk:
        cut = consumed + find_split(audio[consumed:consumed + chunk])
        texts.append(t.transcribe(audio[consumed:cut]).text)
        consumed = cut
    texts.append(t.transcribe(audio[consumed:]).text)

    assert len(texts) >= 4
    assert word_error_rate(reference, " ".join(texts)) < 0.15
