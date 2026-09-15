"""Make a minimal, versioned friend package and GitHub Release ZIP."""
from pathlib import Path
import hashlib
import runpy
import shutil
import uuid
import zipfile

root = Path(__file__).resolve().parents[1]
version = runpy.run_path(str(root / 'app/version.py'))['VERSION']
release_root = root / 'release'
name = f'FinancialTracker-v{version}-Windows'
destination = release_root / name
release_root.mkdir(exist_ok=True)
if destination.exists():
    # Preserve previous generated packages instead of deleting an arbitrary folder.
    destination.rename(release_root / f'.previous-{name}-{uuid.uuid4().hex[:8]}')
source = root / 'dist/FinancialTracker'
assert (source / 'FinancialTracker.exe').is_file()
destination.mkdir()
shutil.copy2(source / 'FinancialTracker.exe',destination)
shutil.copytree(source / '_internal',destination / '_internal',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
shutil.copy2(root / 'LICENSE',destination / 'LICENSE')
readme = f'''Financial Tracker
Version {version}

1. Extract the entire folder.
2. Run FinancialTracker.exe. Your browser opens automatically.
3. Keep the _internal folder beside the EXE. Python is included.
4. Your data stays on this computer: %LOCALAPPDATA%\\FinancialTracker
5. Exit through Settings > Quit application. Closing the tab leaves the app running.

To move your records: Settings > Create backup > Open backup folder.
Restore that .db file through Settings on the new computer.
No user records are included in this package.

РУССКИЙ
1. Распакуйте всю папку.
2. Запустите FinancialTracker.exe — браузер откроется автоматически.
3. Папку _internal оставьте рядом с EXE. Python устанавливать не нужно.
4. Данные: %LOCALAPPDATA%\\FinancialTracker
5. Выход: Настройки > Завершить приложение. Закрытие вкладки не завершает сервер.

Перенос записей: Настройки > Создать резервную копию > Открыть папку.
На новом компьютере восстановите .db через Настройки.
В этом архиве нет пользовательских финансовых записей.

License: MIT. Dependency notices: _internal/third-party-licenses
'''
(destination / 'README.txt').write_text(readme,encoding='utf-8-sig')
archive = release_root / (name+'.zip')
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as output:
    for path in sorted(destination.rglob('*')):
        if path.is_file():
            assert path.suffix not in ('.db','.sqlite','.sqlite3') and path.name not in ('.env','secret.key','server.json')
            output.write(path,path.relative_to(release_root))
with zipfile.ZipFile(archive) as output:
    assert output.testzip() is None
(release_root / (name+'.sha256')).write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+'  '+archive.name+'\n',encoding='ascii')
print(f'Release ready: {archive}')
