"""Lifetime counter for the cooling power consumption.

The ISG only shows windows (1-24 h, 1-12 M, 13-24 M) but no total, so the
total is kept here. "1-24 h" is the consumption of the last 24 hours, which
the ISG updates every hour, a few minutes after the full hour. Reading it
once a day at the same time therefore gives consecutive 24 h periods that
neither overlap nor leave gaps: the total starts at 1-12 M + 13-24 M and
adds the 1-24 h value once a day, in the evening.

The ISG updates 1-12 M once a day, overnight (it stays the same during the
day, while 1-24 h changes hourly). So the start value, taken right at setup,
reaches until the last midnight, and the first evening reading (from 23:00
of the day before) overlaps it by one hour at most.

The reading is taken after the ISG's 23:00 update, so it covers 23:00 of the
day before until 23:00 and is booked on the day it mostly belongs to; only
the last hour of a day moves to the next one. A reading after midnight would
book the whole day on the next date.

On the nights the clocks change, two readings are 23 or 25 hours apart, so
one hour is counted twice (spring) or not at all (autumn). That hour is at
night, in March or October, when there is practically no cooling.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, time

# the daily reading is taken in this window (local time): after the ISG
# updated the 1-24 h value at 23:00 and before its next update at midnight
DAILY_READING_START = time(23, 10)
# times of the daily reading (local time), independent of the poll interval;
# the later ones are retries in case the ISG couldn't be read
DAILY_READING_HOUR = 23
DAILY_READING_MINUTES = (15, 25, 35, 45, 55)

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

    def is_read(self, now: datetime) -> bool:
        """True if the daily reading of this day is done"""
        return self.day == now.date().isoformat()

    def update(
        self,
        last_24h: float | None,
        last_12m: float | None,
        last_prev_12m: float | None,
        now: datetime,
    ) -> None:
        """add a new reading of the ISG windows"""
        today = now.date().isoformat()
        in_reading_window = now.time() >= DAILY_READING_START
        if self.base is None:
            if last_12m is None:
                return
            # right away, at any time: 1-12 M reaches until the last midnight
            self.base = last_12m + (last_prev_12m or 0.0)
            if in_reading_window and last_24h is not None:
                # today's reading is due already, so count today right away;
                # otherwise it would only be added tomorrow evening, if ever
                self.base += last_24h
                self.day = today
            return
        if not in_reading_window:
            # outside the daily reading, or missed it, e.g. while Home
            # Assistant was offline
            return
        if last_24h is None or self.day == today:
            return
        # the 24 hours until 23:00 today
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
