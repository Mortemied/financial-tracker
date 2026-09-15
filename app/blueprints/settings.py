from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, g
from app.services.preferences import save_settings
from app.services.transactions import ValidationError
from app.localization import translate
from .shared import report_error

bp = Blueprint('settings', __name__, url_prefix='/settings')


@bp.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        try:
            g.settings = save_settings(request.form, current_app.config['LANGUAGES'], current_app.config['CURRENCIES'])
            flash(translate('saved'), 'success')
        except ValidationError as error:
            report_error(error)
        # Only local absolute paths are valid return locations.
        target = request.form.get('next', '')
        if not target.startswith('/') or target.startswith('//') or '\\' in target:
            target = url_for('settings.index')
        return redirect(target)
    return render_template('settings.html', active='settings')
