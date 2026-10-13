# API overview

Interactive schemas: `/docs` and `/redoc`.

| Endpoint | Access | Purpose |
|---|---|---|
| `GET /health` | public | Dependency/provider mode status |
| `POST /api/v1/auth/login` | public | Operator OAuth2 password login; returns bearer JWT |
| `GET /api/v1/auth/me` | operator/admin | Current operator |
| `POST /api/v1/incidents` | public | Submit citizen report |
| `GET /api/v1/incidents/{code}` | public | Privacy-limited incident tracking |
| `GET /api/v1/incidents` | operator/admin | Internal incident queue |
| `GET /api/v1/incidents/{id}/detail` | operator/admin | Internal details and available units |
| `PATCH /api/v1/incidents/{id}/status` | operator/admin | Enforced lifecycle transition |
| `POST /api/v1/incidents/{id}/assign` | operator/admin | Human-confirmed assignment to a database-listed available unit |
| `/api/v1/response-units` | operator/admin | List and register units |
| `/api/v1/facilities` | operator/admin | List and register facilities |
| `GET /api/v1/postcodes/lookup?code=…` | public | Provider lookup |
| `GET/POST /api/v1/whatsapp/webhook` | public webhook | Meta verification and event ingestion |
| `GET /api/v1/analytics` | operator/admin | Aggregates from stored incidents |
| `GET /api/v1/notifications` | operator/admin | Internal notifications |
| `GET /api/v1/events` | public, refresh signal only | SSE heartbeat contains no incident or location data; refreshed API queries still require operator auth |

Standard entity routes return JSON; incident submit/queue/track use `{success,data,error}` envelopes. Operator routes require `Authorization: Bearer <token>`. Lifecycle errors are HTTP 409. Citizen tracking intentionally excludes precise location and contact details.
