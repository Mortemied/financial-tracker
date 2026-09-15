# Financial Tracker 1.0.0 — verification

Verified on 2026-09-14 on Windows 11 x64 with Python 3.12.14, PyInstaller 6.16 and Chromium. Mutating tests used isolated databases. The working database was backed up and migrated only after copy-based validation.

## Automated checks

- 95 tests passed in the development environment and again in a fresh virtual environment (7.65 seconds for the final fresh-environment run).
- Fresh setup.bat installed dependencies; start.bat --smoke --no-browser passed real HTTP checks.
- Python compilation and syntax checks for all three JavaScript files passed.
- Coverage includes cents/validation, transactions, duplicate, deletion/Undo, category uniqueness, budgets/copy, goals/updated_at, reports, Unicode search, CSV mapping/duplicates/session isolation/replay/size/encoding, backup validation/restore, migration preservation, localization, CSRF, shutdown restrictions, database error responses and log redaction.

## Browser checks

Passed: transaction Quick Add/edit/duplicate/delete/Undo; Russian category create/rename/delete; budget copy; goal creation and contribution; backup creation and restore confirmation with safety snapshot; CSV export; filter/sort/pagination persistence; custom analytics dates; RU/EN and light/dark persistence; Russian 404; chart rendering; desktop, tablet and mobile layouts without horizontal overflow.

Checked at 1920x1080, 1366x768, 768x1024 and 390x844. Screenshots use demonstration records. Goal edit/delete and CSV import are covered by automated checks; the import upload/mapping/duplicate/confirmation browser workflow was checked during the preceding v2 verification, not manually repeated for this final build. Unexpected 500 and database failures were injected in automated tests, not through a production browser route.

## Windows artifacts

- build.bat completed and generated the versioned portable ZIP and SHA-256 file.
- The actual ZIP was extracted outside the project; its EXE was launched with Python removed from PATH and without Python environment overrides.
- An older packaged EXE opened an isolated copy of an existing database. After adding a record and closing it, the new packaged EXE migrated that database. Every original value across transactions, categories, budgets, goals and settings was unchanged.
- Repeated EXE launch reused the same process and port. All eight application pages and About passed HTTP checks. Shutdown released the instance lock.
- Fresh-profile EXE smoke passed and asserted that all frozen Python import paths remained inside the bundle.
- The real working database migration preserved all existing values and passed SQLite integrity_check.

These checks used an isolated profile on the development PC, not a second clean Windows PC or VM. Windows Sandbox was unavailable. The executable is unsigned; installer packaging and SmartScreen reputation were not tested.

## Performance sample

With 10,000 synthetic transactions in an in-memory SQLite database, median of three server renders: Dashboard 224 ms, analytics 148 ms, transactions 7 ms, filtered search 20 ms, budgets 6 ms. This is a local diagnostic, not a production or physical-phone benchmark.

## Publication status and limits

Source, README, build instructions, MIT license, screenshots, CI workflows and release artifacts are prepared. No GitHub remote was supplied; no push, hosted workflow run or public GitHub Release was performed. The About repository link remains hidden until a real repository URL is configured.

The portable app binds to loopback and stores data locally; phone access over a network, cloud synchronization and automatic currency conversion are not supported. Mobile layout was checked with browser viewport emulation, not a physical phone.
