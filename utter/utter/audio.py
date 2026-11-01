"""Microphone capture to a 16 kHz mono float32 buffer. Audio is kept in memory only."""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from collections.abc import Callable
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


StreamFactory = Callable[[int, Callable[..., None]], Any]  # (rate, callback) -> started stream


def rms(audio: np.ndarray) -> float:
    return float(np.sqrt(np.mean(audio.astype(np.float64) ** 2))) if audio.size else 0.0


class Recorder:
    """Records the microphone into memory.

    With ``warm=True`` the stream stays open between dictations and the last ``preroll_s``
    seconds are kept in a small rolling buffer, so pressing the hotkey also captures the moment
    just before it. That avoids clipping the first word while the mic wakes up. Nothing is
    written to disk either way.
    """

    def __init__(self, device: int | None = None, warm: bool = False, preroll_s: float = 0.4,
                 stream_factory: StreamFactory | None = None) -> None:
        self._device = device
        self.warm = warm
        self.preroll_s = preroll_s
        self._factory = stream_factory or self._open_portaudio
        self._chunks: list[np.ndarray] = []
        self._preroll: deque[np.ndarray] = deque()
        self._preroll_samples = 0
        self._lock = threading.Lock()
        self._stream: Any = None
        self._rate = SAMPLE_RATE
        self._recording = False
        self._started_at = 0.0
        self._last_block_at = 0.0
        self.level = 0.0  # RMS of the latest audio block; drives the live waveform

    @property
    def recording(self) -> bool:
        return self._recording

    def _callback(self, indata: np.ndarray, _frames: int, _time: Any, status: Any) -> None:
        if status:
            log.warning("audio status: %s", status)
        samples = indata[:, 0].copy()
        self.level = rms(samples)
        self._last_block_at = time.monotonic()
        with self._lock:
            if self._recording:
                self._chunks.append(samples)
            elif self.warm:
                self._preroll.append(samples)
                self._preroll_samples += samples.size
                excess = self._preroll_samples - int(self.preroll_s * self._rate)
                while excess > 0 and self._preroll:
                    oldest = self._preroll[0]
                    if oldest.size <= excess:
                        self._preroll.popleft()
                        drop = oldest.size
                    else:
                        self._preroll[0] = oldest[excess:]
                        drop = excess
                    self._preroll_samples -= drop
                    excess -= drop

    def _open_portaudio(self, rate: int, callback: Callable[..., None]) -> Any:
        stream = sd.InputStream(samplerate=rate, channels=1, dtype="float32",
                                device=self._device, callback=callback)
        stream.start()
        return stream

    def _close_stream(self) -> None:
        stream, self._stream = self._stream, None
        if stream is None:
            return
        try:
            stream.stop()
            stream.close()
        except sd.PortAudioError as exc:
            log.warning("closing audio stream failed: %s", exc)

    def _ensure_stream(self) -> None:
        if self._stream is not None:
            stalled = self.warm and time.monotonic() - self._last_block_at > 1.0
            if not stalled:
                return
            log.warning("warm microphone stopped delivering audio; reopening")
            self._close_stream()
        self._last_block_at = time.monotonic()
        try:
            self._stream, self._rate = self._factory(SAMPLE_RATE, self._callback), SAMPLE_RATE
        except sd.PortAudioError as exc:
            # Some drivers refuse 16 kHz; record at the device rate and resample afterwards.
            info = sd.query_devices(self._device, kind="input")
            rate = int(info["default_samplerate"])
            log.info("16 kHz unsupported (%s); recording at %d Hz", exc, rate)
            self._stream, self._rate = self._factory(rate, self._callback), rate

    def open(self) -> None:
        """Open the warm stream now (startup), so the first dictation isn't clipped."""
        self._ensure_stream()
        log.info("warm microphone open at %d Hz (pre-roll %.1fs)", self._rate, self.preroll_s)

    def close(self) -> None:
        self._recording = False
        self._close_stream()

    def start(self) -> None:
        if self._recording:
            return
        self._ensure_stream()
        with self._lock:
            self._chunks = list(self._preroll) if self.warm else []
            self._preroll.clear()
            self._preroll_samples = 0
            self._recording = True
        self._started_at = time.perf_counter()
        log.info("recording started at %d Hz", self._rate)

    def peek(self) -> np.ndarray:
        """Everything recorded so far, at 16 kHz, without stopping."""
        with self._lock:
            audio = np.concatenate(self._chunks) if self._chunks else np.zeros(0, np.float32)
        return resample(audio, self._rate)

    def stop(self) -> np.ndarray:
        if not self._recording:
            return np.zeros(0, dtype=np.float32)
        with self._lock:
            self._recording = False
            audio = np.concatenate(self._chunks) if self._chunks else np.zeros(0, np.float32)
            self._chunks = []
        if not self.warm:
            self._close_stream()
        held = time.perf_counter() - self._started_at
        audio = resample(audio, self._rate)
        log.info("recording stopped: %.2fs audio for %.2fs held (level %.4f)",
                 audio.size / SAMPLE_RATE, held, rms(audio))
        return audio
