from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from app.extensions import db
from app.models import Goal
from app.services.goals import save_goal, add_money, goal_progress
from app.services.transactions import ValidationError
from app.localization import translate
from .shared import report_error

bp = Blueprint('goals',__name__,url_prefix='/goals')


@bp.get('/')
def index():
    rows = db.session.scalars(db.select(Goal).order_by(Goal.created_at.desc())).all()
    return render_template('goals.html',active='goals',rows=[goal_progress(g) for g in rows])


@bp.route('/new',methods=['GET','POST'])
@bp.route('/<int:goal_id>/edit',methods=['GET','POST'])
def edit(goal_id=None):
    goal = db.get_or_404(Goal,goal_id) if goal_id else None
    values = request.form if request.method == 'POST' else {}
    if request.method == 'POST':
        try:
            save_goal(request.form,current_app.config['CURRENCIES'],goal)
            flash(translate('saved'),'success')
            return redirect(url_for('goals.index'))
        except ValidationError as error:
            report_error(error)
            return render_template('goal_form.html',active='goals',goal=goal,values=values),422
    return render_template('goal_form.html',active='goals',goal=goal,values=values)


@bp.post('/<int:goal_id>/add')
def add(goal_id):
    try:
        add_money(db.get_or_404(Goal,goal_id),request.form.get('amount'))
        flash(translate('saved'),'success')
    except ValidationError as error:
        report_error(error)
    return redirect(url_for('goals.index'))


@bp.post('/<int:goal_id>/delete')
def delete(goal_id):
    db.session.delete(db.get_or_404(Goal,goal_id))
    db.session.commit()
    flash(translate('deleted'),'success')
    return redirect(url_for('goals.index'))
