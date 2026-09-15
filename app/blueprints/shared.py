from flask import flash, g
from app.extensions import db
from app.models import Category, Transaction
from app.localization import translate, category_label


def categories():
    if not hasattr(g, 'category_cache'):
        g.category_cache = sorted(db.session.scalars(db.select(Category)).all(), key=category_label)
    return g.category_cache


def records():
    return db.session.scalars(db.select(Transaction).where(Transaction.deleted_at.is_(None)).order_by(Transaction.date, Transaction.id)).all()


def report_error(error):
    flash(translate(error.key, **error.params), 'error')


def chart_payload(summary, history=None):
    labels = {c.id: c for c in categories()}
    return {
        'breakdown': {'labels': [category_label(labels[key]) for key, _ in summary['categories']],
                      'values': [value/100 for _, value in summary['categories']],
                      'colors': [labels[key].color for key, _ in summary['categories']]},
        'monthly': {'labels': list(summary['months']),
                    'income': [v['income']/100 for v in summary['months'].values()],
                    'expense': [v['expense']/100 for v in summary['months'].values()],
                    'savings': [(v['income']-v['expense'])/100 for v in summary['months'].values()]},
        'trend': {'labels': [v['label'] for v in summary['trend']], 'values': [v['value']/100 for v in summary['trend']]},
        'balance': {'labels': [v['label'] for v in (history or [])], 'values': [v['value']/100 for v in (history or [])]},
        'text': {k: translate(k) for k in ['income', 'expense', 'savings', 'balance', 'no_data', 'chart_unavailable']},
    }
