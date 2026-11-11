#!/usr/bin/env bash
# Creates the two EnviroMapper databases and their owner roles.
#
# The Postgres image runs this once, on the first start of the db container with an empty pgdata
# volume (docker-entrypoint-initdb.d), after the image's own TimescaleDB scripts. It never runs
# again, so it holds no tables: those come from migrations (backend EF Core for enviromapper_app,
# db/telemetry/migrations for enviromapper_telemetry). See db/README.md.
# No `set -u`: when the file is not executable the image sources it into its own entrypoint,
# and the option would stay on there. docker-compose.yml already refuses to start without the
# password variables.
set -eo pipefail

# Passwords go in as psql variables (:'name' quotes them), never pasted into the SQL text.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
  -v app_password="$APP_DB_PASSWORD" \
  -v telemetry_password="$TELEMETRY_DB_PASSWORD" <<'SQL'
-- Users, devices, alarm thresholds, alerts, reports, notifications.
CREATE ROLE enviromapper_app LOGIN PASSWORD :'app_password';
CREATE DATABASE enviromapper_app OWNER enviromapper_app;
REVOKE ALL ON DATABASE enviromapper_app FROM PUBLIC;

-- Sensor readings, detected anomalies, model results (TimescaleDB).
CREATE ROLE enviromapper_telemetry LOGIN PASSWORD :'telemetry_password';
CREATE DATABASE enviromapper_telemetry OWNER enviromapper_telemetry;
REVOKE ALL ON DATABASE enviromapper_telemetry FROM PUBLIC;
SQL

# The image installs TimescaleDB into template1, so every new database starts with it.
# Only the telemetry database needs it; IF [NOT] EXISTS keeps this right either way.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname enviromapper_telemetry <<'SQL'
CREATE EXTENSION IF NOT EXISTS timescaledb;
SQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname enviromapper_app <<'SQL'
DROP EXTENSION IF EXISTS timescaledb;
SQL
