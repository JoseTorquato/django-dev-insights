# Changelog

All notable changes to this project are documented in this file.

Format inspired by [Keep a Changelog](https://keepachangelog.com/). Versions follow simple semantic versioning (major.minor.patch).

## [0.3.0] - 2026-03-28

### Added
- **Template Collector**: measures render time of each Django template per request. Opt-in via `ENABLED_COLLECTORS: ['db', 'connection', 'template']`.
- **HTML Panel**: browse recent request metrics at `/__devinsights__/`. Dark theme, severity colors (green/yellow/red), expandable detail rows for duplicates/slow queries/templates, path filtering. Only available when `DEBUG=True`.
- `EXCLUDE_PATHS` config option: list of URL prefixes to skip entirely (e.g. `/static/`, `/favicon.ico`, `/health/`). Requests matching any prefix bypass all collector processing.
- `PANEL_HISTORY_SIZE` config option: controls how many recent requests the HTML panel keeps in memory (default: 50).
- New test files: `test_collectors.py`, `test_middleware.py`, `test_trace.py`, `test_sql_trace.py`, `test_template_collector.py`, `test_panel.py` — test count went from 5 to 43.
- Python 3.12/3.13 and Django 5.1/5.2 classifiers.
- `[project.urls]` section in `pyproject.toml` (Homepage, Repository, Changelog).

### Changed
- **Refactored formatters**: all text output logic (duplicate details, slow queries, connection setup, templates) moved from `middleware.py` into `formatters.py`. The middleware now only orchestrates collectors and calls `format_output()` which returns the complete output string.
- Migrated package metadata from `setup.py` to `pyproject.toml` (`[project]` table with build-system, dependencies, classifiers).
- README rewritten in English for PyPI.

### New files
- `dev_insights/collectors/template.py` — TemplateCollector
- `dev_insights/template_trace.py` — monkeypatch for `Template.render`
- `dev_insights/store.py` — in-memory ring buffer for panel history
- `dev_insights/views.py` — HTML panel view
- `dev_insights/urls.py` — URL configuration for the panel
- `dev_insights/panel.html` — HTML template (dark theme dashboard)

### Notes / Upgrade
- No breaking changes. Existing `DEV_INSIGHTS_CONFIG` settings continue to work.
- Template collector is opt-in — add `'template'` to `ENABLED_COLLECTORS` to enable.
- To enable the HTML panel, add to your `urls.py`:

```python
path('__devinsights__/', include('dev_insights.urls')),
```

- New config keys default to safe values:

```python
DEV_INSIGHTS_CONFIG = {
    'EXCLUDE_PATHS': [],          # no paths excluded
    'PANEL_HISTORY_SIZE': 50,     # last 50 requests
}
```

## [0.2.1] - 2025-10-14

### Added
- ConnectionCollector: detects setup queries per connection (e.g. `SET search_path`, `SELECT VERSION`) and reports connection reopens.
- Traceback capture: captures stack traces for slow queries, duplicate queries, and setup queries when enabled via `ENABLE_TRACEBACKS`.
- New helper `dev_insights/sql_trace.py` that injects (monkeypatch) tracebacks into `connection.queries` entries at execution time (active only when `ENABLE_TRACEBACKS=True` and `DEBUG=True`).
- Config option `ENABLED_COLLECTORS` to enable/disable collectors individually (`db`, `connection`).

### Changed
- Formatted middleware output now prints tracebacks (when available) alongside slow/duplicate/setup queries.
- `formatters` and `middleware` updated to support new fields (traceback) and print per-connection summaries.

### Notes / Upgrade
- To enable traceback capture (development only), configure in `settings.py`:

```python
DEV_INSIGHTS_CONFIG = {
    'ENABLE_TRACEBACKS': True,
    'TRACEBACK_DEPTH': 6,
    'ENABLED_COLLECTORS': ['db', 'connection'],
}
```

- If you use `django-tenants` or another multi-tenant solution, place the tenant middleware **before** `DevInsightsMiddleware` to avoid repeated `SET search_path`; see the README.

## [0.1.1] - 2025-10-01

### Added
- Initial release (DBCollector): query count per request, total DB time, duplicate query detection (N+1), and listing of duplicated SQLs.

## How to publish a new release

1. Update the version in `pyproject.toml` and `dev_insights/__init__.py`.
2. Commit and tag:

```bash
git add CHANGELOG.md pyproject.toml dev_insights/__init__.py
git commit -m "chore(release): 0.3.0"
git tag -a v0.3.0 -m "v0.3.0"
git push origin main --tags
```

3. Build and upload to PyPI:

```bash
python -m build
twine upload dist/*
```
