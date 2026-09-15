from decimal import Decimal
import pytest
from app.extensions import db
from app.models import Transaction, Category
from app.services.transactions import parse_money, ValidationError, save_transaction, transaction_query


@pytest.mark.parametrize('amount', ['0', '-1', 'NaN', 'Infinity', '1.001', '1000000000', '', 'abc'])
def test_invalid_money(amount):
    with pytest.raises(ValidationError):
        parse_money(amount)


def test_money_is_exact():
    assert parse_money('0.29') == 29
    assert parse_money('123,45') == 12345
    assert parse_money('999999999.99') == 99999999999


def test_crud(client, transaction_data):
    assert client.post('/transactions/new', data=transaction_data).status_code == 302
    row = db.session.scalar(db.select(Transaction))
    assert row.amount == Decimal('123.45')
    row_id = row.id
    assert client.get(f'/transactions/{row_id}/edit').status_code == 200
    data = {**transaction_data, 'amount': '0.29', 'description': 'Updated'}
    assert client.post(f'/transactions/{row_id}/edit', data=data).status_code == 302
    db.session.expire_all()
    assert db.session.get(Transaction, row_id).amount_cents == 29
    assert b'Updated' in client.get('/transactions/').data
    assert client.get(f'/transactions/{row_id}/delete').status_code == 405
    assert client.post(f'/transactions/{row_id}/delete').status_code == 302
    assert db.session.get(Transaction, row_id).deleted_at is not None
    assert b'Updated' not in client.get('/transactions/').data
    assert client.post(f'/transactions/{row_id}/delete').status_code == 404


@pytest.mark.parametrize('changes', [
    {'type': 'bad'}, {'amount': '-1'}, {'date': '2026-02-30'},
    {'category_id': '99999'}, {'description': 'x'*251}, {'type': 'income'},
])
def test_server_validation(client, transaction_data, changes):
    response = client.post('/transactions/new', data={**transaction_data, **changes})
    assert response.status_code == 422
    assert db.session.scalar(db.select(db.func.count(Transaction.id))) == 0


def test_filters_sort_pagination(client, transaction_data, category_ids):
    for index in range(13):
        save_transaction({**transaction_data, 'amount': str(index+1), 'description': f'Shop {index}', 'date': f'2026-02-{index+1:02}'})
    save_transaction({**transaction_data, 'type': 'income', 'category_id': str(category_ids['salary']), 'amount': '32000', 'description': 'Pay'})
    assert len(db.session.scalars(transaction_query({'type': 'expense'})).all()) == 13
    assert len(db.session.scalars(transaction_query({'start': '2026-02-01', 'end': '2026-02-02'})).all()) == 2
    assert len(db.session.scalars(transaction_query({'category_id': str(category_ids['salary'])})).all()) == 1
    assert len(db.session.scalars(transaction_query({'q': 'Shop 12'})).all()) == 1
    assert len(db.session.scalars(transaction_query({'q': '%'})).all()) == 0
    assert db.session.scalars(transaction_query({'sort': 'highest'})).first().amount_cents == 3200000
    assert b'Page 2 of 2' in client.get('/transactions/?type=expense&page=2').data
    assert b'Shop 12' not in client.get('/transactions/?type=expense&page=2').data
    response = client.get('/transactions/?start=2026-03-01&end=2026-01-01', follow_redirects=True)
    assert b'Choose a valid date range' in response.data


def test_category_lifecycle(client, transaction_data):
    assert client.post('/categories/', data={'name': 'Pets', 'type': 'expense'}).status_code == 302
    category = db.session.scalar(db.select(Category).where(Category.name == 'Pets'))
    client.post(f'/categories/{category.id}/edit', data={'name': 'My pets', 'type': 'expense'})
    assert category.name == 'My pets'
    row = save_transaction({**transaction_data, 'category_id': str(category.id)})
    response = client.post(f'/categories/{category.id}/delete', follow_redirects=True)
    assert b'used by transactions' in response.data
    client.post(f'/transactions/{row.id}/delete')
    cid = category.id
    client.post(f'/categories/{cid}/delete')
    assert db.session.get(Category, cid) is not None  # Undo still needs the original category.
    # An actually unused custom category remains deletable.
    client.post('/categories/', data={'name':'Unused','type':'expense'})
    unused = db.session.scalar(db.select(Category).where(Category.name == 'Unused'))
    unused_id = unused.id
    client.post(f'/categories/{unused_id}/delete')
    assert db.session.get(Category, unused_id) is None


def test_system_categories_protected(client, category_ids):
    cid = category_ids['food']
    response = client.post(f'/categories/{cid}/delete', follow_redirects=True)
    assert b'Built-in categories cannot' in response.data
    client.post(f'/categories/{cid}/edit', data={'name': 'Oops', 'type': 'income'})
    assert db.session.get(Category, cid).key == 'food'
    assert db.session.get(Category, cid).type == 'expense'
