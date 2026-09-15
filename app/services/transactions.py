from datetime import date
from decimal import Decimal, InvalidOperation
from sqlalchemy import func
from app.extensions import db
from app.models import Transaction, Category, Budget


class ValidationError(ValueError):
    def __init__(self, key, **params):
        self.key, self.params = key, params
        super().__init__(key)


def parse_money(value):
    try:
        amount = Decimal(str(value).strip().replace(',', '.'))
        if not amount.is_finite() or amount <= 0 or amount > Decimal('999999999.99'):
            raise InvalidOperation
        if amount * 100 != (amount * 100).to_integral_value():
            raise InvalidOperation
        return int(amount * 100)
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError('error.amount') from None


def parse_date(value):
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        raise ValidationError('error.date') from None


def category_by_id(value):
    try:
        category = db.session.get(Category, int(value))
    except (ValueError, TypeError):
        category = None
    if category is None:
        raise ValidationError('error.category')
    return category


def validate_transaction(data):
    kind = data.get('type')
    if kind not in ('income', 'expense'):
        raise ValidationError('error.type')
    category = category_by_id(data.get('category_id'))
    if category.type != kind:
        raise ValidationError('error.category_type')
    description = data.get('description', '').strip()
    if len(description) > 250:
        raise ValidationError('error.description')
    return dict(type=kind, amount_cents=parse_money(data.get('amount')),
                category_id=category.id, description=description, date=parse_date(data.get('date')))


def save_transaction(data, transaction=None):
    values = validate_transaction(data)
    transaction = transaction or Transaction()
    for name, value in values.items():
        setattr(transaction, name, value)
    db.session.add(transaction)
    db.session.commit()
    return transaction


def transaction_query(filters):
    query = db.select(Transaction).where(Transaction.deleted_at.is_(None))
    if filters.get('q'):
        # Escape wildcard characters; search is literal and case-insensitive.
        term = filters['q'].strip().casefold().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        query = query.where(func.unicode_casefold(Transaction.description).like(f'%{term}%', escape='\\'))
    if filters.get('type'):
        if filters['type'] not in ('income', 'expense'):
            raise ValidationError('error.type')
        query = query.where(Transaction.type == filters['type'])
    if filters.get('category_id'):
        query = query.where(Transaction.category_id == category_by_id(filters['category_id']).id)
    start = parse_date(filters['start']) if filters.get('start') else None
    end = parse_date(filters['end']) if filters.get('end') else None
    if start and end and start > end:
        raise ValidationError('error.range')
    if start:
        query = query.where(Transaction.date >= start)
    if end:
        query = query.where(Transaction.date <= end)
    sorts = {'newest': Transaction.date.desc(), 'oldest': Transaction.date.asc(),
             'highest': Transaction.amount_cents.desc(), 'lowest': Transaction.amount_cents.asc()}
    return query.order_by(sorts.get(filters.get('sort'), sorts['newest']), Transaction.id.desc())


def save_category(data, category=None):
    name = data.get('name', '').strip()
    kind = data.get('type')
    if not name or len(name) > 80:
        raise ValidationError('error.category_name')
    if kind not in ('income', 'expense'):
        raise ValidationError('error.type')
    if category and category.key:
        raise ValidationError('error.system_category')
    duplicate = db.session.scalar(db.select(Category).where(func.unicode_casefold(Category.name) == name.casefold()))
    if duplicate and (not category or category.id != duplicate.id):
        raise ValidationError('error.duplicate')
    if category and category.type != kind and category_in_use(category):
        raise ValidationError('error.category_used')
    category = category or Category()
    category.name, category.type = name, kind
    db.session.add(category)
    db.session.commit()
    return category


def category_in_use(category):
    return (db.session.scalar(db.select(Transaction.id).where(Transaction.category_id == category.id).limit(1))
            or db.session.scalar(db.select(Budget.id).where(Budget.category_id == category.id).limit(1)))


def delete_category(category):
    if category.key:
        raise ValidationError('error.system_category')
    if category_in_use(category):
        raise ValidationError('error.category_used')
    db.session.delete(category)
    db.session.commit()
