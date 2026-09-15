from datetime import date
from types import SimpleNamespace
import pytest
from app.analytics import summarize, total_balance, balance_history
from app.services.periods import resolve_period, month_period
from app.services.transactions import save_transaction, ValidationError
from app.services.budgets import save_budget, budget_progress
from app.models import Budget
from app.extensions import db


def record(kind, cents, day, category=1):
    return SimpleNamespace(type=kind, amount_cents=cents, date=date.fromisoformat(day), category_id=category)


def test_financial_calculations_and_opening_balance():
    rows = [record('income',10000,'2026-01-01'), record('expense',29,'2026-01-02'),
            record('income',20000,'2026-02-01'), record('expense',3000,'2026-02-10'),
            record('expense',7000,'2026-02-20',2)]
    start, end = date(2026,2,1), date(2026,2,28)
    result = summarize(rows,start,end)
    assert result['income'] == 20000
    assert result['expenses'] == 10000
    assert result['savings'] == 10000
    assert result['average'] == 357
    assert result['biggest'].amount_cents == 7000
    assert result['categories'][0] == (2,7000)
    assert total_balance(rows) == 19971
    history = balance_history(rows,start,end)
    assert history[0]['value'] == 29971
    assert history[-1]['value'] == 19971
    assert result['insights'][0] == {'key':'insight.savings','params':{'percent':50}}


def test_empty_and_deficit():
    result = summarize([],date(2026,1,1),date(2026,2,28))
    assert result['average'] == 0
    assert list(result['months']) == ['2026-01','2026-02']
    assert result['insights'][0]['key'] == 'insight.empty'
    result = summarize([record('expense',100,'2026-01-01')],date(2026,1,1),date(2026,1,1))
    assert result['savings'] == -100
    assert result['insights'][0]['key'] == 'insight.deficit'


def test_period_boundaries():
    with pytest.raises(ValidationError):
        month_period('0001-01')
    assert month_period('2024-02') == (date(2024,2,1), date(2024,2,29))
    assert resolve_period({'period':'last_month'},date(2026,1,15)) == (date(2025,12,1),date(2025,12,31))
    assert resolve_period({'period':'last_3'},date(2026,1,15))[0] == date(2025,11,1)
    assert resolve_period({'period':'last_6'},date(2026,1,15))[0] == date(2025,8,1)
    assert resolve_period({'period':'this_year'},date(2026,8,15))[0] == date(2026,1,1)
    with pytest.raises(ValidationError):
        resolve_period({'period':'custom','start':'2026-02-01','end':'2026-01-01'})


@pytest.mark.parametrize('amount,status', [('79.99','normal'),('80','warning'),('100','warning'),('100.01','over_budget')])
def test_budget_thresholds(app, transaction_data, amount, status):
    save_budget({'category_id':transaction_data['category_id'],'month':'2026-02','amount':'100'})
    save_transaction({**transaction_data,'amount':amount})
    progress = budget_progress(date(2026,2,1),date(2026,2,28))
    assert progress[0]['status'] == status


def test_budget_update_and_month_isolation(client, transaction_data, category_ids):
    data = {'category_id':transaction_data['category_id'],'month':'2026-02','amount':'100'}
    budget = save_budget(data)
    save_budget({**data,'amount':'200'})
    assert db.session.scalar(db.select(db.func.count(Budget.id))) == 1
    assert budget.amount_cents == 20000
    save_transaction({**transaction_data,'date':'2026-03-01'})
    assert budget_progress(date(2026,2,1),date(2026,2,28))[0]['spent'] == 0
    with pytest.raises(ValidationError):
        save_budget({**data,'category_id':str(category_ids['salary'])})
    bid = budget.id
    assert client.post(f'/budgets/{bid}/delete').status_code == 302
    assert db.session.get(Budget,bid) is None
