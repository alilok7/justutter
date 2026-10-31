"""Microphone capture to a 16 kHz mono float32 buffer. Audio is kept in memory only."""

from __future__ import annotations

import logging
import threading
from typing import Any

import numpy as np
import sounddevice as sd

from utter.transcriber import SAMPLE_RATE

log = logging.getLogger(__name__)


def resample(audio: np.ndarray, src_rate: int, dst_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Linear-interpolation resample; adequate for speech recognition input."""
    if src_rate == dst_rate or audio.size == 0:
        same: np.ndarray = np.asarray(audio, dtype=np.float32)
        return same
    duration = audio.size / src_rate
    n_out = max(1, int(round(duration * dst_rate)))
    x_src = np.linspace(0.0, duration, num=audio.size, endpoint=False)
    x_dst = np.linspace(0.0, duration, num=n_out, endpoint=False)
    out: np.ndarray = np.interp(x_dst, x_src, audio).astype(np.float32)
    return out


def find_split(audio: np.ndarray, search_s: float = 3.0, frame_s: float = 0.03) -> int:
    """Index of the quietest 30 ms frame in the last ``search_s`` seconds: a gap between words,
    where a long recording can be cut into chunks without splitting a word."""
    n = audio.size
    frame = int(frame_s * SAMPLE_RATE)
    start = max(0, n - int(search_s * SAMPLE_RATE))
    count = (n - start) // frame
    if count == 0:
        return n
    frames = audio[start:start + count * frame].reshape(count, frame)
    quietest = int(np.argmin((frames.astype(np.float64) ** 2).mean(axis=1)))
    return start + quietest * frame + frame // 2


class Recorder:
    def __init__(self, device: int | None = None) -> None:
        self._device = device
        self._chunks: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._stream: Any = None
        self._rate = SAMPLE_RATE
        self.level = 0.0  # RMS of the latest audio block; drives the live waveform

    @property
    def recording(self) -> bool:
        return self._stream is not None

    def _callback(self, indata: np.ndarray, _frames: int, _time: Any, status: Any) -> None:
        if status:
            log.warning("audio status: %s", status)
        samples = indata[:, 0].copy()
        self.level = float(np.sqrt(np.mean(samples * samples))) if samples.size else 0.0
        with self._lock:
            self._chunks.append(samples)

    def _open(self, rate: int) -> Any:
        stream = sd.InputStream(samplerate=rate, channels=1, dtype="float32",
                                device=self._device, callback=self._callback)
        stream.start()
        return stream

    def start(self) -> None:
        if self._stream is not None:
            return
        with self._lock:
            self._chunks = []
        try:
            self._stream, self._rate = self._open(SAMPLE_RATE), SAMPLE_RATE
        except sd.PortAudioError as exc:
            # Some drivers refuse 16 kHz; record at the device rate and resample afterwards.
            info = sd.query_devices(self._device, kind="input")
            rate = int(info["default_samplerate"])
            log.info("16 kHz unsupported (%s); recording at %d Hz", exc, rate)
            self._stream, self._rate = self._open(rate), rate
        log.info("recording started at %d Hz", self._rate)

    def peek(self) -> np.ndarray:
        """Everything recorded so far, at 16 kHz, without stopping."""
        with self._lock:
            audio = np.concatenate(self._chunks) if self._chunks else np.zeros(0, np.float32)
        return resample(audio, self._rate)

    def stop(self) -> np.ndarray:
        stream, self._stream = self._stream, None
        if stream is None:
            return np.zeros(0, dtype=np.float32)
        try:
            stream.stop()
        finally:
            stream.close()
        with self._lock:
            audio = np.concatenate(self._chunks) if self._chunks else np.zeros(0, np.float32)
            self._chunks = []
        audio = resample(audio, self._rate)
        log.info("recording stopped: %.2fs", audio.size / SAMPLE_RATE)
        return audio
