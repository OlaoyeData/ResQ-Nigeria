# ResQ Nigeria

ResQ Nigeria is a portfolio prototype for emergency response coordination. A person can describe an emergency in their own words and provide a location. ResQ suggests an incident category and urgency, then helps an operator review the report and suitable demo response units.

The homepage includes an animated, interactive WhatsApp-style conversation preview. It demonstrates a free-text report, NIPOST digital postcode, and nearby demo team suggestion.

> **Demo only:** ResQ does not contact WhatsApp, NIPOST, emergency services, or real responders. Sample locations, reports, and response units are illustrative. This prototype is not an emergency service. For an immediate emergency, contact the appropriate official service directly.

## What’s included

- Public emergency report form with free-text descriptions, optional browser location, postcode, and incident tracking.
- Automated demo triage suggestions for incident type and urgency, with operator review in the command centre.
- NIPOST postcode lookup adapter and a clearly identified synthetic postcode fixture for demonstrations.
- Operator dashboard for reviewing incidents, demo units, facilities, maps, history, and analytics.
- FastAPI REST API with interactive documentation at `/docs`.
- Simulated WhatsApp flow and mock AI provider for local demos without third-party credentials.
- SQLite for local development; PostgreSQL support for hosted deployments.

## Technology

- Frontend: React, TypeScript, Vite, and React Router
- Backend: Python, FastAPI, SQLAlchemy, and Alembic
- Database: SQLite locally or PostgreSQL (including Supabase) when hosted
- Maps: Leaflet and OpenStreetMap tiles

## Run locally on Windows

Requirements: Python 3.11 or later and Node.js 20.19 or later.

### 1. Configure the backend

From the repository root in PowerShell:

```powershell
Copy-Item .env.example backend/.env
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
python -m app.seed
```

The seed command creates sample incidents, response units, and a local demo operator. The local demo login is `operator@resq.demo` with password `ResQ-demo-2026!change`.

### 2. Start the API

In the same `backend` terminal:

```powershell
uvicorn app.main:app --reload
```

The API runs at [http://localhost:8000](http://localhost:8000); its interactive API reference is [http://localhost:8000/docs](http://localhost:8000/docs).

### 3. Start the frontend

Open a second PowerShell terminal at the repository root:

```powershell
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). The frontend uses `http://localhost:8000` by default. Keep the API terminal running while using the report, tracking, and operator pages.

## Demo postcode

The synthetic postcode `FC 02 A09 DB 09` demonstrates how the interface can resolve a location and suggest a nearby demo team. It is a fixture for this prototype, not a verified real NIPOST address. See [NIPOST integration notes](docs/nipost-integration.md) for details.

## Deploy to Vercel

The frontend and API are deployed as separate Vercel projects from the same repository. The backend requires a persistent PostgreSQL database; SQLite is intended for local use. Supabase PostgreSQL can be used as the database.

Follow the step-by-step [Vercel deployment guide](docs/deploy-vercel.md) to configure the projects, set environment variables, run migrations, and seed the demo data. Do not commit `.env` files, database connection strings, provider tokens, or private demo credentials.

## Configuration

Copy `.env.example` to `backend/.env` for local development. The defaults use SQLite and mock providers, so no AI, NIPOST, or Meta credentials are needed for the local demo. Provider credentials belong only in the backend environment. Configure a unique `JWT_SECRET` and a new private demo operator password before hosting the command centre.

## Documentation

- [Architecture](docs/architecture.md)
- [API endpoints](docs/api.md)
- [AI behavior and limitations](docs/ai.md)
- [Database and migrations](docs/database.md)
- [Deployment overview](docs/deployment.md)
- [Vercel deployment steps](docs/deploy-vercel.md)
- [NIPOST integration](docs/nipost-integration.md)
- [Security and privacy](docs/security.md)
- [WhatsApp integration](docs/whatsapp.md)

## Current limitations

- AI, NIPOST, and WhatsApp integrations use mock/demo behavior unless real provider credentials and approved configurations are supplied.
- The homepage WhatsApp-style chat is a browser simulation. It does not send or receive real WhatsApp messages.
- A suggested team or operator assignment is not a confirmed real-world dispatch.
- Demo coordinates and sample incident records are not operational data.
- Before any real-world use, the project needs verified agency data, approved emergency workflows, privacy and security review, and tested service integrations.
