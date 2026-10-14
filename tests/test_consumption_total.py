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
    """updated once a day, so it reaches until the last midnight"""
    return round(SEED_12M + sum(BUCKETS[:hours_done(t) // 24 * 24]), 3)


def read(total: CoolingConsumptionTotal, t: datetime) -> None:
    total.update(window_24h(t), window_12m(t), 0.0, t)


def run(added=None, offline=lambda t: False, restarts=()):
    """returns the total and all its values, minute by minute"""
    added = added or ADDED
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


# set up on the third day, so the day before has consumption
ADDED = START + timedelta(days=2, hours=14, minutes=3)


def expected(added=ADDED, lost_days=()) -> float:
    """seed at setup + every evening reading after it"""
    want = window_12m(added)
    day = added.replace(hour=0, minute=0)
    if added.hour == 23 and added.minute >= 10:
        # set up during the reading window: today counted right away
        want += window_24h(added)
        day += timedelta(days=1)
    while day.replace(hour=23, minute=15) <= END:
        if day.date() not in lost_days:
            want += consumption_until_23(day)
        day += timedelta(days=1)
    return round(want, 3)


def true_consumption(until: datetime) -> float:
    return round(SEED_12M + sum(BUCKETS[:hour_index(until)]), 3)


def test_value_right_after_setup():
    total = CoolingConsumptionTotal()
    read(total, ADDED)
    assert total.value == window_12m(ADDED)


def test_overlap_of_the_start_value_is_one_hour():
    # the first evening reading starts at 23:00 the day before, the start
    # value ends at midnight: 23:00-24:00 of that day is counted twice
    total, _ = run()
    last_reading = (END - timedelta(days=1)).replace(hour=23, minute=0)
    overlap_hour = BUCKETS[hour_index(ADDED.replace(hour=0, minute=0)) - 1]
    assert total.value == round(true_consumption(last_reading) + overlap_hour, 3)


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
    read(total, ADDED)
    before = total.value
    read(total, (ADDED + timedelta(days=1)).replace(hour=0, minute=15))
    assert total.value == before


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


def test_added_in_the_reading_window_counts_that_day():
    added = START + timedelta(days=3, hours=23, minutes=40)
    total = CoolingConsumptionTotal()
    read(total, added)
    assert total.value == round(window_12m(added) + window_24h(added), 3)
    assert total.is_read(added)
    total, _ = run(added=added)
    assert total.value == expected(added)


def test_stored_data_of_the_old_version_is_discarded():
    assert CoolingConsumptionTotal.from_dict({"base": 1, "last_24h": 2, "day": "x"}) is None
    assert CoolingConsumptionTotal.from_dict(CoolingConsumptionTotal().as_dict()) is None
