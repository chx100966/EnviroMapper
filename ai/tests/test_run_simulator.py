import json

import pytest

from simulators import run_simulator
from simulators.connection import DpsSettings
from simulators.telemetry import CONTENT_ENCODING, CONTENT_TYPE

GROUP_KEY = "ZW52aXJvbWFwcGVyLXRlc3QtZ3JvdXAta2V5LTAxMjM0NTY3ODlhYmNkZWY="


@pytest.fixture
def no_settings(monkeypatch, tmp_path):
    for name in (
        "DPS_ID_SCOPE",
        "DPS_ENROLLMENT_KEY_AGRICULTURE",
        "DPS_ENROLLMENT_KEY_INDUSTRY",
        "DPS_ENROLLMENT_KEY_WEATHER",
        "IOTHUB_DEVICE_CONNECTION_STRING",
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
        ["--mode", "weather", "--device-id", "Sim-X"],  # not a DPS registration ID
        ["--count", "0"],
    ],
)
def test_rejects_bad_arguments(argv):
    with pytest.raises(SystemExit):
        run_simulator.main([*argv, "--dry-run"])


def test_missing_settings_end_with_a_hint(no_settings, caplog):
    assert run_simulator.main(["--count", "1", *no_settings]) == 2
    assert "ai/.env.example" in caplog.text


def test_a_connection_string_is_one_device(no_settings, monkeypatch, caplog):
    monkeypatch.setenv(
        "IOTHUB_DEVICE_CONNECTION_STRING", "HostName=h;DeviceId=sim-weather-07;SharedAccessKey=a2V5"
    )
    assert run_simulator.main(["--count", "1", *no_settings]) == 2
    assert "--mode" in caplog.text


class FakeClient:
    def __init__(self):
        self.sent = []
        self.closed = False

    async def send_message(self, message):
        self.sent.append(message)

    async def shutdown(self):
        self.closed = True


def test_sends_through_dps_with_the_routing_properties(no_settings, monkeypatch, validator):
    monkeypatch.setenv("DPS_ID_SCOPE", "0ne00ABCDEF")
    monkeypatch.setenv("DPS_ENROLLMENT_KEY_INDUSTRY", GROUP_KEY)
    client = FakeClient()
    connected = []

    async def fake_connect(settings, websockets=False):
        connected.append((settings, websockets))
        return client

    monkeypatch.setattr(run_simulator, "connect", fake_connect)
    argv = ["--mode", "industry", "--count", "2", "--interval", "0", "--websockets", *no_settings]
    assert run_simulator.main(argv) == 0

    [(settings, websockets)] = connected
    assert isinstance(settings, DpsSettings) and settings.registration_id == "sim-industry-01"
    assert websockets
    assert len(client.sent) == 2 and client.closed
    for message in client.sent:
        body = json.loads(message.data)
        assert list(validator.iter_errors(body)) == []
        assert message.content_type == CONTENT_TYPE
        assert message.content_encoding == CONTENT_ENCODING
        assert message.message_id == body["messageId"]
