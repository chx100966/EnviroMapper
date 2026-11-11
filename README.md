# EnviroMapper

**Design and implementation of an IoT device management system with an AI-based analytics module**

Engineering Diploma Project — Computer Science, Cloud Developer  
WSB Merito University Chorzów / Katowice

| | |
|---|---|
| **Supervisor** | Dr. Inż. Mariusz Mol |
| **Team** | Bezrąk Patrycja · Grad-Drzewiecki Olaf · Gajowski Rafał |
| **Tech stack** | C# .NET · React · Python · PyTorch · Microsoft Azure |

---

## Overview

EnviroMapper is a scalable IoT system that collects sensor data, analyses it using AI, and supports users in operational decision-making through reports and notifications.

The system supports three operating modes:

| Mode | Description |
|------|-------------|
| **Agriculture** | Soil conditions, humidity, crop temperature monitoring |
| **Industry / UR** | Machine monitoring, anomaly detection, failure prediction |
| **Weather** | Meteorological stations, atmospheric trend analysis |

---

## Architecture

```
EnviroMapper/
├── backend/          # C# .NET 8 Web API
├── frontend/         # React + TypeScript SPA
├── ai/               # Python / PyTorch — AI models, IoT simulators
├── infra/            # Microsoft Azure — OpenTofu IaC (see infra/terraform/README.md)
├── schemas/          # Shared data contracts, e.g. the telemetry message format (schemas/telemetry/)
├── db/               # Local PostgreSQL + TimescaleDB: init script, migrations (see db/README.md)
└── docs/             # Documentation, mockups, diagrams
```

Key Azure components:
- **Azure IoT Hub** — device / simulator data ingestion
- **Azure SQL / CosmosDB** — sensor data storage
- **Azure Functions** — near-real-time event processing
- **Azure App Service** — API and frontend hosting

---

## Quick start

### Prerequisites
- .NET 8 SDK
- Node.js 20+
- Python 3.11+
- Azure CLI
- OpenTofu 1.11+ (infrastructure only)
- Docker (optional)

`backend/` and `frontend/` are still empty; run instructions come with the first code in each
module. `ai/` has the IoT device simulator ([ai/README.md](ai/README.md)), and the infrastructure is
described in [infra/terraform/README.md](infra/terraform/README.md).

Local database (PostgreSQL + TimescaleDB in Docker): `cp .env.example .env`, set the passwords,
then `docker compose up -d`. Details in [db/README.md](db/README.md).

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for commit conventions, branch strategy, and PR guidelines.

---

## Project phases

- [x] Phase 1 — Analysis & Design
- [ ] Phase 2 — Data ingestion (IoT Hub + Simulator)
- [ ] Phase 3 — AI & Data Analysis
- [ ] Phase 4 — Web Application Development

---

## License

Academic project — all rights reserved by the authors.
