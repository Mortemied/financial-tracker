# Architecture decisions

## Boundaries

```text
HTTP request → Blueprint → validation/service → SQLAlchemy → SQLite
                                      ↓
                              pure analytics
                                      ↓
Jinja / Chart.js ← localized presentation adapter ← numeric results + keys
```

`app/__init__.py` owns wiring. `extensions.py` contains unbound extensions, allowing independent applications in tests. Ten Blueprints divide navigation and route responsibility. Services do not depend on Flask request objects, templates or language settings. They accept mappings or primitive values. The analytics module has no Flask or SQLAlchemy imports and can operate on any record-like object with the required attributes.

The ORM is used directly inside persistence services rather than introducing a generic repository abstraction. This avoids unnecessary indirection in a learning project. If the data store changes, services remain the boundary consumed by routes.

## Money and dates

All stored monetary values are positive integer cents. Transaction type supplies the sign. Parsing uses Decimal and rejects non-finite, negative, zero, over-limit and sub-cent values. There is no floating-point persistence. Fractions converted to JavaScript numbers are for chart visualization only. Display amounts are formatted from Decimal via Babel.

Transaction dates are calendar dates. Creation/update timestamps use UTC. Budgets store the first date of their month and have a unique category/month pair. Period boundaries are inclusive. The current month in analytics ends today; a custom period can include future-dated entries. Dashboard month totals cover the entire selected month, while the current balance stops at today. Balance history includes the opening balance from records before its chart period.

## Localization

Catalogs are loaded once per application and language selection is read from persistent workspace settings for each request. Changing preferences affects all browsers using this local workspace. Missing translations fall back to English, and tests enforce parity of keys and format placeholders. System categories never store translated labels.

Insights return `{key, params, category_id?}` so the same financial logic supports any language. Views look up the category label and translate the message. No generated insight is investment advice or a prediction: they describe the existing records.

## Mutation and security flow

POST forms carry CSRF tokens. Validation happens before mutation and route errors keep transaction form input available. SQLAlchemy parameterizes queries. Jinja autoescapes user data and JSON passed to Chart.js is escaped inside a data attribute. Text is inserted into chart data tables using `textContent`. CSV descriptions/category labels are escaped when they could be treated as spreadsheet formulas.

Category deletion is blocked for system categories and for custom categories referenced by a transaction or budget. Changing the type of a used custom category is also blocked. Security headers disallow framing and script sources other than local static files. A JSON translation adapter supplies localized 400/404/413/500 pages and CSRF messages.

This is not an authenticated shared system. CSRF protection and output escaping do not replace authentication. Add user ownership and authorization before exposing personal records outside the local machine.

## Database evolution

Alembic is invoked programmatically through one shared SQLAlchemy connection. Revision `0001_v1` adopts the original four-table schema without replacing records; `0002_v2` adds `Transaction.deleted_at`, Goal and ImportBatch. `0003_release` adds Goal.updated_at and backfills it from created_at, preserving existing goal values. Existing file databases receive an online SQLite backup before an upgrade. Running initialization again is a no-op at the current revision. Downgrades are intentionally refused to avoid destructive schema rollback.

Restore validates integrity, required columns, references and preferences; copies the uploaded database to an isolated candidate; migrates that candidate; then creates a safety snapshot and uses SQLite's backup API to replace the live database. Connections are explicitly closed (context-manager exit alone is insufficient on Windows). A per-app request lock serializes restore and financial requests. This assumes the managed single-instance launcher; separate manual Flask processes must not share a database during restore.

For scale: move date/category aggregations into SQL, keep the pure analytics API for reporting and tests, paginate APIs, and add indexes based on observed queries. Current in-memory aggregation is intended for personal datasets, not millions of records.

## Import extension

`ImportBatch` stores an uploaded preview and category mapping, scoped to the browser session with an unpredictable ID. Preview never creates Transaction rows. Validation and duplicate detection are repeated at explicit confirmation. All accepted rows and completion time commit together. A completed batch cannot be imported twice. Duplicates compare date, integer amount, trimmed description and type, including repeats within the file. Unrecognized categories require mapping to the matching type. Staging expires after 24 hours; entries older than two days are cleaned on the next upload.

## Desktop runtime

`launcher.py` obtains an OS file lock per data directory before app initialization. Waitress binds loopback with port 0; the OS selects a free port. A random health identity verifies the server before opening the browser or reusing `server.json`. Repeated launches reopen the existing server. Settings shutdown signals the launch loop; metadata and lock are released. `app/runtime.py` separates bundle resources from persistent data: source uses instance/, frozen uses LOCALAPPDATA/FinancialTracker. An environment override supports isolated tests.

PyInstaller onedir bundles local assets and migration scripts; personal data and secrets never enter the bundle. Native file-system protections apply; this is a local single-person tool.

## New financial behavior

Deletion timestamps a row; shared report/export queries exclude it. The signed Undo token contains both ID and deletion timestamp, with a server-enforced 20-second lifetime. A token for an old deletion cannot undo a later deletion. Records remain soft deleted; there is no separate trash UI.

Goal money is independent of transactions and workspace balance. Each goal has its own currency; there is no exchange conversion or cross-currency total. Budget copy previews each category, skips existing category/month limits and inserts missing limits in one commit. Month comparisons deliberately use the previous full month and return no percentage with a zero baseline.

## Frontend

CSS custom properties define both themes. Layout switches from sidebar to a bottom navigation and expandable menu. At phone widths, transaction rows become card-like blocks retaining all data and actions. JavaScript manages navigation, confirmation, dependent form options, custom-period fields, Quick Add, Undo feedback and Chart.js. Quick Add submits to a validated JSON endpoint and reloads the current page after success so totals and charts agree with persisted data. Graphs include accessible data tables. No reference screenshot or remote asset is embedded in the interface.

## Release hardening

The version is centralized in app/version.py and read by UI, launcher, Windows metadata and packaging tools. The About section omits the repository link until a real URL is configured. Shutdown is CSRF-protected POST and loopback-only; the managed launcher accepts only localhost host names.

SQLite registers a deterministic Unicode casefold function for description search and custom-category duplicate detection. This avoids SQLite's ASCII-only lower/LIKE behavior. Categories are cached only within one request; static requests do not query preferences. Dashboard reuses the month calculation result.

Database failure responses bypass the database-backed layout, so a failed settings query cannot recursively break error rendering. JSON Quick Add also receives localized CSRF/database errors. The desktop formatter retains traceback locations and exception type, but omits exception values and SQL parameters. Backup validation rejects executable triggers/views, unknown schema revisions, incomplete stamped schemas and invalid financial references/types/dates before replacing the live DB.

Runtime, test and build dependencies are separated. The release packager includes only the executable, required runtime resources, license notices and bilingual quick-start text. The data directory is never used as a packaging input.
