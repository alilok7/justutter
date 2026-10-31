"""Recent dictations (memory only, text only) and weekly word stats (numbers only, on disk)."""

from __future__ import annotations

import logging
import statistics
from collections import deque
from datetime import date, datetime
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from utter.config import Mode

log = logging.getLogger(__name__)


class Dictation(BaseModel):
    at: datetime
    app: str
    mode: Mode
    raw: str
    clean: str
    rules: list[str]
    latency_s: float
    action: str


class History:
    def __init__(self, size: int = 20) -> None:
        self._items: deque[Dictation] = deque(maxlen=size)

    def add(self, item: Dictation) -> None:
        self._items.append(item)

    def last(self) -> Dictation | None:
        return self._items[-1] if self._items else None

    def items(self) -> list[Dictation]:
        return list(reversed(self._items))


def iso_week(day: date) -> str:
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


class Stats(BaseModel):
    week: str = Field(default_factory=lambda: iso_week(date.today()))
    words_week: int = 0
    words_total: int = 0
    dictations_total: int = 0
    latencies: list[float] = Field(default_factory=list)

    def record(self, words: int, latency_s: float, today: date | None = None) -> None:
        week = iso_week(today or date.today())
        if week != self.week:
            self.week, self.words_week = week, 0
        self.words_week += words
        self.words_total += words
        self.dictations_total += 1
        self.latencies = (self.latencies + [round(latency_s, 3)])[-50:]

    def median_latency(self) -> float | None:
        return statistics.median(self.latencies) if self.latencies else None

    def words_over_free_cap(self, cap: int) -> int:
        return max(0, self.words_week - cap)


def load_stats(path: Path) -> Stats:
    if not path.exists():
        return Stats()
    try:
        return Stats.model_validate_json(path.read_text(encoding="utf-8"))
    except (ValidationError, UnicodeDecodeError) as exc:
        log.error("stats file %s invalid, starting fresh: %s", path, exc)
        return Stats()


def save_stats(stats: Stats, path: Path) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(stats.model_dump_json(), encoding="utf-8")
    tmp.replace(path)
