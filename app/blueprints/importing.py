from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort
from app.extensions import db
from app.models import ImportBatch
from app.services.importing import create_batch, review_batch, commit_batch
from app.services.transactions import ValidationError
from app.localization import translate
from .shared import report_error

bp = Blueprint('importing',__name__,url_prefix='/import')


def owned_batch(batch_id):
    if batch_id not in session.get('import_batches',[]):
        abort(404)
    return db.get_or_404(ImportBatch,batch_id)


@bp.route('/',methods=['GET','POST'])
def index():
    if request.method == 'POST':
        try:
            upload = request.files.get('csv')
            if not upload:
                raise ValidationError('error.csv_empty')
            batch = create_batch(upload.read(2*1024*1024+1))
            session['import_batches'] = (session.get('import_batches',[])+[batch.id])[-10:]
            return redirect(url_for('importing.preview',batch_id=batch.id))
        except ValidationError as error:
            report_error(error)
    return render_template('import.html',active='transfer')


@bp.route('/<batch_id>',methods=['GET','POST'])
def preview(batch_id):
    batch = owned_batch(batch_id)
    try:
        review = review_batch(batch,request.form if request.method == 'POST' else None)
        return render_template('import_preview.html',active='transfer',batch=batch,review=review)
    except ValidationError as error:
        report_error(error)
        return redirect(url_for('importing.index'))


@bp.post('/<batch_id>/confirm')
def confirm(batch_id):
    try:
        if request.form.get('confirmed') != 'yes':
            raise ValidationError('error.csv_review')
        count = commit_batch(owned_batch(batch_id),request.form.get('duplicates','skip'))
        flash(translate('csv.imported',count=count),'success')
        return redirect(url_for('transactions.index'))
    except ValidationError as error:
        report_error(error)
        return redirect(url_for('importing.preview',batch_id=batch_id))
