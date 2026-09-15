"""Track goal updates without replacing existing goal values."""
from alembic import op
import sqlalchemy as sa

revision = '0003_release'
down_revision = '0002_v2'
branch_labels = depends_on = None


def upgrade():
    op.add_column('goal', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))
    op.execute('UPDATE goal SET updated_at = created_at WHERE updated_at IS NULL')


def downgrade():
    raise RuntimeError('Restore a backup instead of discarding schema history.')
