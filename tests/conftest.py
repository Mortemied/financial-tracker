import pytest
from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import Category


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def category_ids(app):
    return {c.key: c.id for c in db.session.scalars(db.select(Category))}


@pytest.fixture
def transaction_data(category_ids):
    return {'type': 'expense', 'amount': '123.45', 'category_id': str(category_ids['food']),
            'date': '2026-02-15', 'description': 'Groceries'}
