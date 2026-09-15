from datetime import date
import random
from app.extensions import db
from app.models import Category, Settings, Transaction, Budget
from app.services.periods import shift_month

CATEGORY_KEYS = {
    'expense': ['housing', 'food', 'transport', 'entertainment', 'shopping', 'health', 'education', 'subscriptions', 'other'],
    'income': ['salary', 'freelance', 'gift', 'investment', 'other_income'],
}
COLORS = ['#3984ff', '#12c89e', '#ffc45c', '#9b83ed', '#ef91b9', '#ff777f', '#6ec8e3', '#b6a0ec', '#8d9bb4']


def initialize():
    from flask import current_app
    from pathlib import Path
    from app.services.migrations import upgrade_database
    upgrade_database(db.engine, None if current_app.testing else Path(current_app.config['DATA_DIR']) / 'backups')
    for kind, keys in CATEGORY_KEYS.items():
        for index, key in enumerate(keys):
            if not db.session.scalar(db.select(Category).where(Category.key == key)):
                db.session.add(Category(key=key, type=kind, color=COLORS[index % len(COLORS)]))
    if not db.session.get(Settings, 1):
        db.session.add(Settings(id=1))
    db.session.commit()


def seed_demo():
    initialize()
    if db.session.scalar(db.select(Transaction.id).limit(1)):
        return 0
    rng = random.Random(42)
    categories = {c.key: c for c in db.session.scalars(db.select(Category))}
    today = date.today()
    count = 0
    for offset in range(-5, 1):
        month = shift_month(today, offset)
        entries = [('salary', 3200000, 1, 'Nord Studio'), ('freelance', rng.randint(3500, 8500)*100, 7, 'Website project'),
                   ('housing', 1200000, 2, 'Apartment'), ('subscriptions', 10900, 5, 'Spotify'),
                   ('subscriptions', 14900, 8, 'Cloud storage'), ('transport', 85000, 3, 'Ruter')]
        for day in (4, 9, 13, 17, 22, 26):
            entries.extend([('food', rng.randint(340, 850)*100, day, 'REMA 1000'),
                            ('entertainment', rng.randint(120, 450)*100, day, 'Coffee & friends')])
        entries.extend([('shopping', rng.randint(600, 1800)*100, 11, 'ARK'),
                        ('health', 32000, 12, 'Apotek'), ('education', 49000, 6, 'Python course')])
        for key, amount, day, description in entries:
            when = month.replace(day=day)
            if when > today:
                continue
            category = categories[key]
            db.session.add(Transaction(type=category.type, amount_cents=amount,
                           category_id=category.id, date=when, description=description))
            count += 1
        for key, amount in [('housing', 12000), ('food', 4000), ('transport', 1000),
                            ('entertainment', 1500), ('shopping', 2000), ('health', 1000), ('subscriptions', 1000)]:
            existing = db.session.scalar(db.select(Budget).where(Budget.category_id == categories[key].id, Budget.month == month))
            if not existing:
                db.session.add(Budget(category_id=categories[key].id, month=month, amount_cents=amount*100))
    db.session.commit()
    return count
