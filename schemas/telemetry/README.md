# Telemetry message format — version 1

Every device (and the simulator in `ai/simulators/`) publishes its readings to the MQTT broker as
JSON messages described by [v1.schema.json](v1.schema.json) (JSON Schema 2020-12). The same file is
the contract for everything that reads them: the ingest service, the backend API and the frontend. [examples/](examples/) has one valid message per mode.

```json
{
  "schemaVersion": 1,
  "messageId": "6f1c2a8e-3b4d-4e5f-9a7b-1c2d3e4f5a6b",
  "deviceId": "sim-agriculture-01",
  "mode": "agriculture",
  "timestamp": "2026-11-06T20:15:30.123Z",
  "readings": { "soil_moisture": 41.27, "temperature": 12.4, "humidity": 78.9 }
}
```

One message carries **all readings a device took at one moment** (one simulator tick).

## Fields

| Field | Type | Rules |
|---|---|---|
| `schemaVersion` | integer | Always `1` for this schema. |
| `messageId` | string | Random lowercase UUID, new for every message. A retried send keeps its ID, so consumers can drop duplicates (QoS 1 delivers at least once). |
| `deviceId` | string | The device ID, e.g. `sim-agriculture-01` (`a-z 0-9 . _ : -`, up to 128 characters). Also the device's MQTT client ID; must equal the `<deviceId>` level of the topic. |
| `mode` | string | `agriculture`, `industry` or `weather`. Must equal the `<mode>` level of the topic. |
| `timestamp` | string | When the readings were taken, by the device clock: RFC 3339 in UTC with `Z`, up to microseconds (`2026-11-06T20:15:30.123Z`). Not the time the message was received. |
| `readings` | object | Sensor → number, in the unit from the table below. Only the sensors of the device's mode; at least one. A sensor that failed to read is left out — never sent as `null` or a placeholder value. |

No other fields are allowed.

## Readings per mode

| Mode | Key | Quantity | Unit | Measuring range |
|---|---|---|---|---|
| `agriculture` | `soil_moisture` | volumetric soil moisture | % | 0 – 100 |
| | `temperature` | air temperature at the crop | °C | −40 – 60 |
| | `humidity` | relative air humidity | % | 0 – 100 |
| `industry` | `vibration` | vibration velocity (RMS) | mm/s | 0 – 100 |
| | `temperature` | machine (bearing/housing) temperature | °C | −40 – 200 |
| | `pressure` | process pressure (gauge) | bar | 0 – 25 |
| `weather` | `temperature` | air temperature | °C | −50 – 60 |
| | `pressure` | atmospheric pressure at sea level | hPa | 850 – 1100 |
| | `wind_speed` | mean wind speed | km/h | 0 – 300 |

Units are fixed per sensor and are not sent; the schema records them in the `x-unit` annotation of
each reading, so code can read them from there.

The **measuring range** is what the sensor can physically report. A value outside it is a sensor
fault, and the message fails validation. A value inside the range but outside the usual operating
values (a hot bearing, a storm) is valid — finding those is the job of anomaly detection, not of
the schema.

## Sending a message

- Topic: `enviromapper/telemetry/<mode>/<deviceId>`, e.g.
  `enviromapper/telemetry/agriculture/sim-agriculture-01`. Consumers subscribe to
  `enviromapper/telemetry/#`, or to one mode with `enviromapper/telemetry/<mode>/+`.
- Payload: the JSON above, UTF-8, compact (`json.dumps(body, separators=(",", ":"))`).
- QoS 1 (at least once); not retained.

**Size:** a version 1 message is about 300 bytes. One message holds a whole tick, units are not
repeated in every message, and the device location is not part of the telemetry — it belongs to the
device's record in the database, not to every reading.

## Where messages are validated

| Where | What | A message that fails |
|---|---|---|
| Device / simulator tests | the whole schema | doesn't ship |
| Ingest service (subscriber) | the whole schema, `deviceId` and `mode` = the topic levels | is logged and not stored |

## Versioning

- **Compatible additions** — a new optional field, a new sensor, a new mode — change this file
  without changing `schemaVersion`. Validators are updated first, devices after them.
- **Anything else** — renaming or removing a field, changing a type, a unit or a measuring range so
  that old messages would be read wrongly — is a new version: `v2.schema.json` with
  `"schemaVersion": 2`, and consumers accept each version they know until no device sends the old
  one.

## Validating a message

```python
import json
from jsonschema import Draft202012Validator, FormatChecker  # pip install jsonschema rfc3339-validator

schema = json.load(open("schemas/telemetry/v1.schema.json"))
validator = Draft202012Validator(schema, format_checker=FormatChecker())
for error in validator.iter_errors(json.load(open("schemas/telemetry/examples/weather.json"))):
    print(error.json_path, error.message)
```

`rfc3339-validator` makes `FormatChecker` check `date-time`; without it only the pattern applies.
