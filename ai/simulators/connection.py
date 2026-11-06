"""Connecting a simulated device to IoT Hub: through DPS (the default) or a connection string.

The Python device SDK (azure-iot-device) speaks MQTT only - port 8883, or 443 with websockets=True
where 8883 is blocked. It is imported lazily, so --dry-run works without it.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import ssl
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from simulators.telemetry import CONTENT_ENCODING, CONTENT_TYPE, serialize

if TYPE_CHECKING:
    from azure.iot.device import Message
    from azure.iot.device.aio import IoTHubDeviceClient

DEFAULT_PROVISIONING_HOST = "global.azure-devices-provisioning.net"


class ConfigError(Exception):
    pass


class DeviceConnectionError(Exception):
    pass


@dataclass(frozen=True)
class DpsSettings:
    id_scope: str
    registration_id: str
    device_key: str
    host: str = DEFAULT_PROVISIONING_HOST


@dataclass(frozen=True)
class ConnectionStringSettings:
    connection_string: str


Settings = DpsSettings | ConnectionStringSettings


def derive_device_key(group_key: str, registration_id: str) -> str:
    """Key of one device in a symmetric-key enrollment group: HMAC-SHA256 of its registration ID."""
    digest = hmac.new(base64.b64decode(group_key), registration_id.encode(), hashlib.sha256)
    return base64.b64encode(digest.digest()).decode()


def connection_string_device_id(connection_string: str) -> str:
    parts = dict(part.split("=", 1) for part in connection_string.split(";") if "=" in part)
    if not parts.get("DeviceId"):
        raise ConfigError("IOTHUB_DEVICE_CONNECTION_STRING has no DeviceId.")
    return parts["DeviceId"]


def dps_settings(env: Mapping[str, str], registration_id: str, mode: str) -> DpsSettings:
    id_scope = env.get("DPS_ID_SCOPE")
    if not id_scope:
        raise ConfigError(
            "Set DPS_ID_SCOPE and the enrollment group keys (or IOTHUB_DEVICE_CONNECTION_STRING) "
            "in ai/.env - see ai/.env.example."
        )
    key_variable = f"DPS_ENROLLMENT_KEY_{mode.upper()}"
    group_key = env.get(key_variable)
    if not group_key:
        raise ConfigError(f"Set {key_variable} in ai/.env to simulate a {mode} device.")
    return DpsSettings(
        id_scope=id_scope,
        registration_id=registration_id,
        device_key=derive_device_key(group_key, registration_id),
        host=env.get("DPS_PROVISIONING_HOST") or DEFAULT_PROVISIONING_HOST,
    )


async def connect(settings: Settings, websockets: bool = False) -> IoTHubDeviceClient:
    from azure.iot.device.exceptions import ClientError, ServiceError

    if not hasattr(ssl, "PROTOCOL_TLSv1_2"):
        # azure-iot-device 2.14 builds its TLS context with it; Pythons linked against OpenSSL 4
        # (e.g. Homebrew's) no longer have it.
        raise DeviceConnectionError(
            f"azure-iot-device needs a Python built with OpenSSL 3 - this one has "
            f"{ssl.OPENSSL_VERSION}. Use python.org's or the system Python (see ai/README.md)."
        )
    try:
        return await _connect(settings, websockets)
    except (ClientError, ServiceError) as error:
        raise DeviceConnectionError(f"{_describe(settings)}: {error!r}") from error


def _describe(settings: Settings) -> str:
    if isinstance(settings, DpsSettings):
        return f"{settings.registration_id} (DPS {settings.id_scope})"
    return connection_string_device_id(settings.connection_string)


async def _connect(settings: Settings, websockets: bool) -> IoTHubDeviceClient:
    from azure.iot.device.aio import IoTHubDeviceClient, ProvisioningDeviceClient

    if isinstance(settings, ConnectionStringSettings):
        client = IoTHubDeviceClient.create_from_connection_string(
            settings.connection_string, websockets=websockets
        )
    else:
        # Registers the device on first use (DPS creates it in IoT Hub with the group's twin
        # tags); later runs get the same assignment back.
        provisioning = ProvisioningDeviceClient.create_from_symmetric_key(
            provisioning_host=settings.host,
            registration_id=settings.registration_id,
            id_scope=settings.id_scope,
            symmetric_key=settings.device_key,
            websockets=websockets,
        )
        result = await provisioning.register()
        if result.status != "assigned":
            raise DeviceConnectionError(
                f"DPS did not assign {settings.registration_id}: status {result.status}"
            )
        client = IoTHubDeviceClient.create_from_symmetric_key(
            symmetric_key=settings.device_key,
            hostname=result.registration_state.assigned_hub,
            device_id=result.registration_state.device_id,
            websockets=websockets,
        )
    await client.connect()
    return client


def to_iothub_message(message: dict[str, Any]) -> Message:
    from azure.iot.device import Message

    # Without the content type and encoding IoT Hub can't read the body for routing, and the
    # message never reaches Cosmos DB.
    return Message(
        serialize(message),
        message_id=message["messageId"],
        content_encoding=CONTENT_ENCODING,
        content_type=CONTENT_TYPE,
    )
