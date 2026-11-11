"""Foundation schema, scoped policies and immutable evidence.

Schema snapshot is deliberately versioned separately from live ORM models.
"""
from pathlib import Path
from alembic import op

revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    folder = Path(__file__).parent
    for filename in ("0001_schema.sql", "0001_security.sql"):
        op.get_bind().exec_driver_sql((folder / filename).read_text(encoding="utf-8"))


def downgrade():
    raise RuntimeError("Destructive foundation downgrade disabled. Restore a verified backup instead.")

