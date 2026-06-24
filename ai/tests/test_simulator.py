"""Smoke tests for the IoT simulator."""

from simulators.run_simulator import SENSORS, generate_reading


def test_generate_reading_agriculture():
    sensor = SENSORS["agriculture"][0]
    reading = generate_reading(sensor, "test-device")
    assert reading["deviceId"] == "test-device"
    assert reading["sensorType"] == sensor["type"]
    assert sensor["min"] <= reading["value"] <= sensor["max"]
    assert "timestamp" in reading


def test_generate_reading_all_modes():
    for mode, sensors in SENSORS.items():
        for sensor in sensors:
            reading = generate_reading(sensor, f"dev-{mode}")
            assert reading["value"] >= sensor["min"]
            assert reading["value"] <= sensor["max"]


def test_all_modes_have_temperature():
    for mode in ("agriculture", "industry", "weather"):
        types = [s["type"] for s in SENSORS[mode]]
        assert "temperature" in types
