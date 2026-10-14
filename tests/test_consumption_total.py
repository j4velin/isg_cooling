"""Daily cooling total, against a simulated ISG with a rolling 24 h window.

The simulation gives the total only the readings it gets in sensor.py: one
at setup (also after a restart) and the evening readings at 23:15, 23:25,
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


def hour_index(t: datetime) -> int:
    return int((t - START).total_seconds() // 3600)


def consumption_until_23(day: datetime) -> float:
    """23:00 of the day before until 23:00 of this day"""
    i = hour_index(day.replace(hour=23, minute=0))
    return sum(BUCKETS[i - 24:i])


def expected(first_day=START, lost_days=()) -> float:
    """seed at the first evening reading + every later day that was read"""
    want = window_12m(first_day.replace(hour=23, minute=15))
    day = first_day + timedelta(days=1)
    while day.replace(hour=23, minute=15) <= END:
        if day.date() not in lost_days:
            want += consumption_until_23(day)
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


def test_each_day_is_booked_on_its_own_date():
    # only the last hour (23:00-24:00) moves to the next day
    total = CoolingConsumptionTotal()
    day = START + timedelta(days=3)
    read(total, day.replace(hour=23, minute=15))
    before = total.value
    read(total, (day + timedelta(days=1)).replace(hour=23, minute=15))
    assert round(total.value - before, 3) == round(consumption_until_23(day + timedelta(days=1)), 3)


def test_retry_after_isg_down_at_23_15():
    day = (START + timedelta(days=5)).date()
    total, _ = run(offline=lambda t: t.date() == day and t.minute < 20)
    assert total.value == expected()


def test_isg_down_all_evening_loses_that_day():
    day = (START + timedelta(days=9)).date()
    total, _ = run(offline=lambda t: t.date() == day and t.hour == 23)
    assert total.value == expected(lost_days={day})


def test_no_reading_after_midnight():
    total = CoolingConsumptionTotal()
    read(total, START + timedelta(days=2, minutes=15))
    assert total.value is None


def test_restart_during_the_day_keeps_the_total():
    total, _ = run(restarts={START + timedelta(days=10, hours=13, minutes=7)})
    assert total.value == expected()


def test_restart_in_the_evening_after_failed_readings_still_counts():
    day = START + timedelta(days=12)
    total, _ = run(
        offline=lambda t: t.date() == day.date() and t.hour == 23 and t.minute < 50,
        restarts={day.replace(hour=23, minute=50)},
    )
    assert total.value == expected()


def test_added_in_the_evening_seeds_right_away():
    added = START + timedelta(days=1, hours=23, minutes=40)
    total, _ = run(added=added)
    want = window_12m(added) + sum(
        consumption_until_23(START + timedelta(days=d)) for d in range(2, 50)
    )
    assert total.value == round(want, 3)


def test_stored_data_of_the_old_version_is_discarded():
    assert CoolingConsumptionTotal.from_dict({"base": 1, "last_24h": 2, "day": "x"}) is None
    assert CoolingConsumptionTotal.from_dict(CoolingConsumptionTotal().as_dict()) is None
