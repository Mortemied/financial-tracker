from pathlib import Path
import sqlite3
from contextlib import closing
from datetime import datetime
from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from app.runtime import resource_directory

HEAD = '0003_release'


def upgrade_database(engine, backup_directory=None):
    """A shared SQLAlchemy transaction supports both file and in-memory SQLite."""
    with engine.connect() as connection:
        current = MigrationContext.configure(connection).get_current_revision()
    if current == HEAD:
        return False
    path = engine.url.database
    if backup_directory and engine.dialect.name == 'sqlite' and path and path != ':memory:' and Path(path).is_file() and Path(path).stat().st_size:
        directory = Path(backup_directory)
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / ('before_migration_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.db')
        with closing(sqlite3.connect(path)) as source, closing(sqlite3.connect(target)) as destination:
            source.backup(destination)
    config = Config()
    config.set_main_option('script_location', str(resource_directory() / 'migrations'))
    with engine.begin() as connection:
        config.attributes['connection'] = connection
        command.upgrade(config, 'head')
    return True
