"""Warm microphone with pre-roll (P1), tested with a fake audio stream."""

from collections.abc import Callable
from typing import Any

import numpy as np

from utter.audio import Recorder, rms
from utter.transcriber import SAMPLE_RATE


class FakeStream:
    def __init__(self, callback: Callable[..., None]) -> None:
        self.callback = callback
        self.closed = False

    def feed(self, value: float, seconds: float) -> None:
        block = np.full((int(seconds * SAMPLE_RATE), 1), value, dtype=np.float32)
        self.callback(block, block.shape[0], None, None)

    def stop(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True


class Factory:
    def __init__(self) -> None:
        self.streams: list[FakeStream] = []

    def __call__(self, rate: int, callback: Callable[..., None]) -> Any:
        self.streams.append(FakeStream(callback))
        return self.streams[-1]


def test_warm_recorder_prepends_preroll() -> None:
    factory = Factory()
    rec = Recorder(warm=True, preroll_s=0.4, stream_factory=factory)
    rec.open()
    stream = factory.streams[0]
    stream.feed(0.1, 1.0)   # old audio: only the last 0.4 s may be kept
    stream.feed(0.2, 0.3)   # the moment just before the hotkey
    rec.start()
    stream.feed(0.5, 1.0)   # speech while holding the keys
    audio = rec.stop()
    assert 1.3 * SAMPLE_RATE <= audio.size <= 1.45 * SAMPLE_RATE
    assert audio[-1] == np.float32(0.5)
    assert np.float32(0.2) in audio  # pre-roll captured
    assert len(factory.streams) == 1 and not stream.closed  # stays warm between dictations


def test_preroll_does_not_leak_into_the_next_dictation() -> None:
    factory = Factory()
    rec = Recorder(warm=True, preroll_s=0.4, stream_factory=factory)
    rec.open()
    stream = factory.streams[0]
    rec.start()
    stream.feed(0.5, 1.0)
    rec.stop()
    stream.feed(0.3, 0.2)
    rec.start()
    stream.feed(0.6, 0.5)
    audio = rec.stop()
    assert np.float32(0.5) not in audio
    assert audio.size <= int(0.75 * SAMPLE_RATE)


def test_cold_recorder_opens_and_closes_per_dictation() -> None:
    factory = Factory()
    rec = Recorder(warm=False, stream_factory=factory)
    rec.start()
    factory.streams[0].feed(0.5, 0.5)
    audio = rec.stop()
    assert audio.size == int(0.5 * SAMPLE_RATE)
    assert factory.streams[0].closed


def test_stalled_warm_stream_is_reopened() -> None:
    factory = Factory()
    rec = Recorder(warm=True, stream_factory=factory)
    rec.open()
    rec._last_block_at -= 5.0  # no audio for 5 s: device went away or driver hung
    rec.start()
    assert len(factory.streams) == 2
    assert factory.streams[0].closed


def test_stop_without_start_is_safe() -> None:
    assert Recorder(warm=True, stream_factory=Factory()).stop().size == 0


def test_rms() -> None:
    assert rms(np.zeros(10, dtype=np.float32)) == 0.0
    assert abs(rms(np.full(10, 0.5, dtype=np.float32)) - 0.5) < 1e-6
    assert rms(np.zeros(0, dtype=np.float32)) == 0.0
