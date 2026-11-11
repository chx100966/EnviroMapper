# EnviroMapper — local database

One PostgreSQL 17 + TimescaleDB server in Docker ([docker-compose.yml](../docker-compose.yml)),
running on your own machine, with two databases:

| Database | Owner role (password in `.env`) | Holds |
|---|---|---|
| `enviromapper_app` | `enviromapper_app` (`APP_DB_PASSWORD`) | users and roles, devices, alarm thresholds, alerts, reports, notifications |
| `enviromapper_telemetry` | `enviromapper_telemetry` (`TELEMETRY_DB_PASSWORD`) | sensor readings (TimescaleDB), detected anomalies, model results |

Keeping them apart means a service that only writes readings never gets access to user accounts.
The applications join data across the two in code, not in SQL.

## Start

You need Docker Desktop (on Windows with the WSL 2 backend).

```bash
cp .env.example .env        # then set the three passwords
docker compose up -d        # starts db (and the mqtt broker); first start creates both databases
docker compose ps           # wait for db to be "healthy"
```

Optional browser UI (Adminer) on http://localhost:8080 — server `db`, user and password of one of
the roles above:

```bash
docker compose --profile tools up -d
```

## Connecting

| From | Host | Example |
|---|---|---|
| your machine (IDE, notebooks, apps run outside Docker) | `localhost`, port `POSTGRES_PORT` (5432) | see below |
| another service in `docker-compose.yml` | `db`, port 5432 | `Host=db;...` |

```text
.NET (Npgsql):  Host=localhost;Port=5432;Database=enviromapper_app;Username=enviromapper_app;Password=<APP_DB_PASSWORD>
Python:         postgresql://enviromapper_telemetry:<TELEMETRY_DB_PASSWORD>@localhost:5432/enviromapper_telemetry
psql:           docker compose exec db psql -U enviromapper_telemetry -d enviromapper_telemetry
```

The port is bound to `127.0.0.1` only, so nobody else on your network can reach the database.

## Tables and migrations

[init/01-init.sh](init/01-init.sh) only creates the databases, the owner roles and the TimescaleDB
extension. The image runs it **once**, when the `pgdata` volume is empty, so tables never go there:

- `enviromapper_app` — EF Core migrations in the backend.
- `enviromapper_telemetry` — plain SQL files in [telemetry/migrations/](telemetry/migrations/)
  (hypertables and other TimescaleDB features are not something EF Core can express).

## Reset

```bash
docker compose down -v      # deletes the pgdata volume - ALL local data is gone
docker compose up -d        # recreated from scratch, init script runs again
```

Needed after changing `01-init.sh` or the passwords in `.env` (they are only read on the first start).

## Troubleshooting

- **`port is already allocated`** — something else uses 5432; set another `POSTGRES_PORT` in `.env`.
- **No databases after the first start, `bash\r: No such file or directory` in `docker compose logs db`**
  — the script has CRLF line endings. `.gitattributes` keeps `*.sh` as LF; if your copy predates it,
  delete `db/init/01-init.sh`, run `git checkout -- db/init/01-init.sh`, then reset as above.
- **`password authentication failed`** after editing `.env` — the volume still has the old passwords;
  reset, or change them with `ALTER ROLE ... PASSWORD`.
