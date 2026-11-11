"""Telemetry messages in the format of schemas/telemetry/v1.schema.json."""

from __future__ import annotations

import json
import random
import uuid
from datetime import UTC, datetime
from typing import Any

from simulators.sensors import SENSORS, Sensor

SCHEMA_VERSION = 1


def utc_timestamp(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def serialize(message: dict[str, Any]) -> str:
    return json.dumps(message, separators=(",", ":"), ensure_ascii=False)


class SimulatedDevice:
    def __init__(self, device_id: str, mode: str, rng: random.Random, start: datetime) -> None:
        self.device_id = device_id
        self.mode = mode
        self.rng = rng
        self.sensors = {name: Sensor(model, rng, start) for name, model in SENSORS[mode].items()}

    def next_message(self, moment: datetime) -> dict[str, Any]:
        return {
            "schemaVersion": SCHEMA_VERSION,
            # From the seeded generator, so a run with --seed is reproducible end to end.
            "messageId": str(uuid.UUID(int=self.rng.getrandbits(128), version=4)),
            "deviceId": self.device_id,
            "mode": self.mode,
            "timestamp": utc_timestamp(moment),
            "readings": {name: sensor.read(moment) for name, sensor in self.sensors.items()},
        }
