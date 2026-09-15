"""Persistence only: values are language independent; money is integer cents."""
from datetime import datetime, timezone
from decimal import Decimal
from app.extensions import db


def utc_now():
    return datetime.now(timezone.utc)


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=True)
    name = db.Column(db.String(80), nullable=True)
    type = db.Column(db.String(10), nullable=False)
    color = db.Column(db.String(7), nullable=False, default='#3984ff')
    __table_args__ = (
        db.CheckConstraint("type IN ('income','expense')"),
        db.CheckConstraint('(key IS NOT NULL) OR (name IS NOT NULL)'),
    )


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(10), nullable=False)
    amount_cents = db.Column(db.BigInteger, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id', ondelete='RESTRICT'), nullable=False)
    category = db.relationship('Category', lazy='joined')
    description = db.Column(db.String(250), nullable=False, default='')
    date = db.Column(db.Date, nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    deleted_at = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    __table_args__ = (
        db.CheckConstraint('amount_cents > 0'),
        db.CheckConstraint("type IN ('income','expense')"),
    )

    @property
    def amount(self):
        return Decimal(self.amount_cents) / 100


class Budget(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id', ondelete='RESTRICT'), nullable=False)
    category = db.relationship('Category', lazy='joined')
    month = db.Column(db.Date, nullable=False, index=True)
    amount_cents = db.Column(db.BigInteger, nullable=False)
    __table_args__ = (
        db.UniqueConstraint('category_id', 'month'),
        db.CheckConstraint('amount_cents > 0'),
    )


class Settings(db.Model):
    """Single local workspace preferences. Add owner_id for a future multi-user version."""
    id = db.Column(db.Integer, primary_key=True)
    language = db.Column(db.String(10), nullable=False, default='en')
    currency = db.Column(db.String(3), nullable=False, default='NOK')
    theme = db.Column(db.String(10), nullable=False, default='light')


class Goal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    target_cents = db.Column(db.BigInteger, nullable=False)
    current_cents = db.Column(db.BigInteger, nullable=False, default=0)
    currency = db.Column(db.String(3), nullable=False)
    target_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    __table_args__ = (db.CheckConstraint('target_cents > 0'), db.CheckConstraint('current_cents >= 0'))


class ImportBatch(db.Model):
    id = db.Column(db.String(64), primary_key=True)
    payload = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    completed_at = db.Column(db.DateTime)
