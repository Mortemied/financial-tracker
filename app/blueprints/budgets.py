from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.extensions import db
from app.models import Budget
from app.services.budgets import save_budget, budget_progress
from app.services.periods import month_period
from app.services.transactions import ValidationError
from app.localization import translate
from .shared import categories, report_error

bp = Blueprint('budgets', __name__, url_prefix='/budgets')


@bp.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        try:
            budget = save_budget(request.form)
            flash(translate('saved'), 'success')
            return redirect(url_for('budgets.index', month=budget.month.strftime('%Y-%m')))
        except ValidationError as error:
            report_error(error)
            return redirect(url_for('budgets.index'))
    try:
        start, end = month_period(request.args.get('month'))
    except ValidationError as error:
        report_error(error)
        return redirect(url_for('budgets.index'))
    rows = budget_progress(start, end)
    return render_template('budgets.html', active='budgets', rows=rows,
                           categories=[c for c in categories() if c.type == 'expense'], month=start.strftime('%Y-%m'),
                           allocated=sum(r['budget'].amount_cents for r in rows), spent=sum(r['spent'] for r in rows))


@bp.post('/<int:budget_id>/delete')
def delete(budget_id):
    budget = db.get_or_404(Budget, budget_id)
    month = budget.month.strftime('%Y-%m')
    db.session.delete(budget)
    db.session.commit()
    flash(translate('deleted'), 'success')
    return redirect(url_for('budgets.index', month=month))


@bp.route('/copy',methods=['GET','POST'])
def copy():
    from app.services.budgets import preview_budget_copy, copy_previous_budgets
    month = request.values.get('month')
    try:
        start, _ = month_period(month)
        month = start.strftime('%Y-%m')
        if request.method == 'POST':
            if request.form.get('confirmed') != 'yes':
                raise ValidationError('error.confirm')
            count = copy_previous_budgets(month)
            flash(translate('budget.copied',count=count),'success')
            return redirect(url_for('budgets.index',month=month))
        return render_template('budget_copy.html',active='budgets',month=month,rows=preview_budget_copy(month))
    except ValidationError as error:
        report_error(error)
        return redirect(url_for('budgets.index'))
