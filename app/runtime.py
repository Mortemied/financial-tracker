"""Writable state is separate from bundled application resources."""
import os
import sys
from pathlib import Path
import secrets


def data_directory():
    if os.getenv('FINANCIAL_TRACKER_DATA_DIR'):
        return Path(os.environ['FINANCIAL_TRACKER_DATA_DIR']).resolve()
    if getattr(sys, 'frozen', False):
        return Path(os.getenv('LOCALAPPDATA', str(Path.home() / 'AppData/Local'))) / 'FinancialTracker'
    return Path(__file__).resolve().parent.parent / 'instance'


def resource_directory():
    return Path(__file__).resolve().parent.parent


def local_secret(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / 'secret.key'
    if not path.exists():
        try:
            with path.open('x', encoding='ascii') as stream:
                stream.write(secrets.token_hex(32))
        except FileExistsError:
            pass
    return path.read_text(encoding='ascii').strip()
