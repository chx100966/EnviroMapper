import random
from datetime import UTC, datetime, timedelta

import pytest

from simulators.sensors import MODES, SENSORS
from simulators.telemetry import METERING_CHUNK, SimulatedDevice, metered_size, utc_timestamp

START = datetime(2026, 11, 6, 20, 0, tzinfo=UTC)


def run(mode, ticks, interval=timedelta(seconds=15), seed=1):
    device = SimulatedDevice(f"sim-{mode}-01", mode, random.Random(seed), START)
    return [device.next_message(START + interval * (i + 1)) for i in range(ticks)]


@pytest.mark.parametrize("mode", MODES)
def test_messages_match_the_schema(validator, mode):
    for message in run(mode, 2000):
        assert list(validator.iter_errors(message)) == [], message


@pytest.mark.parametrize("mode", MODES)
def test_a_message_is_one_chunk_of_the_free_tier_quota(mode):
    longest = max(run(mode, 200), key=metered_size)
    assert metered_size(longest) < METERING_CHUNK


@pytest.mark.parametrize("mode", MODES)
def test_sensors_match_the_schema(schema, mode):
    readings = schema["$defs"][f"{mode}Readings"]["properties"]
    assert set(SENSORS[mode]) == set(readings)
    for name, model in SENSORS[mode].items():
        assert (model.minimum, model.maximum) == (
            readings[name]["minimum"],
            readings[name]["maximum"],
        )
        assert model.minimum <= model.baseline <= model.maximum


@pytest.mark.parametrize("mode", MODES)
def test_readings_stay_in_range_after_a_long_gap(validator, mode):
    for message in run(mode, 50, interval=timedelta(days=3)):
        assert list(validator.iter_errors(message)) == []


def test_consecutive_readings_change_smoothly():
    temperatures = [m["readings"]["temperature"] for m in run("industry", 500)]
    steps = [abs(b - a) for a, b in zip(temperatures, temperatures[1:], strict=False)]
    # 15 s apart, a bearing temperature (spread 3 °C) moves by tenths of a degree, not degrees.
    assert max(steps) < 2


def test_a_seed_reproduces_the_run():
    assert run("weather", 20, seed=7) == run("weather", 20, seed=7)
    assert run("weather", 20, seed=7) != run("weather", 20, seed=8)


def test_timestamps_are_utc_with_milliseconds():
    moment = datetime(2026, 11, 6, 21, 15, 30, 123456, tzinfo=UTC).astimezone()
    assert utc_timestamp(moment) == "2026-11-06T21:15:30.123Z"
