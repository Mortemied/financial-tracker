import os
from pathlib import Path
import click
import threading
from app.runtime import data_directory
from dotenv import load_dotenv
from flask import Flask, g, render_template, request, jsonify
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from flask_wtf.csrf import CSRFError
from app.extensions import db, csrf
from app.config import Config, ProductionConfig
from app.version import VERSION, APP_NAME, REPOSITORY_URL


@event.listens_for(Engine, 'connect')
def enable_sqlite_foreign_keys(connection, _):
    if connection.__class__.__module__.startswith('sqlite3'):
        connection.create_function('unicode_casefold',1,lambda value: value.casefold() if value else '',deterministic=True)
        cursor = connection.cursor()
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.close()


def create_app(config=None):
    from app.runtime import resource_directory
    import sys
    load_dotenv((data_directory() if getattr(sys, 'frozen', False) else resource_directory()) / '.env')
    app = Flask(__name__, instance_relative_config=True, instance_path=str(data_directory()))
    app.config.from_object(ProductionConfig if os.getenv('APP_ENV') == 'production' else Config)
    # Config classes load at import time; re-read .env values for direct python run.py.
    if os.getenv('SECRET_KEY'):
        app.config['SECRET_KEY'] = os.environ['SECRET_KEY']
    if os.getenv('DATABASE_URL'):
        app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
    if config:
        app.config.from_mapping(config) if isinstance(config, dict) else app.config.from_object(config)
    if not app.testing and os.getenv('APP_ENV') != 'production' and app.config['SECRET_KEY'] in ('replace-with-a-random-secret', 'development-only-change-before-deployment'):
        from app.runtime import local_secret
        app.config['SECRET_KEY'] = local_secret(app.instance_path)
    if os.getenv('APP_ENV') == 'production' and app.config['SECRET_KEY'] in ('replace-with-a-random-secret', 'development-only-change-before-deployment'):
        raise RuntimeError('Set a random SECRET_KEY for production.')
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    app.config.setdefault('DATA_DIR', app.instance_path)
    app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024
    app.extensions['data_lock'] = threading.RLock()
    db.init_app(app)
    from app.localization import init_localization
    init_localization(app)
    from app.blueprints import register_blueprints
    register_blueprints(app)

    @app.before_request
    def lock_database():
        app.extensions['data_lock'].acquire()
        g.data_lock_held = True

    @app.teardown_request
    def unlock_database(error=None):
        if getattr(g, 'data_lock_held', False):
            g.data_lock_held = False
            app.extensions['data_lock'].release()

    @app.before_request
    def preferences():
        g.pop('category_cache', None)
        if request.endpoint == 'static':
            return
        from app.services.preferences import get_settings
        g.settings = get_settings()
        if g.settings:
            g.safe_preferences = (g.settings.language, g.settings.theme)

    csrf.init_app(app)

    @app.context_processor
    def context():
        from datetime import date
        from app.blueprints.shared import categories
        return {'settings': getattr(g, 'settings', None), 'languages': app.config['LANGUAGES'],
                'currencies': app.config['CURRENCIES'], 'today': date.today(),
                'app_version': VERSION, 'app_name': APP_NAME, 'repository_url': REPOSITORY_URL,
                'quick_categories': [] if getattr(g,'fatal_error',False) else categories()}

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
        if request.endpoint != 'static':
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        if request.accept_mimetypes.best == 'application/json':
            from app.localization import translate
            return jsonify(ok=False,error=translate('error.csrf')),400
        return render_template('error.html', code=400, message='error.csrf'), 400

    def fatal_response(code, message):
        # Never ask a failed database for settings/categories while reporting its failure.
        from types import SimpleNamespace
        from app.localization import translate
        g.fatal_error = True
        language, theme = getattr(g,'safe_preferences',('en','light'))
        g.settings = SimpleNamespace(language=language,theme=theme,currency='NOK')
        if request.accept_mimetypes.best == 'application/json':
            return jsonify(ok=False,error=translate(message)),code
        return render_template('fatal.html',code=code,message=message,language=language,theme=theme),code

    @app.errorhandler(SQLAlchemyError)
    def database_error(error):
        db.session.rollback()
        app.logger.error('Database operation failed (%s)',type(error).__name__)
        return fatal_response(503,'error.database')

    for code in (400, 403, 404, 413, 500):
        def handler(error, status=code):
            if status == 500:
                db.session.rollback()
                return fatal_response(500,'error.500')
            if status == 413 and request.accept_mimetypes.best == 'application/json':
                from app.localization import translate
                return jsonify(ok=False,error=translate('error.413')),413
            return render_template('error.html', code=status, message=f'error.{status}'), status
        app.register_error_handler(code, handler)

    @app.cli.command('migrate-db')
    def migrate_db_command():
        from app.services.migrations import upgrade_database
        upgrade_database(db.engine, Path(app.config['DATA_DIR']) / 'backups')
        click.echo('Database is up to date.')

    @app.cli.command('init-db')
    def init_db_command():
        """Create tables and system categories without demo financial records."""
        from app.services.seed import initialize
        initialize()
        click.echo('Database initialized.')

    @app.cli.command('seed-demo')
    def seed_demo_command():
        """Add deterministic demo data to an empty transaction database."""
        from app.services.seed import seed_demo
        click.echo(f'Created {seed_demo()} demo transactions.')

    # A fresh local installation is immediately usable; seed-demo is always opt-in.
    with app.app_context():
        from app.services.seed import initialize
        initialize()
    return app
