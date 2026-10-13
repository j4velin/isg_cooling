"""Lifetime counter for the cooling power consumption.

The ISG only shows windows (1-24 h, 1-12 M, 13-24 M) but no total, so the
total is kept here. "1-24 h" is the consumption of the last 24 hours, which
the ISG updates every hour, a few minutes after the full hour. Reading it
once a day at the same time therefore gives consecutive 24 h periods that
neither overlap nor leave gaps: the total starts at 1-12 M + 13-24 M and
adds the 1-24 h value once a day, shortly after midnight.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, time

# the daily reading is taken in this window (local time), after the ISG
# updated the 1-24 h value at midnight and before its next update
DAILY_READING_START = time(0, 10)
DAILY_READING_END = time(1, 0)
# extra refresh for the daily reading, independent of the poll interval
DAILY_READING_TIME = time(0, 15)

# stored data of an older version is discarded and the total seeded again
STORAGE_VERSION = 2


@dataclass
class CoolingConsumptionTotal:
    """total consumption, updated once a day"""

    base: float | None = None
    # ISO date of the last daily reading added to base
    day: str | None = None

    @property
    def value(self) -> float | None:
        if self.base is None:
            return None
        return round(self.base, 3)

    def update(
        self,
        last_24h: float | None,
        last_12m: float | None,
        last_prev_12m: float | None,
        now: datetime,
    ) -> None:
        """add a new reading of the ISG windows"""
        today = now.date().isoformat()
        if not DAILY_READING_START <= now.time() < DAILY_READING_END:
            # outside the daily reading, or missed it, e.g. while Home
            # Assistant was offline
            return
        if self.base is None:
            if last_12m is None:
                return
            # seeded at the daily reading too, so the windows end at midnight
            # like the daily readings and nothing is counted twice
            self.base = last_12m + (last_prev_12m or 0.0)
            self.day = today
            return
        if last_24h is None or self.day == today:
            return
        # the 24 hours before midnight
        self.base += last_24h
        self.day = today

    def as_dict(self) -> dict:
        return {"version": STORAGE_VERSION, **asdict(self)}

    @classmethod
    def from_dict(cls, data: dict) -> CoolingConsumptionTotal | None:
        if data.get("version") != STORAGE_VERSION:
            return None
        try:
            return cls(base=float(data["base"]), day=data.get("day"))
        except (KeyError, TypeError, ValueError):
            return None
