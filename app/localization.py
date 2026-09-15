"""Small JSON catalog adapter + Babel locale-aware formatting.

Add a catalog and register its locale in Config.LANGUAGES; services never translate.
"""
import json
from pathlib import Path
from decimal import Decimal
from babel.numbers import format_currency, format_decimal
from babel.dates import format_date
from flask import g, current_app


def locale():
    return getattr(g, 'settings', None).language if getattr(g, 'settings', None) else 'en'


def translate(key, **params):
    catalogs = current_app.extensions['catalogs']
    value = catalogs.get(locale(), catalogs['en']).get(key, catalogs['en'].get(key, key))
    return value.format(**params)


def format_money(amount, currency=None):
    currency = currency or g.settings.currency
    return format_currency(Decimal(amount), currency, locale=locale())


def money_cents(value, currency=None):
    return format_money(Decimal(value) / 100, currency)


def category_label(category):
    return translate('category.' + category.key) if category.key else category.name


def init_localization(app):
    directory = Path(app.root_path) / 'translations'
    app.extensions['catalogs'] = {code: json.loads((directory / f'{code}.json').read_text(encoding='utf-8'))
                                  for code in app.config['LANGUAGES']}
    app.jinja_env.globals.update(t=translate, category_label=category_label, format_money=format_money)
    app.jinja_env.filters.update(money=money_cents,
        localnumber=lambda value: format_decimal(value, locale=locale()),
        localdate=lambda value: format_date(value, format='medium', locale=locale()))
