"""Pure analytics functions. Inputs are records; outputs contain numbers and translation keys."""
from collections import defaultdict
from datetime import timedelta


def summarize(records, start, end):
    selected = [r for r in records if start <= r.date <= end]
    income = sum(r.amount_cents for r in selected if r.type == 'income')
    expenses = sum(r.amount_cents for r in selected if r.type == 'expense')
    categories = defaultdict(int)
    months = defaultdict(lambda: {'income': 0, 'expense': 0})
    daily = defaultdict(int)
    for r in selected:
        months[r.date.strftime('%Y-%m')][r.type] += r.amount_cents
        if r.type == 'expense':
            categories[r.category_id] += r.amount_cents
            daily[r.date.isoformat()] += r.amount_cents
    biggest = max((r for r in selected if r.type == 'expense'), key=lambda r: r.amount_cents, default=None)
    ordered = sorted(categories.items(), key=lambda pair: pair[1], reverse=True)
    insights = []
    if income:
        insights.append({'key': 'insight.savings', 'params': {'percent': round((income-expenses)/income*100)}})
    if expenses > income:
        insights.append({'key': 'insight.deficit', 'params': {}})
    if not selected:
        insights.append({'key': 'insight.empty', 'params': {}})
    elif expenses and ordered:
        insights.append({'key': 'insight.top', 'params': {'percent': round(ordered[0][1]/expenses*100)},
                         'category_id': ordered[0][0]})
    day = start
    trend = []
    while day <= end:
        trend.append({'label': day.isoformat(), 'value': daily[day.isoformat()]})
        months[day.strftime('%Y-%m')]  # Include months without transactions.
        if day == end:
            break
        day += timedelta(days=1)
    return {'income': income, 'expenses': expenses, 'savings': income-expenses,
            'average': expenses // max(1, (end-start).days+1), 'biggest': biggest,
            'categories': ordered, 'months': dict(sorted(months.items())), 'trend': trend,
            'insights': insights, 'count': len(selected)}


def total_balance(records):
    return sum(r.amount_cents * (1 if r.type == 'income' else -1) for r in records)


def balance_history(records, start, end):
    balance = total_balance([r for r in records if r.date < start])
    changes = defaultdict(int)
    for r in records:
        if start <= r.date <= end:
            changes[r.date] += r.amount_cents * (1 if r.type == 'income' else -1)
    result, day = [], start
    while day <= end:
        balance += changes[day]
        result.append({'label': day.isoformat(), 'value': balance})
        if day == end:
            break
        day += timedelta(days=1)
    return result
