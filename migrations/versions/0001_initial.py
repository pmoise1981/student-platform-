"""initial schema"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    from app.db import Base
    from app import models  # noqa
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)

def downgrade():
    from app.db import Base
    from app import models  # noqa
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
