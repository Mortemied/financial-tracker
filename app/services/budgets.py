from app.extensions import db
from app.models import Budget, Transaction
from app.services.transactions import category_by_id, parse_money, ValidationError
from app.services.periods import month_period


def save_budget(data):
    category = category_by_id(data.get('category_id'))
    if category.type != 'expense':
        raise ValidationError('error.category_type')
    start, _ = month_period(data.get('month'))
    amount = parse_money(data.get('amount'))
    budget = db.session.scalar(db.select(Budget).where(Budget.category_id == category.id, Budget.month == start))
    budget = budget or Budget(category_id=category.id, month=start)
    budget.amount_cents = amount
    db.session.add(budget)
    db.session.commit()
    return budget


def budget_progress(start, end):
    budgets = db.session.scalars(db.select(Budget).where(Budget.month == start).order_by(Budget.id)).all()
    spent = dict(db.session.execute(db.select(Transaction.category_id, db.func.sum(Transaction.amount_cents))
                 .where(Transaction.deleted_at.is_(None), Transaction.type == 'expense', Transaction.date >= start, Transaction.date <= end)
                 .group_by(Transaction.category_id)).all())
    result = []
    for budget in budgets:
        value = spent.get(budget.category_id, 0)
        percent = round(value/budget.amount_cents*100)
        status = 'over_budget' if value > budget.amount_cents else ('warning' if value * 100 >= budget.amount_cents * 80 else 'normal')
        result.append({'budget': budget, 'spent': value, 'percent': percent, 'status': status})
    return result


def preview_budget_copy(month):
    from app.services.periods import shift_month
    start, _ = month_period(month)
    previous = shift_month(start,-1)
    existing = set(db.session.scalars(db.select(Budget.category_id).where(Budget.month == start)))
    source = db.session.scalars(db.select(Budget).where(Budget.month == previous)).all()
    return [{'budget':b,'skip':b.category_id in existing} for b in source]


def copy_previous_budgets(month):
    start, _ = month_period(month)
    rows = preview_budget_copy(month)
    count = 0
    for row in rows:
        if not row['skip']:
            b = row['budget']
            db.session.add(Budget(category_id=b.category_id,month=start,amount_cents=b.amount_cents))
            count += 1
    db.session.commit()
    return count
