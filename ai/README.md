# EnviroMapper — AI module

For now this module holds the **IoT device simulator**; the analytics models come later.

## Simulator

`simulators/` simulates one device per mode — `sim-agriculture-01`, `sim-industry-01`,
`sim-weather-01` — each sending its readings every 15 s as one message in the
[telemetry format](../schemas/telemetry/README.md). On start every device registers through the
Device Provisioning Service, which creates it in IoT Hub with the twin tag `mode`, and then sends
over MQTT.

### Setup

Python 3.11 (what CI and the Function App use) or newer, **built with OpenSSL 3**: the device SDK
(`azure-iot-device` 2.14) doesn't work with OpenSSL 4. python.org installers and distribution
packages are fine; Homebrew/Linuxbrew Python may not be — check with
`python3 -c "import ssl; print(ssl.OPENSSL_VERSION)"`.

```bash
cd ai
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

### Connection settings

`ai/.env` (git-ignored, template in [.env.example](.env.example)) needs the DPS ID scope and the
enrollment group key of each mode. After `tofu apply`, with access to the Key Vault:

```bash
cd infra/terraform
kv=$(tofu output -raw key_vault_name)
{
  echo "DPS_ID_SCOPE=$(tofu output -raw dps_id_scope)"
  for mode in agriculture industry weather; do
    key=$(az keyvault secret show --vault-name "$kv" --name "dps-enrollment-key-$mode" --query value -o tsv)
    echo "DPS_ENROLLMENT_KEY_$(echo "$mode" | tr a-z A-Z)=$key"
  done
} > ../../ai/.env
```

A group key lets anyone register devices of that mode, so `.env` stays on your machine. The
simulator derives each device's own key from it (HMAC-SHA256 of the registration ID).

For a single device created by hand (`az iot hub device-identity create`), set
`IOTHUB_DEVICE_CONNECTION_STRING` instead and pick its `--mode`.

### Running

```bash
python -m simulators.run_simulator --dry-run --count 3     # print messages, nothing sent
python -m simulators.run_simulator                         # 3 devices, every 15 s, until Ctrl+C
python -m simulators.run_simulator --mode industry --device-id sim-industry-02 --count 20
```

| Option | Default | |
|---|---|---|
| `--mode` | `all` | `agriculture`, `industry`, `weather`, or `all` (one device each) |
| `--device-id` | `sim-<mode>-01` | device / DPS registration ID; with a single `--mode` |
| `--interval` | `15` | seconds between messages of a device |
| `--count` | until Ctrl+C | messages per device, then exit |
| `--seed` | random | reproducible readings (and message IDs) |
| `--websockets` | off | MQTT over WebSockets on port 443, for networks that block 8883 |
| `--dry-run` | off | print the messages as JSON lines instead of sending them |
| `--env-file` | `ai/.env` | connection settings; variables already in the environment win |

To watch the messages arrive:
`az iot hub monitor-events --hub-name "$(tofu output -raw iothub_name)" --properties all` (from
`infra/terraform`, needs `az extension add --name azure-iot`) shows each body with the `mode`
property IoT Hub adds. Stored messages are in the portal: Cosmos DB account → *Data Explorer* →
`enviromapper` → `telemetry`.

**Mind the quota:** the free IoT Hub takes 8,000 messages a day (reset at 00:00 UTC). Three devices
every 15 s send 720 an hour, so ~11 hours of simulation a day; use a longer `--interval` or fewer
modes for longer runs. A message is ~300 bytes, one 0.5 KB chunk. Once the quota is used up, sends
fail with a warning until midnight UTC.

**Protocol:** the Python device SDK supports MQTT only (port 8883, or 443 with `--websockets`); for
AMQP a device would need the C#, Java, Node.js or C SDK. MQTT is enough here — the simulator only
sends telemetry.

### How the readings are generated

Each sensor is a mean-reverting random walk (Ornstein–Uhlenbeck process) around a baseline, with a
daily cycle for air temperature and humidity, clipped to the measuring range from the schema
([sensors.py](simulators/sensors.py)). Consecutive values are correlated like real measurements,
which matters once the data is used to train anomaly detection. There are no injected anomalies
yet.

## Tests

```bash
pytest          # messages against schemas/telemetry, size per message, DPS key derivation, CLI
ruff check .
```

CI runs both on every pull request.
