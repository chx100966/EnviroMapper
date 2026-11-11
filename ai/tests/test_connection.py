import pytest

from simulators.connection import (
    DEFAULT_PORT,
    DEFAULT_TLS_PORT,
    DEFAULT_TOPIC_PREFIX,
    ConfigError,
    MqttSettings,
    mqtt_settings,
    topic,
)


def test_settings_need_only_the_host():
    assert mqtt_settings({"MQTT_HOST": "localhost"}) == MqttSettings(
        host="localhost", port=DEFAULT_PORT, topic_prefix=DEFAULT_TOPIC_PREFIX
    )


def test_settings_read_credentials_and_tls():
    env = {
        "MQTT_HOST": "broker.example.com",
        "MQTT_USERNAME": "simulator",
        "MQTT_PASSWORD": "secret",
        "MQTT_TLS": "true",
        "MQTT_TOPIC_PREFIX": "test/telemetry/",
    }
    settings = mqtt_settings(env)
    assert settings.port == DEFAULT_TLS_PORT
    assert (settings.username, settings.password, settings.tls) == ("simulator", "secret", True)
    assert settings.topic_prefix == "test/telemetry"


def test_settings_need_the_host():
    with pytest.raises(ConfigError, match="MQTT_HOST"):
        mqtt_settings({})


def test_port_must_be_a_number():
    with pytest.raises(ConfigError, match="MQTT_PORT"):
        mqtt_settings({"MQTT_HOST": "localhost", "MQTT_PORT": "abc"})


def test_topic_is_per_mode_and_device():
    settings = MqttSettings(host="localhost")
    message = {"mode": "weather", "deviceId": "sim-weather-01"}
    assert topic(settings, message) == "enviromapper/telemetry/weather/sim-weather-01"
