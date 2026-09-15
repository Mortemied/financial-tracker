from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for
from app.analytics import summarize, total_balance, balance_history
from app.services.periods import month_period, shift_month
from app.services.transactions import ValidationError
from .shared import records, chart_payload, report_error

bp = Blueprint('dashboard', __name__)


@bp.get('/')
def index():
    try:
        start, end = month_period(request.args.get('month'))
    except ValidationError as error:
        report_error(error)
        return redirect(url_for('dashboard.index'))
    rows = records()
    from app.analytics.monthly import month_summary
    from app.services.budgets import budget_progress
    monthly = month_summary(rows,start,end)
    alerts = [row for row in budget_progress(start,end) if row['status'] != 'normal']
    current = monthly['totals']
    chart_start = shift_month(start, -5)
    charts = chart_payload(summarize(rows, chart_start, end), balance_history(rows, chart_start, end))
    charts['breakdown'] = chart_payload(current)['breakdown']
    recent = sorted([r for r in rows if start <= r.date <= end], key=lambda r: (r.date, r.id), reverse=True)[:5]
    return render_template('dashboard.html', active='dashboard', summary=current,
                           balance=total_balance([r for r in rows if r.date <= date.today()]),
                           recent=recent, chart_data=charts, month=start.strftime('%Y-%m'), start=start, end=end,
                           monthly=monthly, alerts=alerts)
