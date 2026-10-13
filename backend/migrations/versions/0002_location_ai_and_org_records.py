"""Add normalized organization, location, postcode, and AI assessment records."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from app.database import Base
from app import models  # noqa

revision = "0002_location_ai"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

def upgrade():
    bind=op.get_bind()
    Base.metadata.create_all(bind=bind)
    columns={c["name"] for c in inspect(bind).get_columns("incidents")}
    if "location_confidence" not in columns:
        op.add_column("incidents",sa.Column("location_confidence",sa.Float(),nullable=False,server_default="0"))

def downgrade():
    # Retain audit-sensitive data by default; schema rollback is intentionally manual.
    pass
