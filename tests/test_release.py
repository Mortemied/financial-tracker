import io
import json
import logging
from datetime import date
from pathlib import Path
from types import SimpleNamespace
import pytest
from sqlalchemy.exc import OperationalError
from app import create_app
from app.extensions import db
from app.models import Goal, Category, Transaction
from app.version import VERSION
from app.services.goals import save_goal, add_money
from app.services.importing import create_batch, review_batch, commit_batch
from app.services.transactions import ValidationError, save_transaction
from app.services.backups import create_backup, restore_backup
from app.logging_config import PrivateFormatter
from app.analytics import summarize, balance_history


def test_about_and_privacy(client):
    for language,text in [('en','Your financial data is stored locally'),('ru','Ваши финансовые данные хранятся локально')]:
        client.post('/settings/',data={'language':language})
        page=client.get('/settings/').text
        assert VERSION in page and text in page
        assert 'MIT' in page
        assert 'href=""' not in page


def test_goal_update_timestamp(app):
    goal=save_goal({'name':'Trip','target_amount':'100','current_amount':'0','currency':'NOK'},['NOK'])
    before=goal.updated_at
    add_money(goal,'10')
    assert goal.updated_at >= before
    assert goal.current_cents == 1000


def test_database_failure_renders_without_reading_failed_db(client,monkeypatch):
    def fail():
        raise OperationalError('SELECT secret',{'description':'private finance'},Exception('private'))
    monkeypatch.setattr('app.services.preferences.get_settings',fail)
    response=client.get('/')
    assert response.status_code==503
    assert 'temporarily unavailable' in response.text
    assert 'private finance' not in response.text and 'Traceback' not in response.text
    assert client.get('/static/css/app.css').status_code==200
    response=client.post('/transactions/quick',headers={'Accept':'application/json'})
    assert response.status_code==503 and response.json['ok'] is False


def test_unexpected_error_page_is_safe():
    app=create_app({'TESTING':True,'PROPAGATE_EXCEPTIONS':False,'SQLALCHEMY_DATABASE_URI':'sqlite://'})
    @app.get('/broken-for-test')
    def broken():
        raise RuntimeError('Never display this private detail')
    response=app.test_client().get('/broken-for-test')
    assert response.status_code==500
    assert 'private detail' not in response.text and 'Traceback' not in response.text
    with app.app_context():
        db.session.remove();db.engine.dispose()


def test_shutdown_is_loopback_post_only(client,app):
    called=[]
    app.config['STOP_APPLICATION']=lambda:called.append(True)
    assert client.get('/backups/quit').status_code==405
    assert client.post('/backups/quit',environ_overrides={'REMOTE_ADDR':'192.168.1.20'}).status_code==403
    assert called==[]
    assert client.post('/backups/quit').status_code==200
    assert called==[True]


def test_json_csrf_error():
    app=create_app({'TESTING':True,'SQLALCHEMY_DATABASE_URI':'sqlite://','WTF_CSRF_ENABLED':True})
    response=app.test_client().post('/transactions/quick',headers={'Accept':'application/json'})
    assert response.status_code==400 and 'expired' in response.json['error']
    with app.app_context():
        db.session.remove();db.engine.dispose()


def test_private_log_formatter_omits_exception_values():
    import sys
    try:
        raise OperationalError('INSERT INTO secret',{'amount':'123456.78'},Exception('sensitive description'))
    except OperationalError:
        text=PrivateFormatter().formatException(sys.exc_info())
    assert 'OperationalError' in text and 'test_release.py' in text
    assert 'sensitive' not in text and '123456.78' not in text and 'INSERT' not in text


def test_calendar_upper_boundary():
    end=date(9999,12,31)
    assert summarize([],end,end)['trend']==[{'label':'9999-12-31','value':0}]
    assert balance_history([],end,end)==[{'label':'9999-12-31','value':0}]


def test_unicode_category_duplicates_and_search(client,category_ids):
    client.post('/categories/',data={'name':'Кофе','type':'expense'})
    client.post('/categories/',data={'name':'КОФЕ','type':'expense'})
    names=db.session.scalars(db.select(Category.name).where(Category.key.is_(None))).all()
    assert len(names)==1
    save_transaction({'type':'expense','amount':'10','category_id':category_ids['food'],'description':'Продукты','date':'2026-09-14'})
    assert 'Продукты' in client.get('/transactions/?q=ПРОДУКТЫ').text


def test_csv_repeated_submit_and_other_session(client,app):
    raw=b'Date,Type,Category,Description,Amount\n2026-09-14,expense,food,Test,10.00\n'
    response=client.post('/import/',data={'csv':(io.BytesIO(raw),'../../outside.csv')})
    path=response.headers['Location']
    assert app.test_client().get(path).status_code==404
    client.post(path+'/confirm',data={'confirmed':'yes','duplicates':'skip'})
    client.post(path+'/confirm',data={'confirmed':'yes','duplicates':'import'})
    assert db.session.scalar(db.select(db.func.count(Transaction.id)))==1


@pytest.mark.parametrize('raw',[b'not csv',b'\xff\xfe',b'Date,Type,Category,Description,Amount\n',b'x'*(2*1024*1024+1)],ids=['headers','encoding','empty','size'])
def test_invalid_csv_does_not_create_records(client,raw):
    response=client.post('/import/',data={'csv':(io.BytesIO(raw),'bad.csv')})
    assert response.status_code==200
    assert db.session.scalar(db.select(db.func.count(Transaction.id)))==0


def test_backup_rejects_trigger_without_replacing(tmp_path):
    import sqlite3
    from contextlib import closing
    app=create_app({'TESTING':True,'WTF_CSRF_ENABLED':False,'DATA_DIR':str(tmp_path),
                    'SQLALCHEMY_DATABASE_URI':'sqlite:///'+(tmp_path/'db.sqlite').as_posix()})
    with app.app_context():
        backup=create_backup()
        with closing(sqlite3.connect(backup)) as c:
            c.execute('CREATE TRIGGER unexpected AFTER INSERT ON goal BEGIN DELETE FROM "transaction"; END')
            c.commit()
        with pytest.raises(ValidationError):
            restore_backup(backup)
        assert db.session.scalar(db.select(db.func.count(Category.id)))==14
        db.session.remove();db.engine.dispose()


def test_stamped_incomplete_backup_rejected(tmp_path):
    import sqlite3
    from contextlib import closing
    app=create_app({'TESTING':True,'DATA_DIR':str(tmp_path),'SQLALCHEMY_DATABASE_URI':'sqlite:///'+(tmp_path/'db.sqlite').as_posix()})
    with app.app_context():
        backup=create_backup()
        with closing(sqlite3.connect(backup)) as c:
            c.execute('DROP TABLE goal');c.commit()
        with pytest.raises(ValidationError):
            restore_backup(backup)
        assert db.session.scalar(db.select(db.func.count(Category.id)))==14
        db.session.remove();db.engine.dispose()
