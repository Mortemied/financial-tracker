"""Adopt the original v1 schema without rewriting existing data."""
from alembic import op
import sqlalchemy as sa

revision = '0001_v1'
down_revision = None
branch_labels = depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    expected = {'category': {'id','key','name','type','color'},
                'transaction': {'id','type','amount_cents','category_id','description','date','created_at','updated_at'},
                'budget': {'id','category_id','month','amount_cents'},
                'settings': {'id','language','currency','theme'}}
    existing = set(inspector.get_table_names()) - {'alembic_version'}
    if existing:
        for table, columns in expected.items():
            if table not in existing or not columns <= {c['name'] for c in inspector.get_columns(table)}:
                raise RuntimeError('Unrecognized database schema. Original database was not modified.')
        return
    op.create_table('category', sa.Column('id',sa.Integer,primary_key=True),sa.Column('key',sa.String(50),unique=True),sa.Column('name',sa.String(80)),sa.Column('type',sa.String(10),nullable=False),sa.Column('color',sa.String(7),nullable=False),sa.CheckConstraint("type IN ('income','expense')"),sa.CheckConstraint('(key IS NOT NULL) OR (name IS NOT NULL)'))
    op.create_table('transaction',sa.Column('id',sa.Integer,primary_key=True),sa.Column('type',sa.String(10),nullable=False),sa.Column('amount_cents',sa.BigInteger,nullable=False),sa.Column('category_id',sa.Integer,sa.ForeignKey('category.id',ondelete='RESTRICT'),nullable=False),sa.Column('description',sa.String(250),nullable=False),sa.Column('date',sa.Date,nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),sa.CheckConstraint('amount_cents > 0'),sa.CheckConstraint("type IN ('income','expense')"))
    op.create_index('ix_transaction_date','transaction',['date'])
    op.create_table('budget',sa.Column('id',sa.Integer,primary_key=True),sa.Column('category_id',sa.Integer,sa.ForeignKey('category.id',ondelete='RESTRICT'),nullable=False),sa.Column('month',sa.Date,nullable=False),sa.Column('amount_cents',sa.BigInteger,nullable=False),sa.UniqueConstraint('category_id','month'),sa.CheckConstraint('amount_cents > 0'))
    op.create_index('ix_budget_month','budget',['month'])
    op.create_table('settings',sa.Column('id',sa.Integer,primary_key=True),sa.Column('language',sa.String(10),nullable=False),sa.Column('currency',sa.String(3),nullable=False),sa.Column('theme',sa.String(10),nullable=False))


def downgrade():
    raise RuntimeError('Destructive downgrade is disabled. Restore a verified backup instead.')
