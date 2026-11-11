"""IoT device simulator: sends telemetry of the three modes to Azure IoT Hub over MQTT.

    cd ai
    python -m simulators.run_simulator --dry-run --count 3   # print messages, no cloud
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
    ConnectionStringSettings,
    DeviceConnectionError,
    Settings,
    connect,
    connection_string_device_id,
    dps_settings,
    to_iothub_message,
)
from simulators.sensors import MODES
from simulators.telemetry import METERING_CHUNK, SimulatedDevice, metered_size, serialize

log = logging.getLogger("simulator")

# DPS registration IDs, as the telemetry schema expects them in deviceId.
DEVICE_ID = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,127}$")
DEFAULT_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


@dataclass
class PlannedDevice:
    device: SimulatedDevice
    settings: Settings | None  # None: dry run


def device_id(value: str) -> str:
    if not DEVICE_ID.match(value):
        raise argparse.ArgumentTypeError(
            "use lowercase letters, digits and . _ : - (up to 128 characters)"
        )
    return value


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m simulators.run_simulator",
        description="Send simulated EnviroMapper telemetry to Azure IoT Hub.",
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
        help="device / DPS registration ID (default sim-<mode>-01); needs a single --mode",
    )
    parser.add_argument(
        "--interval", type=float, default=15.0, help="seconds between messages (default 15)"
    )
    parser.add_argument(
        "--count", type=int, help="messages per device, then exit (default: until Ctrl+C)"
    )
    parser.add_argument("--seed", type=int, help="random seed, for reproducible readings")
    parser.add_argument(
        "--websockets",
        action="store_true",
        help="MQTT over WebSockets (port 443), for networks that block 8883",
    )
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
    connection_string = env.get("IOTHUB_DEVICE_CONNECTION_STRING")
    if connection_string and not args.dry_run and len(modes) > 1:
        raise ConfigError("IOTHUB_DEVICE_CONNECTION_STRING is one device - pick its --mode.")

    rng = random.Random(args.seed)
    start = datetime.now(UTC)
    planned = []
    for mode in modes:
        name = args.device_id or f"sim-{mode}-01"
        settings: Settings | None = None
        if connection_string and not args.dry_run:
            name = connection_string_device_id(connection_string)
            if not DEVICE_ID.match(name):
                raise ConfigError(
                    f"Device ID {name!r} doesn't fit the telemetry schema's deviceId."
                )
            settings = ConnectionStringSettings(connection_string)
        elif not args.dry_run:
            settings = dps_settings(env, name, mode)
        planned.append(PlannedDevice(SimulatedDevice(name, mode, rng, start), settings))
    return planned


async def send(client: Any, message: dict[str, Any]) -> None:
    from azure.iot.device.exceptions import ClientError

    try:
        await client.send_message(to_iothub_message(message))
    except ClientError as error:
        # The SDK reconnects by itself; this is e.g. a timeout, or the F1 hub refusing messages
        # once its daily quota is used up. Keep going - the next tick may get through.
        log.warning("%s: message %s not sent: %r", message["deviceId"], message["messageId"], error)
    else:
        size = metered_size(message)
        chunks = -(-size // METERING_CHUNK)
        log.info(
            "%s sent %s (%d B, %d of the daily quota)",
            message["deviceId"],
            message["messageId"],
            size,
            chunks,
        )


async def simulate(planned: PlannedDevice, args: argparse.Namespace) -> None:
    device = planned.device
    client = None
    if planned.settings is not None:
        client = await connect(planned.settings, websockets=args.websockets)
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
    logging.getLogger("azure.iot.device").setLevel(logging.WARNING)

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
