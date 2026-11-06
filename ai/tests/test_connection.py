import pytest

from simulators.connection import (
    DEFAULT_PROVISIONING_HOST,
    ConfigError,
    connection_string_device_id,
    derive_device_key,
    dps_settings,
)

GROUP_KEY = "ZW52aXJvbWFwcGVyLXRlc3QtZ3JvdXAta2V5LTAxMjM0NTY3ODlhYmNkZWY="


def test_device_key_is_hmac_of_the_registration_id():
    # printf sim-agriculture-01 | openssl mac -digest SHA256 -macopt hexkey:<group key> HMAC
    assert derive_device_key(GROUP_KEY, "sim-agriculture-01") == (
        "FGi8LqFZesJdyKp8A7VjU4UK8jfTZ73SsuCYsnvuCPI="
    )


def test_dps_settings_derive_the_device_key_from_the_mode_group():
    env = {"DPS_ID_SCOPE": "0ne00ABCDEF", "DPS_ENROLLMENT_KEY_AGRICULTURE": GROUP_KEY}
    settings = dps_settings(env, "sim-agriculture-01", "agriculture")
    assert settings.id_scope == "0ne00ABCDEF"
    assert settings.registration_id == "sim-agriculture-01"
    assert settings.device_key == derive_device_key(GROUP_KEY, "sim-agriculture-01")
    assert settings.host == DEFAULT_PROVISIONING_HOST


def test_dps_settings_need_the_id_scope():
    with pytest.raises(ConfigError, match="DPS_ID_SCOPE"):
        dps_settings({"DPS_ENROLLMENT_KEY_WEATHER": GROUP_KEY}, "sim-weather-01", "weather")


def test_dps_settings_need_the_group_key_of_the_mode():
    env = {"DPS_ID_SCOPE": "0ne00ABCDEF", "DPS_ENROLLMENT_KEY_AGRICULTURE": GROUP_KEY}
    with pytest.raises(ConfigError, match="DPS_ENROLLMENT_KEY_INDUSTRY"):
        dps_settings(env, "sim-industry-01", "industry")


def test_device_id_comes_from_the_connection_string():
    value = "HostName=iot-x.azure-devices.net;DeviceId=sim-weather-07;SharedAccessKey=a2V5"
    assert connection_string_device_id(value) == "sim-weather-07"
    with pytest.raises(ConfigError):
        connection_string_device_id("HostName=iot-x.azure-devices.net;SharedAccessKey=a2V5")
