# One-directory build: only code and resources, never instance/ or user databases.
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = [('app/templates','app/templates'),('app/static','app/static'),
         ('app/translations','app/translations'),('migrations','migrations'),
         ('build/third-party-licenses','third-party-licenses')]
datas += collect_data_files('babel')
a = Analysis(['launcher.py'], pathex=[], binaries=[], datas=datas,
             hiddenimports=collect_submodules('app.blueprints') + ['sqlalchemy.dialects.sqlite','alembic'],
             hookspath=[], runtime_hooks=[], excludes=['pytest'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz,a.scripts,[],exclude_binaries=True,name='FinancialTracker',
          debug=False,strip=False,upx=False,console=False,version='build/version-info.txt')
coll = COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='FinancialTracker')
