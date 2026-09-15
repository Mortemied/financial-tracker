"""Generate Windows version info from the one application version constant."""
from pathlib import Path
import runpy

root = Path(__file__).resolve().parents[1]
metadata = runpy.run_path(str(root / 'app/version.py'))
version = metadata['VERSION']
number = tuple(int(part) for part in version.split('.')) + (0,)
(root / 'build').mkdir(exist_ok=True)
content = f'''VSVersionInfo(
  ffi=FixedFileInfo(filevers={number!r}, prodvers={number!r}, mask=0x3f,
                   flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('040904B0', [
    StringStruct('FileDescription', {metadata['APP_NAME']!r}),
    StringStruct('FileVersion', {version!r}),
    StringStruct('ProductName', {metadata['APP_NAME']!r}),
    StringStruct('ProductVersion', {version!r}),
    StringStruct('InternalName', 'FinancialTracker'),
    StringStruct('OriginalFilename', 'FinancialTracker.exe')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])])
'''
(root / 'build/version-info.txt').write_text(content, encoding='utf-8')
