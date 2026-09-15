from app.extensions import db
from app.models import Goal
from app.services.transactions import parse_money, parse_date, ValidationError


def save_goal(data, currencies, goal=None):
    name = data.get('name','').strip()
    if not name or len(name) > 80:
        raise ValidationError('error.goal_name')
    if data.get('currency') not in currencies:
        raise ValidationError('error.settings')
    target = parse_money(data.get('target_amount'))
    raw = str(data.get('current_amount','0')).strip()
    current = 0 if raw in ('0','0.00','0,00','') else parse_money(raw)
    target_date = parse_date(data['target_date']) if data.get('target_date') else None
    goal = goal or Goal()
    goal.name, goal.target_cents, goal.current_cents = name, target, current
    goal.currency, goal.target_date = data['currency'], target_date
    db.session.add(goal)
    db.session.commit()
    return goal


def add_money(goal, value):
    cents = parse_money(value)
    if goal.current_cents + cents > 99999999999:
        raise ValidationError('error.amount')
    goal.current_cents += cents
    db.session.commit()


def goal_progress(goal):
    return {'goal':goal, 'percent':round(goal.current_cents/goal.target_cents*100),
            'remaining':max(0,goal.target_cents-goal.current_cents)}
