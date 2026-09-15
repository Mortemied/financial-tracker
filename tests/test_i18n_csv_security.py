import csv
import io
import json
import re
from pathlib import Path
import pytest
from app import create_app
from app.extensions import db
from app.models import Settings, Category
from app.services.transactions import save_transaction, ValidationError
from app.services.csv_transfer import preview_import
from app.services.seed import seed_demo


@pytest.mark.parametrize('path',['/','/transactions/','/transactions/new','/categories/','/analytics/','/budgets/','/settings/','/export/'])
@pytest.mark.parametrize('language',['en','ru'])
def test_localized_pages(client,path,language):
    client.post('/settings/',data={'language':language})
    response = client.get(path)
    assert response.status_code == 200
    assert f'lang="{language}"'.encode() in response.data
    assert (('Главная' if language == 'ru' else 'Overview').encode()) in response.data
    assert b'nav.dashboard' not in response.data


def test_persisted_settings_and_money(client,app):
    client.post('/settings/',data={'language':'ru','theme':'dark','currency':'EUR'})
    fresh_client = app.test_client()
    html = fresh_client.get('/').data.decode()
    assert 'data-theme="dark"' in html and 'lang="ru"' in html and '€' in html
    settings = db.session.get(Settings,1)
    assert (settings.language,settings.currency,settings.theme) == ('ru','EUR','dark')
    client.post('/settings/',data={'language':'invalid','currency':'BAD'})
    assert settings.language == 'ru' and settings.currency == 'EUR'
    for currency in ['NOK','EUR','USD','UAH']:
        assert client.post('/settings/',data={'currency':currency}).status_code == 302


def test_catalog_keys_and_literal_translation_calls(app):
    catalogs = app.extensions['catalogs']
    assert set(catalogs['en']) == set(catalogs['ru'])
    for key in catalogs['en']:
        assert set(re.findall(r'\{(\w+)\}',catalogs['en'][key])) == set(re.findall(r'\{(\w+)\}',catalogs['ru'][key]))
    for path in Path(app.root_path).rglob('*'):
        if path.suffix not in ('.py','.html'):
            continue
        text = path.read_text(encoding='utf-8')
        for key in re.findall(r"\b(?:t|translate|ValidationError)\(['\"]([\w.]+)['\"]\)",text):
            assert key in catalogs['en'], (path,key)


def test_csv_filters_localization_and_formula_safety(client,transaction_data,category_ids):
    save_transaction({**transaction_data,'description':'=HYPERLINK("bad")'})
    save_transaction({**transaction_data,'description':'comma, "quote"\nline','date':'2026-03-01'})
    save_transaction({**transaction_data,'type':'income','category_id':str(category_ids['salary']),'amount':'1000'})
    client.post('/settings/',data={'language':'ru'})
    response = client.get('/export/download?type=expense&start=2026-02-01&end=2026-02-28')
    assert response.status_code == 200
    text = response.data.decode('utf-8-sig')
    rows = list(csv.DictReader(io.StringIO(text)))
    assert len(rows) == 1
    assert rows[0]['Amount'] == '123.45'
    assert rows[0]['Category'] == 'Еда'
    assert rows[0]['Description'].startswith("'=")
    assert 'attachment;' in response.headers['Content-Disposition']
    assert len(list(csv.DictReader(io.StringIO(client.get('/export/download?type=income').data.decode('utf-8-sig'))))) == 1


def test_import_preview_validates_without_writes(app,category_ids):
    source = 'Date,Type,Category,Description,Amount\n2026-02-01,expense,food,Test,0.29\n2026-02-02,expense,food,Bad,-1\n'
    result = preview_import(source,lambda key,kind: category_ids[key])
    assert result['rows'][0]['amount_cents'] == 29
    assert result['errors'] == [{'row':3,'key':'error.amount'}]
    from app.models import Transaction
    assert db.session.scalar(db.select(db.func.count(Transaction.id))) == 0
    with pytest.raises(ValidationError):
        preview_import('Bad,Headers\n1,2',lambda key,kind: 1)


def test_csrf_and_security_headers():
    app = create_app({'TESTING':True,'SQLALCHEMY_DATABASE_URI':'sqlite://','WTF_CSRF_ENABLED':True})
    client = app.test_client()
    response = client.post('/settings/',data={'theme':'dark'})
    assert response.status_code == 400
    assert b'This form expired' in response.data
    response = client.get('/')
    assert response.headers['X-Content-Type-Options'] == 'nosniff'
    assert "script-src 'self'" in response.headers['Content-Security-Policy']
    token = re.search(r'name="csrf_token" value="([^"]+)"',response.data.decode()).group(1)
    assert client.post('/settings/',data={'csrf_token':token,'theme':'dark'}).status_code == 302
    with app.app_context():
        assert db.session.get(Settings,1).theme == 'dark'
        db.drop_all()


def test_xss_is_escaped_and_redirect_is_local(client,transaction_data):
    save_transaction({**transaction_data,'description':'<script>alert(1)</script>'})
    assert b'&lt;script&gt;alert(1)&lt;/script&gt;' in client.get('/transactions/').data
    response = client.post('/settings/',data={'next':'//evil.example'})
    assert response.headers['Location'] == '/settings/'
    response = client.post('/settings/',data={'next':'/\\evil.example'})
    assert response.headers['Location'] == '/settings/'


def test_seed_is_idempotent_and_populates_charts(client):
    count = seed_demo()
    assert count > 90
    assert seed_demo() == 0
    response = client.get('/')
    assert response.status_code == 200
    assert b'chart-config' in response.data
    assert b'REMA 1000' in client.get('/transactions/?q=REMA').data
    for key in db.session.scalars(db.select(Category.key)).all():
        assert key.isascii()
