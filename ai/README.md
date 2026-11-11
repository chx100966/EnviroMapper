# EnviroMapper — AI module

For now this module holds the **IoT device simulator**; the analytics models come later.

## Simulator

`simulators/` simulates one device per mode — `sim-agriculture-01`, `sim-industry-01`,
`sim-weather-01` — each sending its readings every 15 s as one message in the
[telemetry format](../schemas/telemetry/README.md). Every device opens its own MQTT connection
(client ID = device ID) to the broker and publishes to `enviromapper/telemetry/<mode>/<deviceId>`
with QoS 1.

### Setup

Python 3.11 (what CI uses) or newer.

```bash
cd ai
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

### Connection settings

The broker is the `mqtt` service (Eclipse Mosquitto) from [docker-compose.yml](../docker-compose.yml):

```bash
docker compose up -d mqtt     # from the repository root; needs the root .env (cp .env.example .env)
cp ai/.env.example ai/.env    # defaults point at localhost:1883
```

`ai/.env` (git-ignored, template in [.env.example](.env.example)) holds `MQTT_HOST`, `MQTT_PORT`
and, for a broker that needs them, `MQTT_USERNAME`, `MQTT_PASSWORD` and `MQTT_TLS=true`.

### Running

```bash
python -m simulators.run_simulator --dry-run --count 3     # print messages, nothing sent
python -m simulators.run_simulator                         # 3 devices, every 15 s, until Ctrl+C
python -m simulators.run_simulator --mode industry --device-id sim-industry-02 --count 20
```

| Option | Default | |
|---|---|---|
| `--mode` | `all` | `agriculture`, `industry`, `weather`, or `all` (one device each) |
| `--device-id` | `sim-<mode>-01` | device ID (and MQTT client ID); with a single `--mode` |
| `--interval` | `15` | seconds between messages of a device |
| `--count` | until Ctrl+C | messages per device, then exit |
| `--seed` | random | reproducible readings (and message IDs) |
| `--dry-run` | off | print the messages as JSON lines instead of sending them |
| `--env-file` | `ai/.env` | connection settings; variables already in the environment win |

To watch the messages arrive:

```bash
docker compose exec mqtt mosquitto_sub -t 'enviromapper/telemetry/#' -v
```

### How the readings are generated

Each sensor is a mean-reverting random walk (Ornstein–Uhlenbeck process) around a baseline, with a
daily cycle for air temperature and humidity, clipped to the measuring range from the schema
([sensors.py](simulators/sensors.py)). Consecutive values are correlated like real measurements,
which matters once the data is used to train anomaly detection. There are no injected anomalies
yet.

## Tests

```bash
pytest          # messages against schemas/telemetry, MQTT settings, CLI
ruff check .
```

CI runs both on every pull request.
