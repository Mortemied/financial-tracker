from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, abort
from app.extensions import db
from app.models import Transaction, utc_now
from datetime import date
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from app.services.transactions import save_transaction, transaction_query, ValidationError
from app.localization import translate
from .shared import categories, report_error

bp = Blueprint('transactions', __name__, url_prefix='/transactions')


@bp.get('/')
def index():
    try:
        query = transaction_query(request.args)
        page = max(1, request.args.get('page', 1, type=int))
        pagination = db.paginate(query, page=page, per_page=10, error_out=False)
    except ValidationError as error:
        report_error(error)
        return redirect(url_for('transactions.index'))
    args = request.args.to_dict()
    args.pop('page', None)
    return render_template('transactions.html', active='transactions', pagination=pagination,
                           categories=categories(), filter_args=args)


@bp.route('/new', methods=['GET', 'POST'])
@bp.route('/<int:transaction_id>/edit', methods=['GET', 'POST'])
def edit(transaction_id=None):
    row = db.get_or_404(Transaction, transaction_id) if transaction_id else None
    if row and row.deleted_at is not None:
        abort(404)
    if request.method == 'POST':
        try:
            save_transaction(request.form, row)
            flash(translate('saved'), 'success')
            return redirect(url_for('transactions.index'))
        except ValidationError as error:
            report_error(error)
            return render_template('transaction_form.html', active='transactions', row=row,
                                   categories=categories(), values=request.form), 422
    values = {'type': row.type, 'amount': str(row.amount), 'category_id': str(row.category_id),
              'description': row.description, 'date': row.date.isoformat()} if row else {}
    return render_template('transaction_form.html', active='transactions', row=row, categories=categories(), values=values)


def active_transaction(transaction_id):
    row = db.get_or_404(Transaction, transaction_id)
    if row.deleted_at is not None:
        abort(404)
    return row


@bp.post('/<int:transaction_id>/delete')
def delete(transaction_id):
    row = active_transaction(transaction_id)
    row.deleted_at = utc_now()
    db.session.commit()
    token = URLSafeTimedSerializer(current_app.secret_key, salt='transaction-undo').dumps({'id':row.id,'deleted_at':row.deleted_at.isoformat()})
    flash({'text':translate('transaction.deleted'),'token':token}, 'undo')
    return redirect(url_for('transactions.index'))


@bp.post('/undo')
def undo():
    try:
        identity = URLSafeTimedSerializer(current_app.secret_key, salt='transaction-undo').loads(request.form.get('token',''),max_age=20)
        row = db.session.get(Transaction,identity['id'])
        if not row or row.deleted_at is None or row.deleted_at.isoformat() != identity['deleted_at']:
            raise BadSignature('Not deleted')
        row.deleted_at = None
        db.session.commit()
        flash(translate('transaction.restored'),'success')
    except (BadSignature, SignatureExpired):
        flash(translate('error.undo_expired'),'error')
    return redirect(url_for('transactions.index'))


@bp.get('/<int:transaction_id>/duplicate')
def duplicate(transaction_id):
    row = active_transaction(transaction_id)
    values = {'type':row.type,'amount':str(row.amount),'category_id':str(row.category_id),
              'description':row.description,'date':date.today().isoformat()}
    return render_template('transaction_form.html',active='transactions',row=None,values=values,categories=categories(),duplicating=True)


@bp.post('/quick')
def quick():
    try:
        save_transaction(request.form)
        flash(translate('saved'),'success')
        return jsonify(ok=True)
    except ValidationError as error:
        return jsonify(ok=False,error=translate(error.key,**error.params)),422
