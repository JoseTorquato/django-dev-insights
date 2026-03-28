# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

django-dev-insights is a Django middleware package that provides real-time, per-request performance diagnostics: query counts, duplicate SQL detection (N+1), slow query identification, connection tracking, and optional stack traces. It only activates when `DEBUG=True`.

## Commands

```bash
# Format check
python -m black --check .

# Lint (scoped to project dirs)
python -m flake8 dev_insights tests .github .

# Run tests with coverage
python -m pytest --cov=dev_insights --cov-report=term-missing -q

# Run a single test
python -m pytest tests/test_formatters_and_config.py::TestClassName::test_name -q
```

## Code Style

- Black formatter, line-length 88, target Python 3.10+
- Flake8 with E203/W503 ignored, max line length 88
- Config: `pyproject.toml` (black), `.flake8` (flake8)

## Architecture

```
dev_insights/
├── middleware.py          # DevInsightsMiddleware — orchestrates request lifecycle
├── config.py              # get_config() reads DEV_INSIGHTS_CONFIG from Django settings
├── formatters.py          # format_output() — text (colored) or JSON output
├── trace.py               # Stack trace capture with project-frame filtering
├── sql_trace.py           # Monkeypatches Django's CursorDebugWrapper
└── collectors/
    ├── db.py              # DBCollector — queries, duplicates, slow queries, timing
    └── connection.py      # ConnectionCollector — setup queries, connection reopens
```

**Request flow:** Middleware receives request → initializes enabled collectors → collectors gather metrics during request processing → middleware aggregates results → formatter produces text or JSON output → output goes to stdout or Python logger.

**Collector pattern:** Each collector implements a consistent interface (start/collect/results). The middleware enables collectors based on `ENABLED_COLLECTORS` config. Adding a new collector means creating a class in `collectors/` and registering it in the middleware.

**Key design decisions:**
- Configuration is lazy-loaded via `get_config()` which merges user's `DEV_INSIGHTS_CONFIG` with defaults
- `sql_trace.py` wraps `CursorDebugWrapper.execute` with try/except to safely inject traceback capture
- `trace.py` filters stack frames into project vs. external (stdlib/venv) to surface relevant code paths
- `DISPLAY_LIMIT` truncates output; JSON includes `_omitted` counts

## Testing

Tests are in `tests/test_formatters_and_config.py`. They cover formatters, config reloading, and middleware logging. Tests use `override_settings` and `importlib.reload` to test configuration changes.

## Package Info

- Supports Python 3.8–3.11, Django 3.2+
- CI runs on Python 3.10 and 3.11
- Dependencies: Django>=3.2, colorama>=0.4.0
- Published as `pip install django-dev-insights`
- Version tracked in both `dev_insights/__init__.py` and `setup.py`
