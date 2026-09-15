"""Recoverable transaction deletion, savings goals and reviewed CSV batches."""
from alembic import op
import sqlalchemy as sa

revision = '0002_v2'
down_revision = '0001_v1'
branch_labels = depends_on = None


def upgrade():
    op.add_column('transaction',sa.Column('deleted_at',sa.DateTime(timezone=True),nullable=True))
    op.create_index('ix_transaction_deleted_at','transaction',['deleted_at'])
    op.create_table('goal',sa.Column('id',sa.Integer,primary_key=True),sa.Column('name',sa.String(80),nullable=False),sa.Column('target_cents',sa.BigInteger,nullable=False),sa.Column('current_cents',sa.BigInteger,nullable=False,server_default='0'),sa.Column('currency',sa.String(3),nullable=False),sa.Column('target_date',sa.Date),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.CheckConstraint('target_cents > 0'),sa.CheckConstraint('current_cents >= 0'))
    op.create_table('import_batch',sa.Column('id',sa.String(64),primary_key=True),sa.Column('payload',sa.Text,nullable=False),sa.Column('created_at',sa.DateTime,nullable=False),sa.Column('completed_at',sa.DateTime))


def downgrade():
    raise RuntimeError('Downgrade would discard goals and undo history. Restore a backup instead.')
