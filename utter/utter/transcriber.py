"""Local speech-to-text with faster-whisper (CPU, int8). Never downloads at runtime."""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Sequence
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel
from pydantic import BaseModel

log = logging.getLogger(__name__)

SAMPLE_RATE = 16_000


class ModelMissingError(RuntimeError):
    pass


class TranscriptResult(BaseModel):
    text: str
    avg_logprob: float
    no_speech_prob: float
    audio_s: float
    latency_s: float
    confident: bool


def model_path(models_root: Path, name: str) -> Path:
    return models_root / name


def is_confident(text: str, avg_logprob: float, no_speech_prob: float,
                 no_speech_threshold: float, logprob_threshold: float) -> bool:
    return bool(text.strip()) and no_speech_prob <= no_speech_threshold and (
        avg_logprob >= logprob_threshold
    )


class Transcriber:
    def __init__(self, name: str, models_root: Path, beam_size: int = 1,
                 threads: int = 8) -> None:
        path = model_path(models_root, name)
        if not (path / "model.bin").exists():
            raise ModelMissingError(
                f"Model '{name}' not found in {path}. Run: python -m utter download-model"
            )
        started = time.perf_counter()
        self.name = name
        self.beam_size = beam_size
        self._model = WhisperModel(
            str(path), device="cpu", compute_type="int8",
            cpu_threads=min(threads, os.cpu_count() or threads), local_files_only=True,
        )
        log.info("loaded model %s in %.2fs", name, time.perf_counter() - started)

    def warmup(self) -> None:
        self.transcribe(np.zeros(SAMPLE_RATE, dtype=np.float32))

    def transcribe(self, audio: np.ndarray, hotwords: Sequence[str] = (),
                   no_speech_threshold: float = 0.6,
                   logprob_threshold: float = -1.0) -> TranscriptResult:
        if audio.dtype != np.float32 or audio.ndim != 1:
            raise ValueError("audio must be 1-D float32 mono at 16 kHz")
        started = time.perf_counter()
        segments, _info = self._model.transcribe(
            audio,
            language="en",
            beam_size=self.beam_size,
            temperature=0.0,  # no retry loop: low confidence is refused instead (M1)
            vad_filter=True,
            condition_on_previous_text=False,
            without_timestamps=True,
            hotwords=", ".join(hotwords) if hotwords else None,
        )
        segs = list(segments)
        latency = time.perf_counter() - started
        text = " ".join(s.text.strip() for s in segs).strip()
        if segs:
            avg_logprob = float(np.mean([s.avg_logprob for s in segs]))
            no_speech = float(np.mean([s.no_speech_prob for s in segs]))
        else:
            avg_logprob, no_speech = -10.0, 1.0
        result = TranscriptResult(
            text=text,
            avg_logprob=avg_logprob,
            no_speech_prob=no_speech,
            audio_s=len(audio) / SAMPLE_RATE,
            latency_s=latency,
            confident=is_confident(text, avg_logprob, no_speech, no_speech_threshold,
                                   logprob_threshold),
        )
        log.info("transcribed %.1fs audio in %.2fs (logprob %.2f, no_speech %.2f, confident %s)",
                 result.audio_s, latency, avg_logprob, no_speech, result.confident)
        return result
