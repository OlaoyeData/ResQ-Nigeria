# Database

SQLAlchemy models are defined in `backend/app/models.py`; Alembic is the migration runner. Models cover organizations, users/operators, incidents, incident messages and locations, postcode verifications, AI assessments, response units, facilities, dispatches, WhatsApp contacts/messages, audit logs, and notifications. UUID strings are used as entity identifiers. Indexes support incident type/status/time, postcode, coordinates, unit status, and audit/message lookup.

Local default is SQLite. Docker runs PostgreSQL 16 with PostGIS. Portable coordinate columns are indexed latitude and longitude; geography columns and GIS functions are not yet used. Run `alembic upgrade head`; create demo content with `python -m app.seed`.
