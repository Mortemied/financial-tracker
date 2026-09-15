import io
import json
import re
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
import pytest
from sqlalchemy import create_engine
from app import create_app
from app.extensions import db
from app.models import Transaction, Goal, Category, ImportBatch
from app.services.transactions import save_transaction, transaction_query, ValidationError
from app.services.importing import parse_upload, create_batch, review_batch, commit_batch
from app.services.budgets import save_budget, preview_budget_copy, copy_previous_budgets, budget_progress
from app.services.goals import save_goal, add_money
from app.services.backups import create_backup, restore_backup, validate_backup
from app.services.migrations import upgrade_database
from app.analytics.monthly import month_summary


def test_quick_add(client,transaction_data):
    response = client.post('/transactions/quick',data=transaction_data)
    assert response.json == {'ok':True}
    assert client.post('/transactions/quick',data={**transaction_data,'amount':'-1'}).status_code == 422
    assert db.session.scalar(db.select(db.func.count(Transaction.id))) == 1


def test_duplicate_requires_confirmation(client,transaction_data):
    row = save_transaction(transaction_data)
    page = client.get(f'/transactions/{row.id}/duplicate')
    assert page.status_code == 200
    assert b'action="/transactions/new"' in page.data
    assert date.today().isoformat().encode() in page.data
    category_select = re.search(r'<select[^>]+id="transaction-category".*?</select>',page.text,re.S).group()
    assert f'value="{row.category_id}" data-type="{row.type}" selected' in category_select
    assert db.session.scalar(db.select(db.func.count(Transaction.id))) == 1
    client.post('/transactions/new',data={**transaction_data,'date':date.today().isoformat()})
    assert db.session.scalar(db.select(db.func.count(Transaction.id))) == 2


def test_delete_undo_excludes_all_reports(client,transaction_data):
    row = save_transaction(transaction_data)
    save_budget({'category_id':row.category_id,'month':'2026-02','amount':'1000'})
    response = client.post(f'/transactions/{row.id}/delete',follow_redirects=True)
    token = re.search(r'name="token" value="([^"]+)"',response.data.decode()).group(1)
    assert db.session.scalars(transaction_query({})).all() == []
    assert budget_progress(date(2026,2,1),date(2026,2,28))[0]['spent'] == 0
    assert b'Groceries' not in client.get('/export/download').data
    assert client.get(f'/transactions/{row.id}/edit').status_code == 404
    client.post('/transactions/undo',data={'token':token})
    assert db.session.get(Transaction,row.id).deleted_at is None
    assert len(db.session.scalars(transaction_query({})).all()) == 1
    # A token from an earlier deletion cannot undo a later deletion.
    client.post(f'/transactions/{row.id}/delete')
    client.post('/transactions/undo',data={'token':token})
    assert db.session.get(Transaction,row.id).deleted_at is not None


def test_invalid_undo_does_not_restore(client,transaction_data):
    row = save_transaction(transaction_data)
    client.post(f'/transactions/{row.id}/delete')
    response = client.post('/transactions/undo',data={'token':'tampered'},follow_redirects=True)
    assert b'Undo expired' in response.data
    assert row.deleted_at is not None


def test_month_comparison_and_estimate():
    rows=[SimpleNamespace(type='expense',amount_cents=10000,date=date(2026,1,1),category_id=1),
          SimpleNamespace(type='expense',amount_cents=15000,date=date(2026,2,1),category_id=1)]
    summary=month_summary(rows,date(2026,2,1),date(2026,2,28),date(2026,2,10))
    assert summary['comparison']['expenses']==50
    assert summary['comparison']['income'] is None
    assert summary['average']==1500 and summary['estimated']==42000 and summary['days_remaining']==18
    assert month_summary([],date(2026,2,1),date(2026,2,28),date(2026,2,10))['comparison']['expenses'] is None


def test_copy_budget_preserves_existing(client,category_ids):
    save_budget({'category_id':category_ids['food'],'month':'2026-01','amount':'4000'})
    save_budget({'category_id':category_ids['housing'],'month':'2026-01','amount':'12000'})
    save_budget({'category_id':category_ids['food'],'month':'2026-02','amount':'4500'})
    assert len(preview_budget_copy('2026-02'))==2
    assert client.get('/budgets/copy?month=2026-02').status_code==200
    assert copy_previous_budgets('2026-02')==1
    assert copy_previous_budgets('2026-02')==0
    rows=budget_progress(date(2026,2,1),date(2026,2,28))
    assert next(row for row in rows if row['budget'].category_id==category_ids['food'])['budget'].amount_cents==450000


def test_goal_crud_does_not_change_balance(client):
    data={'name':'Vacation','target_amount':'30000','current_amount':'12500','currency':'NOK','target_date':'2027-07-01'}
    response=client.post('/goals/new',data=data)
    assert response.status_code==302
    goal=db.session.scalar(db.select(Goal))
    client.post(f'/goals/{goal.id}/add',data={'amount':'0.29'})
    assert goal.current_cents==1250029
    client.post(f'/goals/{goal.id}/edit',data={**data,'name':'Trip','current_amount':'12500.29'})
    assert goal.name=='Trip'
    assert db.session.scalar(db.select(db.func.count(Transaction.id)))==0
    assert client.get('/goals/').status_code==200
    gid=goal.id
    client.post(f'/goals/{gid}/delete')
    assert db.session.get(Goal,gid) is None


def csv_bytes(category='food',amount='12.34'):
    return f'Date,Type,Category,Description,Amount\n2026-02-15,expense,{category},Coffee,{amount}\n'.encode('utf-8')


def test_import_mapping_and_duplicates(app,category_ids):
    batch=create_batch(csv_bytes('Cafe'))
    review=review_batch(batch)
    assert review['rows'][0]['status']=='unknown'
    key=next(iter(review['unknown']))
    review=review_batch(batch,{'map_'+key:str(category_ids['food'])})
    assert review['rows'][0]['status']=='ready'
    assert commit_batch(batch)==1
    with pytest.raises(ValidationError):
        commit_batch(batch)
    duplicate=create_batch(csv_bytes())
    assert review_batch(duplicate)['rows'][0]['status']=='duplicate'
    assert commit_batch(duplicate,'skip')==0
    another=create_batch(csv_bytes())
    assert commit_batch(another,'import')==1


def test_import_within_file_duplicate_and_invalid(app):
    raw=csv_bytes()+csv_bytes().split(b'\n')[1]+b'\n'
    batch=create_batch(raw)
    assert [r['status'] for r in review_batch(batch)['rows']]==['ready','duplicate']
    assert commit_batch(batch)==1
    invalid=create_batch(csv_bytes(amount='NaN'))
    assert review_batch(invalid)['rows'][0]['status']=='invalid'
    with pytest.raises(ValidationError):
        commit_batch(invalid)
    assert len(parse_upload(csv_bytes().replace(b',',b';')))==1


def test_csv_upload_requires_preview(client):
    response=client.post('/import/',data={'csv':(io.BytesIO(csv_bytes()),'input.csv')},content_type='multipart/form-data')
    assert response.status_code==302
    assert db.session.scalar(db.select(db.func.count(Transaction.id)))==0
    page=client.get(response.headers['Location'])
    assert b'Ready' in page.data
    client.post(response.headers['Location']+'/confirm',data={'confirmed':'yes','duplicates':'skip'})
    assert db.session.scalar(db.select(db.func.count(Transaction.id)))==1


@pytest.fixture
def file_app(tmp_path):
    app=create_app({'TESTING':True,'WTF_CSRF_ENABLED':False,'DATA_DIR':str(tmp_path),
                    'SQLALCHEMY_DATABASE_URI':'sqlite:///'+(tmp_path/'finance.db').as_posix()})
    with app.app_context():
        yield app
        db.session.remove(); db.engine.dispose()


def test_backup_restore_preserves_safety(file_app):
    category=db.session.scalar(db.select(Category).where(Category.key=='food'))
    values={'type':'expense','amount':'0.29','category_id':category.id,'description':'before','date':'2026-02-15'}
    save_transaction(values)
    backup=create_backup()
    assert validate_backup(backup)['transaction']==1
    save_transaction({**values,'description':'after'})
    safety=restore_backup(backup)
    assert validate_backup(safety)['transaction']==2
    assert db.session.scalar(db.select(db.func.count(Transaction.id)))==1
    assert backup.exists() and safety.exists()


def test_invalid_backup_never_overwrites(file_app,tmp_path):
    before=create_backup()
    invalid=tmp_path/'invalid.db'; invalid.write_bytes(b'not a database')
    with pytest.raises(ValidationError):
        restore_backup(invalid)
    assert validate_backup(before)['category']==14


def test_migrate_real_v1_shape_without_losing_rows(tmp_path):
    from alembic import command
    from alembic.config import Config
    from app.runtime import resource_directory
    target=tmp_path/'legacy.db'
    engine=create_engine('sqlite:///'+target.as_posix())
    config=Config();config.set_main_option('script_location',str(resource_directory()/'migrations'))
    with engine.begin() as conn:
        config.attributes['connection']=conn
        command.upgrade(config,'0001_v1')
        conn.exec_driver_sql("INSERT INTO category VALUES(1,'food',NULL,'expense','#123456')")
        conn.exec_driver_sql("INSERT INTO settings VALUES(1,'ru','NOK','dark')")
        conn.exec_driver_sql("INSERT INTO \"transaction\" VALUES(7,'expense',29,1,'Legacy','2026-02-15','2026-02-15','2026-02-15')")
        conn.exec_driver_sql('DROP TABLE alembic_version')
    assert upgrade_database(engine,tmp_path/'backups')
    assert not upgrade_database(engine,tmp_path/'backups')
    with engine.connect() as conn:
        assert conn.exec_driver_sql('SELECT id,amount_cents,description,deleted_at FROM "transaction"').one()==(7,29,'Legacy',None)
        assert conn.exec_driver_sql('SELECT language FROM settings').scalar()=='ru'
    assert list((tmp_path/'backups').glob('*.db'))
    engine.dispose()


@pytest.mark.parametrize('language',['en','ru'])
@pytest.mark.parametrize('path',['/','/goals/','/goals/new','/import/','/settings/','/budgets/copy'])
def test_v2_localized_pages(client,path,language):
    client.post('/settings/',data={'language':language})
    response=client.get(path)
    assert response.status_code==200
    assert f'lang="{language}"'.encode() in response.data


def test_csv_mapping_survives_multiple_reviews(app, category_ids):
    from app.services.importing import mapping_key
    batch = create_batch(csv_bytes('Cafe'))
    first = review_batch(batch, {'map_'+mapping_key('Cafe','expense'):str(category_ids['food'])})
    second = review_batch(batch, {})
    assert first['rows'][0]['resolved_category'].id == category_ids['food']
    assert second['rows'][0]['status'] == 'ready'
    assert commit_batch(batch) == 1


def test_undo_expires_on_server(client, transaction_data, monkeypatch):
    from itsdangerous.timed import TimestampSigner
    row = save_transaction(transaction_data)
    response = client.post(f'/transactions/{row.id}/delete', follow_redirects=True)
    token = re.search(r'name="token" value="([^"]+)"', response.text).group(1)
    real_time = TimestampSigner.get_timestamp
    monkeypatch.setattr(TimestampSigner, 'get_timestamp', lambda self: real_time(self)+21)
    response = client.post('/transactions/undo', data={'token':token}, follow_redirects=True)
    assert row.deleted_at is not None
    assert 'Undo expired' in response.text


def test_backup_restore_ui_requires_confirmation(file_app):
    client = file_app.test_client()
    assert client.post('/backups/create').status_code == 302
    backup = create_backup()
    response = client.post('/backups/preview', data={'backup':(io.BytesIO(backup.read_bytes()),'copy.db')})
    assert response.status_code == 200
    with client.session_transaction() as session:
        token = session['restore_token']
    assert client.post('/backups/restore',data={'token':token}).status_code == 400
    response = client.post('/backups/restore',data={'token':token,'confirmed':'yes'},follow_redirects=True)
    assert response.status_code == 200
    assert list((Path(file_app.config['DATA_DIR'])/'backups').glob('before_restore_*.db'))
    assert client.post('/backups/open',follow_redirects=True).status_code == 200


def test_instance_lock_rejects_second_process(tmp_path):
    import subprocess, sys
    from launcher import InstanceLock
    lock = InstanceLock(tmp_path)
    assert lock.acquire()
    try:
        code = 'from pathlib import Path; from launcher import InstanceLock; import sys; lock=InstanceLock(Path(sys.argv[1])); acquired=lock.acquire(); lock.close(); sys.exit(1 if acquired else 0)'
        assert subprocess.run([sys.executable,'-c',code,str(tmp_path)],timeout=10).returncode == 0
    finally:
        lock.close()
    next_lock=InstanceLock(tmp_path)
    assert next_lock.acquire()
    next_lock.close()
