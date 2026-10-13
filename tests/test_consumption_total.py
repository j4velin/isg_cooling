"""Daily cooling total, against a simulated ISG with a rolling 24 h window.

The simulation gives the total only the readings it gets in sensor.py: one
at setup (also after a restart) and the nightly readings at 00:15, 00:25,
... - not the regular polling.
"""
import json
import random
from datetime import datetime, timedelta

from isg_cooling.consumption_total import (
    DAILY_READING_HOUR,
    DAILY_READING_MINUTES,
    CoolingConsumptionTotal,
)

START = datetime(2026, 6, 1, 0, 0)  # bucket i = consumption of hour START + i
END = START + timedelta(days=50)
UPDATE_MINUTE = 4  # the ISG updates its windows a few minutes after the hour
SEED_12M = 313.0

_random = random.Random(2)
BUCKETS = [_random.choice([0, 0, 0.3, 0.8, 1.25]) for _ in range(24 * 52)]


def hours_done(t: datetime) -> int:
    """number of full hours the ISG has already put into its windows"""
    n = int((t - START).total_seconds() // 3600)
    return n if t.minute >= UPDATE_MINUTE else n - 1


def window_24h(t: datetime) -> float:
    n = hours_done(t)
    return round(sum(BUCKETS[max(0, n - 24):n]), 3)


def window_12m(t: datetime) -> float:
    return round(SEED_12M + sum(BUCKETS[:hours_done(t)]), 3)


def read(total: CoolingConsumptionTotal, t: datetime) -> None:
    total.update(window_24h(t), window_12m(t), 0.0, t)


def run(added=START + timedelta(hours=14, minutes=3), offline=lambda t: False, restarts=()):
    """returns the total and all its values, minute by minute"""
    total = CoolingConsumptionTotal()
    read(total, added)  # setup reading
    values, t = [], added
    while t < END:
        t += timedelta(minutes=1)
        if t in restarts:
            total = CoolingConsumptionTotal.from_dict(json.loads(json.dumps(total.as_dict())))
            if not offline(t):
                read(total, t)  # setup reading after the restart
        nightly = t.hour == DAILY_READING_HOUR and t.minute in DAILY_READING_MINUTES
        if nightly and not total.is_read(t) and not offline(t):
            read(total, t)
        if total.value is not None:
            values.append(total.value)
    return total, values


def expected(lost_days=()) -> float:
    """seed at the first midnight + every later day that was read"""
    first = START + timedelta(days=1)
    want = window_12m(first.replace(minute=15))
    day = first + timedelta(days=1)
    while day + timedelta(minutes=15) <= END:
        if day.date() not in lost_days:
            i = int((day - START).total_seconds() // 3600)
            want += sum(BUCKETS[i - 24:i])
        day += timedelta(days=1)
    return round(want, 3)


def test_unknown_before_the_first_daily_reading():
    total = CoolingConsumptionTotal()
    read(total, START + timedelta(hours=14))
    assert total.value is None


def test_matches_the_true_consumption_and_never_decreases():
    total, values = run()
    assert all(b >= a for a, b in zip(values, values[1:]))
    assert total.value == expected()


def test_retry_after_isg_down_at_00_15():
    day = (START + timedelta(days=5)).date()
    total, _ = run(offline=lambda t: t.date() == day and t.minute < 20)
    assert total.value == expected()


def test_isg_down_all_night_loses_that_day():
    day = (START + timedelta(days=9)).date()
    total, _ = run(offline=lambda t: t.date() == day and t.hour == 0)
    assert total.value == expected({day})


def test_restart_during_the_day_keeps_the_total():
    total, _ = run(restarts={START + timedelta(days=10, hours=13, minutes=7)})
    assert total.value == expected()


def test_restart_at_night_after_failed_readings_still_counts():
    day = START + timedelta(days=12)
    total, _ = run(
        offline=lambda t: t.date() == day.date() and t.hour == 0 and t.minute < 50,
        restarts={day + timedelta(minutes=50)},
    )
    assert total.value == expected()


def test_added_at_night_seeds_right_away():
    total, _ = run(added=START + timedelta(days=1, minutes=40))
    assert total.value == expected()


def test_stored_data_of_the_old_version_is_discarded():
    assert CoolingConsumptionTotal.from_dict({"base": 1, "last_24h": 2, "day": "x"}) is None
    assert CoolingConsumptionTotal.from_dict(CoolingConsumptionTotal().as_dict()) is None
