"""IoT device simulator — sends synthetic sensor readings to Azure IoT Hub."""

import argparse
import asyncio
import json
import random
import time
from datetime import datetime, timezone

MODES = ("agriculture", "industry", "weather")

SENSORS: dict[str, list[dict]] = {
    "agriculture": [
        {"type": "soil_moisture", "unit": "%", "min": 10, "max": 90},
        {"type": "temperature", "unit": "°C", "min": -5, "max": 40},
        {"type": "humidity", "unit": "%", "min": 20, "max": 100},
    ],
    "industry": [
        {"type": "vibration", "unit": "mm/s", "min": 0, "max": 50},
        {"type": "temperature", "unit": "°C", "min": 20, "max": 120},
        {"type": "pressure", "unit": "bar", "min": 0, "max": 10},
    ],
    "weather": [
        {"type": "temperature", "unit": "°C", "min": -20, "max": 45},
        {"type": "pressure", "unit": "hPa", "min": 950, "max": 1050},
        {"type": "wind_speed", "unit": "km/h", "min": 0, "max": 150},
    ],
}


def generate_reading(sensor: dict, device_id: str) -> dict:
    value = round(random.uniform(sensor["min"], sensor["max"]), 2)
    return {
        "deviceId": device_id,
        "sensorType": sensor["type"],
        "value": value,
        "unit": sensor["unit"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def simulate(mode: str, interval: float, device_id: str) -> None:
    sensors = SENSORS[mode]
    print(f"[simulator] mode={mode}  device={device_id}  interval={interval}s")
    while True:
        for sensor in sensors:
            reading = generate_reading(sensor, device_id)
            print(json.dumps(reading))
        await asyncio.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=MODES, default="agriculture")
    parser.add_argument("--device-id", default="sim-device-001")
    parser.add_argument("--interval", type=float, default=5.0)
    args = parser.parse_args()
    asyncio.run(simulate(args.mode, args.interval, args.device_id))


if __name__ == "__main__":
    main()
