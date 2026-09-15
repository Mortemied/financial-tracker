from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.extensions import db
from app.models import Category
from app.services.transactions import save_category, delete_category, ValidationError
from app.localization import translate
from .shared import categories, report_error

bp = Blueprint('categories', __name__, url_prefix='/categories')


@bp.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        try:
            save_category(request.form)
            flash(translate('saved'), 'success')
        except ValidationError as error:
            report_error(error)
        return redirect(url_for('categories.index'))
    return render_template('categories.html', active='categories', categories=categories())


@bp.post('/<int:category_id>/edit')
def edit(category_id):
    category = db.get_or_404(Category, category_id)
    try:
        save_category(request.form, category)
        flash(translate('saved'), 'success')
    except ValidationError as error:
        report_error(error)
    return redirect(url_for('categories.index'))


@bp.post('/<int:category_id>/delete')
def delete(category_id):
    category = db.get_or_404(Category, category_id)
    try:
        delete_category(category)
        flash(translate('deleted'), 'success')
    except ValidationError as error:
        report_error(error)
    return redirect(url_for('categories.index'))
