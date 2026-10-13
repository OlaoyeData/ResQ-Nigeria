"""Keep the citizen selected and AI detected incident types distinct."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from app.database import Base
from app import models  # noqa

revision = "0003_ai_reported_type"
down_revision = "0002_location_ai"
branch_labels = None
depends_on = None

def upgrade():
    bind=op.get_bind()
    Base.metadata.create_all(bind=bind)
    columns={c["name"] for c in inspect(bind).get_columns("incidents")}
    if "ai_incident_type" not in columns:
        op.add_column("incidents",sa.Column("ai_incident_type",sa.String(length=30),nullable=False,server_default="other"))

def downgrade():
    pass
