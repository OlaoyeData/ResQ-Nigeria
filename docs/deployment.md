# Deployment

Deploy the static Vite build to a static host and FastAPI as an ASGI service; use managed PostgreSQL/PostGIS for shared environments. Set `VITE_API_URL` at frontend build time. Configure backend `DATABASE_URL`, `JWT_SECRET`, CORS allow-list, and provider secrets using the deployment platform secret store. Run Alembic migrations as a release step; do not run seed data in production.

Use HTTPS, health checks at `/health`, backups, structured log collection without sensitive message/credential content, and a supported Python/Node runtime. The Docker Compose file is for local integration and not a production security profile. Establish operator provisioning, retention, and official response processes before real emergency use.
