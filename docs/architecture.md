# Architecture

```text
Citizen browser ─┐                     ┌─ NIPOST postcode API
                ├─ React/Vite ─ FastAPI├─ Meta WhatsApp Cloud API
Operator browser┘              │      └─ AI provider boundary
                                └─ SQLAlchemy ─ SQLite (local) / PostgreSQL + PostGIS (Docker)
```

The API owns validation, incident state, assignment checks, audit records, and provider secrets. `Incident` stores the operational state and location metadata. `Dispatch` records the human-created assignment. AI and postcode provider boundaries are under `backend/app/services`. WhatsApp conversation state is persisted per sender. The browser refreshes operational views periodically and receives an SSE refresh signal. No provider output directly assigns resources.
