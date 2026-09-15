from calendar import monthrange
from datetime import date
from app.services.transactions import parse_date, ValidationError


def shift_month(day, offset):
    total = day.year * 12 + day.month - 1 + offset
    year, month = divmod(total, 12)
    return date(year, month + 1, 1)


def month_end(day):
    return day.replace(day=monthrange(day.year, day.month)[1])


def month_period(value=None):
    if value:
        try:
            start = date.fromisoformat(value + '-01')
            if start.year < 2:
                raise ValueError
        except (TypeError, ValueError):
            raise ValidationError('error.date') from None
    else:
        start = date.today().replace(day=1)
    return start, month_end(start)


def resolve_period(filters, today=None):
    today = today or date.today()
    month = today.replace(day=1)
    period = filters.get('period', 'this_month')
    if period == 'custom':
        start, end = parse_date(filters.get('start')), parse_date(filters.get('end'))
    elif period == 'last_month':
        start = shift_month(month, -1)
        end = month_end(start)
    elif period in ('last_3', 'last_6'):
        start, end = shift_month(month, -2 if period == 'last_3' else -5), today
    elif period == 'this_year':
        start, end = date(today.year, 1, 1), today
    elif period == 'this_month':
        start, end = month, today
    else:
        raise ValidationError('error.range')
    if start > end or (end-start).days > 3660:
        raise ValidationError('error.range')
    return start, end
