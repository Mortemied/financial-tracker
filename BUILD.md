# Windows build and release

## User package

Double-click `FinancialTracker.exe` in the extracted release folder. Keep `_internal` beside the EXE. Python is bundled; no console commands are needed. Use Settings → Quit application to stop the server.

Default data stays in `%LOCALAPPDATA%\FinancialTracker`, outside the application folder. Updating the folder does not delete the database. Move data to another PC using Settings backup/restore, not by copying the EXE alone.

## Build from source

Windows x64 and Python 3.11+ x64 are required for building. Run `build.bat` (double-click). It prepares `.venv`, installs `requirements-build.txt`, gathers dependency notices, generates Windows version metadata and invokes PyInstaller using `FinancialTracker.spec`.

The version is read from `app/version.py`. Outputs:

- `dist/FinancialTracker/FinancialTracker.exe` and `_internal/`.
- `release/FinancialTracker-v<version>-Windows/` with EXE, runtime, LICENSE and short bilingual README.txt.
- `release/FinancialTracker-v<version>-Windows.zip` and `.sha256`, ready to attach to a GitHub Release.

The user package contains no tests, virtual environment, repository, build cache, developer docs, personal database or secret. Templates, translations and Alembic revision scripts are required runtime resources inside `_internal`, not a second source checkout. Previous generated package folders are preserved with a `.previous-` name when repackaging; only the versioned ZIP should be sent to testers.

`requirements.txt` is runtime only; `requirements-dev.txt` adds pytest; `requirements-build.txt` adds PyInstaller. `requirements.lock.txt` and `requirements-build.lock.txt` record tested environment versions. The normal bootstrap uses direct requirements; byte-for-byte reproducible binaries are not promised.

## Standalone smoke

```powershell
$env:FINANCIAL_TRACKER_DATA_DIR = Join-Path $env:TEMP 'FinancialTracker-smoke'
$p = Start-Process .\dist\FinancialTracker\FinancialTracker.exe -ArgumentList '--smoke','--no-browser' -WindowStyle Hidden -Wait -PassThru
$p.ExitCode
Get-Content (Join-Path $env:FINANCIAL_TRACKER_DATA_DIR 'smoke-result.json')
Remove-Item Env:FINANCIAL_TRACKER_DATA_DIR
```

Smoke runs real Waitress HTTP checks for pages, CSS, JavaScript and font resources. It confirms frozen Python paths stay inside the bundle and exits. Expected: exit 0, `ok: true`, `frozen: true`, correct version. Remove old test-result files or use a fresh folder when testing a new build.

For source launch, `start.bat --smoke --no-browser` runs equivalent checks. `--setup --no-browser` applies migrations without serving; `--no-browser` runs without opening a tab. `FT_NONINTERACTIVE=1` disables BAT pause for CI.

## Update verification

1. Create a test record and backup in the previous build, then quit it.
2. Run the new EXE using the same data directory.
3. Check original records/preferences and migration backup.
4. Start EXE again: it should reuse the same process/port.
5. Quit from Settings and reopen: data should persist.

Never point a test at your only live financial database. Use a copy. On this development machine the release is also tested after relocation outside the project with PATH containing no Python and with a separate LOCALAPPDATA profile. That does not substitute for a physical second-machine test; see the verification report.

## GitHub publication

The repository has no remote configured yet. Create your GitHub repository, commit the source files that are not ignored, add its actual URL as `origin`, and push. Do not commit `instance/`, `.env`, `.venv/`, `build/`, `dist/`, `release/`, logs or backups.

Create a tag matching `app/version.py` and attach the generated Windows ZIP and checksum to its GitHub Release. `.github/workflows/windows-build.yml` can also produce a tested artifact on Windows runners. It uploads a workflow artifact; it does not silently publish a GitHub Release. After a public URL exists, set `REPOSITORY_URL` in `app/version.py` to enable the About link.

## Troubleshooting

- Missing Python affects source setup only; send friends the portable ZIP.
- Keep the whole folder together; `_internal` is required.
- Read `logs/application.log` in the data directory on a startup failure.
- A browser tab can be reopened by starting EXE again.
- Closing a tab does not stop the app. Use Settings → Quit application.
- Unsigned Windows builds may show an unknown-publisher notice. Signing is not configured; do not disable system protections.
- Windows Sandbox / a separate clean Windows machine was not available during local verification. The GitHub Windows workflow offers an additional fresh-runner check after publication.

## References

- [PyInstaller runtime paths](https://pyinstaller.org/en/stable/runtime-information.html)
- [PyInstaller onedir behavior](https://pyinstaller.org/en/stable/operating-mode.html)
- [Alembic commands](https://alembic.sqlalchemy.org/en/latest/api/commands.html)
