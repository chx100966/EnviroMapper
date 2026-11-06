"""Sensor models: plausible, smoothly changing signals for the readings of each mode.

Every reading is a mean-reverting random walk (an Ornstein-Uhlenbeck process) around a baseline,
optionally with a daily cycle, clipped to the sensor's measuring range. Consecutive values are
correlated like real measurements - plain uniform noise isn't, and would be useless for training
anomaly detection later.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import datetime

MODES = ("agriculture", "industry", "weather")


@dataclass(frozen=True)
class SensorModel:
    baseline: float
    spread: float  # standard deviation around the (daily) mean in the long run
    reversion: float  # how fast the value returns to the mean, per hour
    minimum: float  # measuring range, as in schemas/telemetry/v1.schema.json
    maximum: float
    daily_amplitude: float = 0.0  # +/- around the baseline over a day, peak at 14:00 UTC

    def mean(self, moment: datetime) -> float:
        hours = moment.hour + moment.minute / 60
        return self.baseline + self.daily_amplitude * math.cos(2 * math.pi * (hours - 14) / 24)


# Keys and measuring ranges follow the telemetry schema; tests keep the two in sync.
SENSORS: dict[str, dict[str, SensorModel]] = {
    "agriculture": {
        "soil_moisture": SensorModel(35, 4, 0.05, 0, 100),
        "temperature": SensorModel(15, 2, 0.5, -40, 60, daily_amplitude=6),
        "humidity": SensorModel(70, 5, 0.5, 0, 100, daily_amplitude=-15),
    },
    "industry": {
        "vibration": SensorModel(3.5, 0.5, 2, 0, 100),
        "temperature": SensorModel(65, 3, 1, -40, 200),
        "pressure": SensorModel(6, 0.3, 4, 0, 25),
    },
    "weather": {
        "temperature": SensorModel(10, 2.5, 0.3, -50, 60, daily_amplitude=5),
        "pressure": SensorModel(1013, 6, 0.05, 850, 1100),
        "wind_speed": SensorModel(15, 6, 1, 0, 300),
    },
}


class Sensor:
    def __init__(self, model: SensorModel, rng: random.Random, start: datetime) -> None:
        self.model = model
        self.rng = rng
        self.value = self._clip(model.mean(start) + rng.gauss(0, model.spread))
        self.updated = start

    def read(self, moment: datetime) -> float:
        """Advances the signal to `moment` and returns the reading, rounded to 2 decimals."""
        model = self.model
        hours = max((moment - self.updated).total_seconds(), 0) / 3600
        # Exact update of the process, stable for any interval (a plain Euler step overshoots
        # when the interval is long compared with 1 / reversion).
        decay = math.exp(-model.reversion * hours)
        mean = model.mean(moment)
        noise = model.spread * math.sqrt(1 - decay**2) * self.rng.gauss(0, 1)
        self.value = self._clip(mean + (self.value - mean) * decay + noise)
        self.updated = moment
        return round(self.value, 2)

    def _clip(self, value: float) -> float:
        return min(max(value, self.model.minimum), self.model.maximum)
