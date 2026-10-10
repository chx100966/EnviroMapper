"""Smoke test for the IoT simulator."""

from simulators.run_simulator import SENSORS, generate_reading


def test_generate_reading():
    for sensors in SENSORS.values():
        for sensor in sensors:
            reading = generate_reading(sensor, "test-device")
            assert reading["deviceId"] == "test-device"
            assert sensor["min"] <= reading["value"] <= sensor["max"]
