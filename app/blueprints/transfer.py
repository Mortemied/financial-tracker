from flask import Blueprint, render_template, request, Response, redirect, url_for
from app.extensions import db
from app.services.transactions import transaction_query, ValidationError
from app.services.csv_transfer import export_csv
from app.localization import category_label
from .shared import report_error

bp = Blueprint('transfer', __name__, url_prefix='/export')


@bp.get('/')
def index():
    return render_template('export.html', active='transfer')


@bp.get('/download')
def download():
    try:
        rows = db.session.scalars(transaction_query(request.args)).all()
    except ValidationError as error:
        report_error(error)
        return redirect(url_for('transfer.index'))
    return Response(export_csv(rows, category_label), content_type='text/csv; charset=utf-8',
                    headers={'Content-Disposition': 'attachment; filename="financial-tracker.csv"'})
