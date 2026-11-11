"""Connecting a simulated device to the MQTT broker (mosquitto, see docker-compose.yml).

paho-mqtt is imported lazily, so --dry-run works without it.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from simulators.telemetry import serialize

if TYPE_CHECKING:
    from paho.mqtt.client import Client

DEFAULT_PORT = 1883
DEFAULT_TLS_PORT = 8883
DEFAULT_TOPIC_PREFIX = "enviromapper/telemetry"
# At least once: the broker acknowledges every message. Consumers drop duplicates by messageId.
QOS = 1
CONNECT_TIMEOUT = 10.0
PUBLISH_TIMEOUT = 10.0


class ConfigError(Exception):
    pass


class DeviceConnectionError(Exception):
    pass


class SendError(Exception):
    pass


@dataclass(frozen=True)
class MqttSettings:
    host: str
    port: int = DEFAULT_PORT
    username: str | None = None
    password: str | None = None
    tls: bool = False
    topic_prefix: str = DEFAULT_TOPIC_PREFIX


def _flag(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def mqtt_settings(env: Mapping[str, str]) -> MqttSettings:
    host = env.get("MQTT_HOST")
    if not host:
        raise ConfigError("Set MQTT_HOST in ai/.env - see ai/.env.example.")
    tls = _flag(env.get("MQTT_TLS"))
    port_value = env.get("MQTT_PORT")
    try:
        port = int(port_value) if port_value else (DEFAULT_TLS_PORT if tls else DEFAULT_PORT)
    except ValueError:
        raise ConfigError(f"MQTT_PORT must be a number, not {port_value!r}.") from None
    return MqttSettings(
        host=host,
        port=port,
        username=env.get("MQTT_USERNAME") or None,
        password=env.get("MQTT_PASSWORD") or None,
        tls=tls,
        topic_prefix=(env.get("MQTT_TOPIC_PREFIX") or DEFAULT_TOPIC_PREFIX).rstrip("/"),
    )


def topic(settings: MqttSettings, message: dict[str, Any]) -> str:
    """enviromapper/telemetry/<mode>/<deviceId> - consumers can subscribe per mode or per device."""
    return f"{settings.topic_prefix}/{message['mode']}/{message['deviceId']}"


class DeviceClient:
    """One MQTT connection per simulated device, with its own client ID."""

    def __init__(self, client: Client, settings: MqttSettings) -> None:
        self.client = client
        self.settings = settings

    async def send(self, message: dict[str, Any]) -> None:
        info = self.client.publish(topic(self.settings, message), serialize(message), qos=QOS)
        try:
            await asyncio.to_thread(info.wait_for_publish, PUBLISH_TIMEOUT)
        except (ValueError, RuntimeError) as error:  # queue full / not connected
            raise SendError(str(error)) from error
        if not info.is_published():
            raise SendError(f"not acknowledged by the broker (rc={info.rc})")

    async def shutdown(self) -> None:
        self.client.disconnect()
        self.client.loop_stop()


async def connect(settings: MqttSettings, device_id: str) -> DeviceClient:
    import paho.mqtt.client as mqtt

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=device_id)
    if settings.username:
        client.username_pw_set(settings.username, settings.password)
    if settings.tls:
        client.tls_set()
    # Reconnects by itself (loop_start) if the broker goes away; publishes wait for it.
    client.reconnect_delay_set(min_delay=1, max_delay=30)

    loop = asyncio.get_running_loop()
    connected = loop.create_future()

    def on_connect(_client, _userdata, _flags, reason_code, _properties):
        if not connected.done():
            loop.call_soon_threadsafe(connected.set_result, reason_code)

    client.on_connect = on_connect
    where = f"{device_id} ({settings.host}:{settings.port})"
    try:
        await asyncio.to_thread(client.connect, settings.host, settings.port)
    except OSError as error:
        raise DeviceConnectionError(f"{where}: {error}") from error
    client.loop_start()
    try:
        reason_code = await asyncio.wait_for(connected, CONNECT_TIMEOUT)
    except TimeoutError:
        client.loop_stop()
        raise DeviceConnectionError(f"{where}: no answer from the broker") from None
    if reason_code.is_failure:
        client.loop_stop()
        raise DeviceConnectionError(f"{where}: broker refused the connection ({reason_code})")
    return DeviceClient(client, settings)
