"""Collect installed runtime licenses without adding user files to the bundle."""
from importlib import metadata
from pathlib import Path
import shutil
import sys

root = Path(__file__).resolve().parents[1]
target = root / 'build' / 'third-party-licenses'
target.mkdir(parents=True, exist_ok=True)
index = ['Third-party distributions in the build environment:']
for distribution in sorted(metadata.distributions(), key=lambda item: item.metadata['Name'].lower()):
    name = distribution.metadata['Name']
    index.append(f'{name} {distribution.version}')
    for relative in distribution.files or []:
        if any(word in relative.name.lower() for word in ('license', 'copying', 'notice')) and '.dist-info/' in str(relative).replace('\\', '/'):
            source = Path(distribution.locate_file(relative))
            if source.is_file():
                folder = target / name
                folder.mkdir(exist_ok=True)
                shutil.copy2(source, folder / relative.name)
for base in (Path(sys.base_prefix), Path(sys.base_prefix).parent):
    for name in ('LICENSE.txt', 'LICENSE'):
        if (base / name).is_file():
            shutil.copy2(base / name, target / 'Python-LICENSE.txt')
(target / 'DISTRIBUTIONS.txt').write_text('\n'.join(index)+'\n', encoding='utf-8')
