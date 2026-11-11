"""IoT device simulator: publishes telemetry of the three modes to the MQTT broker.

    cd ai
    python -m simulators.run_simulator --dry-run --count 3   # print messages, no broker
    python -m simulators.run_simulator                       # one device per mode, every 15 s

Connection settings come from ai/.env (see ai/.env.example and ai/README.md).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import random
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from simulators.connection import (
    ConfigError,
    DeviceConnectionError,
    MqttSettings,
    SendError,
    connect,
    mqtt_settings,
)
from simulators.sensors import MODES
from simulators.telemetry import SimulatedDevice, serialize

log = logging.getLogger("simulator")

# As the telemetry schema expects them in deviceId; also the device's MQTT client ID.
DEVICE_ID = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,127}$")
DEFAULT_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


@dataclass
class PlannedDevice:
    device: SimulatedDevice
    settings: MqttSettings | None  # None: dry run


def device_id(value: str) -> str:
    if not DEVICE_ID.match(value):
        raise argparse.ArgumentTypeError(
            "use lowercase letters, digits and . _ : - (up to 128 characters)"
        )
    return value


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m simulators.run_simulator",
        description="Publish simulated EnviroMapper telemetry to the MQTT broker.",
    )
    parser.add_argument(
        "--mode",
        choices=(*MODES, "all"),
        default="all",
        help="device mode; all = one device per mode (default)",
    )
    parser.add_argument(
        "--device-id",
        type=device_id,
        help="device ID (default sim-<mode>-01); needs a single --mode",
    )
    parser.add_argument(
        "--interval", type=float, default=15.0, help="seconds between messages (default 15)"
    )
    parser.add_argument(
        "--count", type=int, help="messages per device, then exit (default: until Ctrl+C)"
    )
    parser.add_argument("--seed", type=int, help="random seed, for reproducible readings")
    parser.add_argument(
        "--dry-run", action="store_true", help="print the messages instead of sending them"
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=DEFAULT_ENV_FILE,
        help="file with the connection settings (default ai/.env)",
    )
    args = parser.parse_args(argv)
    if args.device_id and args.mode == "all":
        parser.error("--device-id needs a single --mode")
    if args.interval < 0:
        parser.error("--interval can't be negative")
    if args.count is not None and args.count < 1:
        parser.error("--count must be at least 1")
    return args


def plan(args: argparse.Namespace, env: Mapping[str, str]) -> list[PlannedDevice]:
    modes = MODES if args.mode == "all" else (args.mode,)
    settings = None if args.dry_run else mqtt_settings(env)

    rng = random.Random(args.seed)
    start = datetime.now(UTC)
    return [
        PlannedDevice(
            SimulatedDevice(args.device_id or f"sim-{mode}-01", mode, rng, start), settings
        )
        for mode in modes
    ]


async def send(client: Any, message: dict[str, Any]) -> None:
    try:
        await client.send(message)
    except SendError as error:
        # paho reconnects by itself; keep going - the next tick may get through.
        log.warning("%s: message %s not sent: %s", message["deviceId"], message["messageId"], error)
    else:
        log.info("%s sent %s", message["deviceId"], message["messageId"])


async def simulate(planned: PlannedDevice, args: argparse.Namespace) -> None:
    device = planned.device
    client = None
    if planned.settings is not None:
        client = await connect(planned.settings, device.device_id)
        log.info("%s connected (%s)", device.device_id, device.mode)

    loop = asyncio.get_running_loop()
    next_tick = loop.time()
    sent = 0
    try:
        while args.count is None or sent < args.count:
            if sent:
                # Fixed schedule, so slow sends don't stretch the interval.
                next_tick += args.interval
                await asyncio.sleep(max(next_tick - loop.time(), 0))
            message = device.next_message(datetime.now(UTC))
            if client is None:
                print(serialize(message), flush=True)
            else:
                await send(client, message)
            sent += 1
    finally:
        if client is not None:
            await client.shutdown()


async def run(devices: list[PlannedDevice], args: argparse.Namespace) -> None:
    await asyncio.gather(*(simulate(planned, args) for planned in devices))


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stderr
    )

    if not args.dry_run:
        from dotenv import load_dotenv

        load_dotenv(args.env_file)  # variables already set in the environment take precedence

    try:
        asyncio.run(run(plan(args, os.environ), args))
    except (ConfigError, DeviceConnectionError) as error:
        log.error("%s", error)
        return 2
    except KeyboardInterrupt:
        log.info("stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
