"""The shared telemetry schema (schemas/telemetry) and its examples."""

import copy
import json
from pathlib import Path

import pytest

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas" / "telemetry"
EXAMPLES = sorted((SCHEMA_DIR / "examples").glob("*.json"))


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.stem)
def test_examples_are_valid(validator, path):
    assert list(validator.iter_errors(load(path))) == []


def test_there_is_an_example_per_mode(schema):
    assert {p.stem for p in EXAMPLES} == set(schema["properties"]["mode"]["enum"])


INVALID = {
    "sensor of another mode": lambda m: m["readings"].update(wind_speed=3.0),
    "outside the measuring range": lambda m: m["readings"].update(humidity=100.5),
    "unknown field": lambda m: m.update(location="Katowice"),
    "local time instead of UTC": lambda m: m.update(timestamp="2026-11-06T21:15:30+01:00"),
    "impossible date": lambda m: m.update(timestamp="2026-13-06T20:15:30Z"),
    "no readings": lambda m: m.update(readings={}),
    "number as a string": lambda m: m["readings"].update(temperature="12.4"),
    "null instead of leaving the sensor out": lambda m: m["readings"].update(temperature=None),
    "unknown mode": lambda m: m.update(mode="mining"),
    "other schema version": lambda m: m.update(schemaVersion=2),
    "uppercase device ID": lambda m: m.update(deviceId="Sim-Agriculture-01"),
    "message ID that isn't a UUID": lambda m: m.update(messageId="42"),
    "missing timestamp": lambda m: m.pop("timestamp"),
}


@pytest.mark.parametrize("mutate", INVALID.values(), ids=INVALID.keys())
def test_rejects(validator, mutate):
    message = copy.deepcopy(load(SCHEMA_DIR / "examples" / "agriculture.json"))
    mutate(message)
    assert list(validator.iter_errors(message)) != []


def test_partial_readings_are_valid(validator):
    message = load(SCHEMA_DIR / "examples" / "weather.json")
    del message["readings"]["wind_speed"]
    assert list(validator.iter_errors(message)) == []
