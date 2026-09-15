from app.models import Settings
from app.extensions import db
from app.services.transactions import ValidationError


def get_settings():
    return db.session.get(Settings, 1)


def save_settings(data, languages, currencies):
    settings = get_settings()
    language = data.get('language', settings.language)
    currency = data.get('currency', settings.currency)
    theme = data.get('theme', settings.theme)
    if language not in languages or currency not in currencies or theme not in ('light', 'dark'):
        raise ValidationError('error.settings')
    settings.language, settings.currency, settings.theme = language, currency, theme
    db.session.commit()
    return settings
