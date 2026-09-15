import os
from pathlib import Path
import secrets
import sqlite3
import ipaddress
from flask import Blueprint, current_app, request, redirect, url_for, flash, session, render_template, abort
from app.services.backups import create_backup, backup_directory, validate_backup, restore_backup
from app.services.transactions import ValidationError
from app.localization import translate
from .shared import report_error

bp = Blueprint('backups',__name__,url_prefix='/backups')


@bp.post('/create')
def create():
    try:
        target = create_backup()
        flash(translate('backup.created',name=target.name),'success')
    except (OSError,sqlite3.Error,ValidationError) as error:
        current_app.logger.error('Backup creation failed (%s)',type(error).__name__)
        report_error(error if isinstance(error,ValidationError) else ValidationError('error.backup_failed'))
    return redirect(url_for('settings.index'))


@bp.post('/open')
def open_folder():
    try:
        directory = backup_directory()
    except OSError:
        current_app.logger.error('Backup directory unavailable')
        report_error(ValidationError('error.backup_failed'))
        return redirect(url_for('settings.index'))
    if os.name == 'nt' and not current_app.testing:
        try:
            os.startfile(str(directory))
        except OSError:
            flash(translate('backup.folder_path',path=str(directory)),'error')
    else:
        flash(translate('backup.folder_path',path=str(directory)),'success')
    return redirect(url_for('settings.index'))


@bp.post('/preview')
def preview():
    upload = request.files.get('backup')
    if not upload:
        report_error(ValidationError('error.backup_invalid'))
        return redirect(url_for('settings.index'))
    directory = Path(current_app.config['DATA_DIR']) / 'restore-previews'
    token = secrets.token_hex(24)
    path = directory / (token+'.db')
    try:
        directory.mkdir(parents=True,exist_ok=True)
        upload.save(path)
        counts = validate_backup(path)
        session['restore_token'] = token
        return render_template('restore_preview.html',active='settings',counts=counts,token=token)
    except (OSError,ValidationError) as error:
        current_app.logger.warning('Backup preview rejected (%s)',type(error).__name__)
        path.unlink(missing_ok=True)
        report_error(error if isinstance(error,ValidationError) else ValidationError('error.backup_failed'))
        return redirect(url_for('settings.index'))


@bp.post('/restore')
def restore():
    token = session.get('restore_token')
    if not token or token != request.form.get('token') or request.form.get('confirmed') != 'yes':
        abort(400)
    path = Path(current_app.config['DATA_DIR']) / 'restore-previews' / (token+'.db')
    try:
        safety = restore_backup(path)
        session.clear()
        flash(translate('backup.restored',name=safety.name),'success')
    except Exception:
        current_app.logger.exception('Backup restore failed')
        flash(translate('error.backup_failed'),'error')
    finally:
        path.unlink(missing_ok=True)
    return redirect(url_for('settings.index'))


@bp.post('/quit')
def quit_app():
    try:
        local = ipaddress.ip_address(request.remote_addr or '').is_loopback
    except ValueError:
        local = False
    if not local:
        abort(403)
    stop = current_app.config.get('STOP_APPLICATION')
    if not stop:
        abort(404)
    stop()
    return render_template('stopped.html',active='settings')
