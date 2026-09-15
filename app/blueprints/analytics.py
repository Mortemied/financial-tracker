from flask import Blueprint, render_template, request, redirect, url_for
from app.analytics import summarize
from app.services.periods import resolve_period
from app.services.transactions import ValidationError
from .shared import records, categories, chart_payload, report_error

bp = Blueprint('analytics', __name__, url_prefix='/analytics')


@bp.get('/')
def index():
    try:
        start, end = resolve_period(request.args)
    except ValidationError as error:
        report_error(error)
        return redirect(url_for('analytics.index'))
    summary = summarize(records(), start, end)
    return render_template('analytics.html', active='analytics', summary=summary,
                           category_map={c.id: c for c in categories()}, chart_data=chart_payload(summary), start=start, end=end)
