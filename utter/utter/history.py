"""Recent dictations (text only, optionally saved locally) and weekly word stats (numbers only)."""

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
    """Most recent dictations, newest last. With a ``path`` they are kept in a local JSON-lines
    file (text only, never audio) so they survive restarts."""

    def __init__(self, size: int = 20, path: Path | None = None) -> None:
        self._items: deque[Dictation] = deque(maxlen=size)
        self.path = path
        if path is not None and path.exists():
            self._load(path, size)

    def _load(self, path: Path, size: int) -> None:
        lines = path.read_text(encoding="utf-8").splitlines()
        bad = 0
        for line in lines[-size:]:
            try:
                self._items.append(Dictation.model_validate_json(line))
            except ValidationError:
                bad += 1
        if bad:
            log.warning("skipped %d unreadable history lines in %s", bad, path)
        if len(lines) > size or bad:
            self._rewrite()

    def _rewrite(self) -> None:
        if self.path is None:
            return
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text("".join(d.model_dump_json() + "\n" for d in self._items), encoding="utf-8")
        tmp.replace(self.path)

    def add(self, item: Dictation) -> None:
        self._items.append(item)
        if self.path is not None:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(item.model_dump_json() + "\n")

    def clear(self) -> None:
        self._items.clear()
        if self.path is not None and self.path.exists():
            self.path.unlink()
        log.info("history cleared")

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
