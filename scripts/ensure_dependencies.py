"""Install only if the requirements changed or an installed version is missing."""
import hashlib
import importlib.metadata
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
requirements = root / 'requirements.txt'
digest = hashlib.sha256(requirements.read_bytes()).hexdigest()
marker = root / '.venv/requirements.sha256'
ready = marker.exists() and marker.read_text() == digest
for line in requirements.read_text().splitlines():
    if '==' not in line or line.startswith('#'):
        continue
    name, version = line.strip().split('==')
    try:
        ready = ready and importlib.metadata.version(name) == version
    except importlib.metadata.PackageNotFoundError:
        ready = False
if not ready:
    result = subprocess.run([sys.executable,'-m','pip','install','--disable-pip-version-check','-r',str(requirements)],cwd=root)
    if result.returncode:
        raise SystemExit(result.returncode)
    marker.write_text(digest)
print('Dependencies are ready. / Зависимости готовы.')
