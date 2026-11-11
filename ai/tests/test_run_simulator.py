import json

import pytest

from simulators import run_simulator
from simulators.connection import MqttSettings, SendError


@pytest.fixture
def no_settings(monkeypatch, tmp_path):
    for name in (
        "MQTT_HOST",
        "MQTT_PORT",
        "MQTT_USERNAME",
        "MQTT_PASSWORD",
        "MQTT_TLS",
        "MQTT_TOPIC_PREFIX",
    ):
        monkeypatch.delenv(name, raising=False)
    return ["--env-file", str(tmp_path / "missing.env")]


def printed_messages(capsys):
    return [json.loads(line) for line in capsys.readouterr().out.splitlines()]


def test_dry_run_prints_valid_messages(capsys, validator):
    assert (
        run_simulator.main(
            ["--mode", "weather", "--count", "3", "--interval", "0", "--dry-run", "--seed", "1"]
        )
        == 0
    )
    messages = printed_messages(capsys)
    assert len(messages) == 3
    assert {m["deviceId"] for m in messages} == {"sim-weather-01"}
    assert all(list(validator.iter_errors(m)) == [] for m in messages)


def test_all_modes_by_default(capsys):
    run_simulator.main(["--count", "1", "--dry-run"])
    assert sorted(m["mode"] for m in printed_messages(capsys)) == [
        "agriculture",
        "industry",
        "weather",
    ]


@pytest.mark.parametrize(
    "argv",
    [
        ["--device-id", "sim-x-01"],  # needs a single mode
        ["--mode", "weather", "--device-id", "Sim-X"],  # doesn't fit the schema's deviceId
        ["--count", "0"],
    ],
)
def test_rejects_bad_arguments(argv):
    with pytest.raises(SystemExit):
        run_simulator.main([*argv, "--dry-run"])


def test_missing_settings_end_with_a_hint(no_settings, caplog):
    assert run_simulator.main(["--count", "1", *no_settings]) == 2
    assert "ai/.env.example" in caplog.text


class FakeClient:
    def __init__(self, fail=False):
        self.sent = []
        self.closed = False
        self.fail = fail

    async def send(self, message):
        if self.fail:
            raise SendError("not connected")
        self.sent.append(message)

    async def shutdown(self):
        self.closed = True


def fake_connect(monkeypatch, client):
    connected = []

    async def connect(settings, device_id):
        connected.append((settings, device_id))
        return client

    monkeypatch.setattr(run_simulator, "connect", connect)
    return connected


def test_publishes_one_connection_per_device(no_settings, monkeypatch, validator):
    monkeypatch.setenv("MQTT_HOST", "localhost")
    client = FakeClient()
    connected = fake_connect(monkeypatch, client)
    argv = ["--count", "2", "--interval", "0", *no_settings]
    assert run_simulator.main(argv) == 0

    assert sorted(device_id for _, device_id in connected) == [
        "sim-agriculture-01",
        "sim-industry-01",
        "sim-weather-01",
    ]
    assert all(settings == MqttSettings(host="localhost") for settings, _ in connected)
    assert len(client.sent) == 6 and client.closed
    assert all(list(validator.iter_errors(message)) == [] for message in client.sent)


def test_a_failed_send_is_logged_and_the_run_goes_on(no_settings, monkeypatch, caplog):
    monkeypatch.setenv("MQTT_HOST", "localhost")
    client = FakeClient(fail=True)
    fake_connect(monkeypatch, client)
    argv = ["--mode", "industry", "--count", "2", "--interval", "0", *no_settings]
    assert run_simulator.main(argv) == 0
    assert caplog.text.count("not sent") == 2 and client.closed
