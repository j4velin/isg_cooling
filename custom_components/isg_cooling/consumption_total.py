"""Lifetime counter for the cooling power consumption.

The ISG only shows windows (1-24 h, 1-12 M, 13-24 M) but no total, so the
total is kept here: it starts at 1-12 M + 13-24 M and then adds up the
1-24 h counter, which resets at midnight.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime

# hours after midnight after which the ISG has reset its 1-24 h counter
RESET_GRACE_HOURS = 1


@dataclass
class CoolingConsumptionTotal:
    """consumption before the current day (base) + the current day (last_24h)"""

    base: float | None = None
    last_24h: float = 0.0
    # ISO date of the last_24h reading
    day: str | None = None

    @property
    def value(self) -> float | None:
        if self.base is None:
            return None
        return round(self.base + self.last_24h, 3)

    def update(
        self,
        last_24h: float | None,
        last_12m: float | None,
        last_prev_12m: float | None,
        now: datetime,
    ) -> None:
        """add a new reading of the ISG windows"""
        if last_24h is None:
            # no cooling rows on the ISG page
            return
        today = now.date().isoformat()
        if self.base is None:
            if last_12m is None:
                return
            self.base = last_12m + (last_prev_12m or 0.0)
        elif last_24h < self.last_24h or (
            self.day != today and now.hour >= RESET_GRACE_HOURS
        ):
            # the 1-24 h counter was reset, maybe while we didn't look
            self.base += self.last_24h
        self.last_24h = last_24h
        self.day = today

    def as_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> CoolingConsumptionTotal | None:
        try:
            return cls(
                base=float(data["base"]),
                last_24h=float(data["last_24h"]),
                day=data.get("day"),
            )
        except (KeyError, TypeError, ValueError):
            return None
