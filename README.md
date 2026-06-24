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
├── infra/            # Microsoft Azure — Bicep IaC
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
- Docker (optional)

### Backend
```bash
cd backend/src/EnviroMapper.API
dotnet restore
dotnet run
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### AI / IoT Simulator
```bash
cd ai
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python simulators/run_simulator.py --mode agriculture
```

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
