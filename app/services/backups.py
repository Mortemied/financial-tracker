"""SQLite online backups; restore only verified, migrated snapshots."""
from contextlib import closing
import os
import sqlite3
import tempfile
from pathlib import Path
from datetime import datetime
from sqlalchemy import create_engine
from flask import current_app
from app.extensions import db
from app.services.transactions import ValidationError
from app.services.migrations import upgrade_database


def backup_directory():
    directory = Path(current_app.config['DATA_DIR']) / 'backups'
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def database_path():
    path = db.engine.url.database
    if db.engine.dialect.name != 'sqlite' or not path or path == ':memory:':
        raise ValidationError('error.backup_unavailable')
    return Path(path)


def create_backup(prefix='financial_tracker_backup'):
    target = backup_directory() / (prefix + '_' + datetime.now().strftime('%Y-%m-%d_%H%M%S_%f') + '.db')
    db.session.remove()
    with closing(sqlite3.connect(database_path())) as source, closing(sqlite3.connect(target)) as destination:
        source.backup(destination)
    return target


def validate_backup(path):
    from datetime import date
    from app.services.seed import CATEGORY_KEYS
    try:
        with closing(sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)) as connection:
            connection.execute('PRAGMA trusted_schema=OFF')
            schema = connection.execute("SELECT type,name FROM sqlite_master").fetchall()
            if any(kind in ('trigger','view') for kind,name in schema):
                raise ValueError
            if connection.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError
            tables = {name for kind,name in schema if kind == 'table'}
            required = {
                'category': {'id','key','name','type','color'},
                'transaction': {'id','type','amount_cents','category_id','description','date','created_at','updated_at'},
                'budget': {'id','category_id','month','amount_cents'},
                'settings': {'id','language','currency','theme'},
            }
            if 'alembic_version' in tables:
                revision = connection.execute('SELECT version_num FROM alembic_version').fetchone()
                if not revision or revision[0] not in ('0001_v1','0002_v2','0003_release'):
                    raise ValueError
                if revision[0] != '0001_v1':
                    required['transaction'].add('deleted_at')
                    required['goal'] = {'id','name','target_cents','current_cents','currency','target_date','created_at'}
                    required['import_batch'] = {'id','payload','created_at','completed_at'}
                    if revision[0] == '0003_release':
                        required['goal'].add('updated_at')
            for table, columns in required.items():
                if table not in tables or not columns <= {row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')}:
                    raise ValueError
            if connection.execute('PRAGMA foreign_key_check').fetchall():
                raise ValueError
            prefs = connection.execute('SELECT language,currency,theme FROM settings WHERE id=1').fetchone()
            if not prefs or prefs[0] not in current_app.config['LANGUAGES'] or prefs[1] not in current_app.config['CURRENCIES'] or prefs[2] not in ('light','dark'):
                raise ValueError
            categories = {}
            for identity,key,name,kind,color in connection.execute('SELECT id,key,name,type,color FROM category'):
                if kind not in CATEGORY_KEYS or (key and key not in CATEGORY_KEYS[kind]) or (not key and (not name or len(name)>80)):
                    raise ValueError
                categories[identity] = kind
            def valid_amount(value, zero=False):
                if type(value) is not int or not (0 if zero else 1) <= value <= 99999999999:
                    raise ValueError
            def valid_timestamp(value):
                datetime.fromisoformat(value)
            for kind,amount,category,description,when,created,updated in connection.execute('SELECT type,amount_cents,category_id,description,date,created_at,updated_at FROM "transaction"'):
                if categories.get(category) != kind or not isinstance(description,str) or len(description)>250:
                    raise ValueError
                valid_amount(amount); date.fromisoformat(when)
                valid_timestamp(created); valid_timestamp(updated)
            for category,month,amount in connection.execute('SELECT category_id,month,amount_cents FROM budget'):
                if categories.get(category) != 'expense' or date.fromisoformat(month).day != 1:
                    raise ValueError
                valid_amount(amount)
            if 'goal' in tables:
                for name,target,current,currency,when,created in connection.execute('SELECT name,target_cents,current_cents,currency,target_date,created_at FROM goal'):
                    if not name or len(name)>80 or currency not in current_app.config['CURRENCIES']:
                        raise ValueError
                    valid_amount(target); valid_amount(current,zero=True); valid_timestamp(created)
                    if when:
                        date.fromisoformat(when)
            return {table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] if table in tables else 0
                    for table in ['transaction','category','budget','goal']}
    except (sqlite3.Error, ValueError, TypeError, OSError):
        raise ValidationError('error.backup_invalid') from None


def restore_backup(path):
    validate_backup(path)
    # Migration is tested on a private copy before the live database is touched.
    fd, name = tempfile.mkstemp(suffix='.db', dir=backup_directory())
    os.close(fd)
    candidate = Path(name)
    engine = None
    try:
        with closing(sqlite3.connect(path)) as source, closing(sqlite3.connect(candidate)) as destination:
            source.backup(destination)
        engine = create_engine('sqlite:///' + candidate.as_posix())
        upgrade_database(engine)
        engine.dispose()
        validate_backup(candidate)
        safety = create_backup('before_restore')
        live = database_path()
        db.session.remove()
        db.engine.dispose()
        with closing(sqlite3.connect(candidate)) as source, closing(sqlite3.connect(live)) as destination:
            source.backup(destination)
        return safety
    finally:
        if engine:
            engine.dispose()
        candidate.unlink(missing_ok=True)
