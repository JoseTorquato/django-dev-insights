# django-dev-insights

[![PyPI version](https://badge.fury.io/py/django-dev-insights.svg)](https://badge.fury.io/py/django-dev-insights)
[![CI](https://github.com/josetorquato/django-dev-insights/actions/workflows/ci.yml/badge.svg)](https://github.com/josetorquato/django-dev-insights/actions/workflows/ci.yml)

Lightweight, real-time performance diagnostics for Django development — per-request metrics printed to your console, emitted as structured JSON, or viewed in a built-in HTML panel.

---

## Why this project

In real-world Django apps a single view can inadvertently issue dozens or hundreds of SQL queries. Finding the source of those queries is time-consuming. `django-dev-insights` gives you an immediate, per-request snapshot so you can find and fix hot spots during development.

**Real results:**

- Page load reduced from **28s → 1.8s** by identifying and removing 200+ duplicated queries.
- Page load reduced from **8s → 0.3s** by locating an N+1 pattern visible only with large datasets.

---

## Features

- **Per-request metrics**: total time, DB time, query count.
- **Duplicate and similar SQL detection** — exact duplicates (same SQL, same parameters) and *similar* queries (same normalized SQL, different parameters: the classic N+1), with the file and line that ran them when tracebacks are on.
- **Slow query detection** (configurable threshold) with optional stack traces.
- **Connection collector**: detects setup queries (`SET search_path`, `SELECT VERSION`) and connection reopens.
- **Template collector**: measures render time of each Django template per request.
- **HTML panel**: browse recent request metrics at `/__devinsights__/` — dark theme, severity colors, expandable detail rows, path filtering.
- **Path filtering**: skip noisy requests (`/static/`, `/favicon.ico`) via `EXCLUDE_PATHS`.
- **CI guard (pytest)**: a per-view query baseline, versioned in your repo, that only tightens — a request that runs more queries, more N+1-like repeats or more template renders than the baseline fails the test.
- **Two output modes**: colored `text` for interactive development and structured `json` for logs/CI.
- **Logging integration**: emit JSON to Python's `logging` system with optional file rotation.

---

## Installation

```bash
pip install django-dev-insights
```

**Compatibility:** Python 3.10–3.13 and Django 4.2, 5.0, 5.1, 5.2, 6.0 and 6.1 — every one of these Django versions and Python versions is exercised in CI.

---

## Quickstart

Add the middleware to `settings.py` — place it high in the stack to measure the full request lifecycle:

```python
# settings.py
MIDDLEWARE = [
    'dev_insights.middleware.DevInsightsMiddleware',
    # ... other middleware
]
```

Run `python manage.py runserver` and you will see per-request reports in your console (requires `DEBUG = True`).

---

## HTML Panel

Browse recent request metrics in a visual dashboard:

```python
# urls.py
from django.urls import include, path

urlpatterns = [
    path('__devinsights__/', include('dev_insights.urls')),
    # ... your other urls
]
```

Then visit `http://localhost:8000/__devinsights__/` in your browser.

The panel shows a table of recent requests with:
- Severity indicators (green/yellow/red) based on configurable thresholds
- Click on any row to expand duplicate queries, slow queries, and template details
- Filter by path to focus on specific endpoints
- Only available when `DEBUG = True`

---

## Output modes

### Text output (default)

Colored, human-readable lines with expandable detail sections:

```
[DevInsights] Path: /users/45 | Total: 4821.37ms | DB Queries: 36 | DB Time: 4120.5ms | !! DUPLICATES: 12 !! | !! SIMILAR (N+1?): 30 !!
    [Duplicated SQLs]:
      -> (4x) SELECT "users"."id", ...
         Traceback:
         app/views.py:123 in user_detail -> User.objects.filter(...)
    [Similar SQLs (same query, different params)]:
      -> (26x) SELECT "orders"."id", ... WHERE "orders"."user_id" = ?
         at app/views.py:131 in user_detail
    [Slow Queries (> 100ms)]:
      -> [732.1ms] SELECT "reports"."id", ...
    [Templates]: 3 rendered in 45.2ms
      -> [30.1ms] templates/base.html
      -> [12.0ms] templates/users/detail.html
```

In the middleware, the `Traceback:` and `at file:line` lines only appear with `ENABLE_TRACEBACKS = True` (default `False`). With the default, you still get the counts and the SQL, without the origin. `QueryRecorder` and the CI guard always capture the origin.

### JSON output

Structured payload per request — useful for logs, CI, or tooling:

```json
{
  "path": "/api/users/",
  "total_time_ms": 281.93,
  "db_metrics": {
    "query_count": 12,
    "total_db_time_ms": 266.0,
    "duplicate_query_count": 0,
    "duplicate_sqls": [],
    "similar_query_count": 0,
    "similar_sqls": [],
    "slow_queries": []
  },
  "connection_metrics": {
    "total_setup_query_count": 1,
    "setup_queries": {
      "default": [{"sql": "SET search_path = 'public'"}]
    }
  },
  "template_metrics": {
    "template_count": 2,
    "total_render_time_ms": 15.3,
    "templates": [
      {"name": "base.html", "time_ms": 10.1},
      {"name": "home.html", "time_ms": 5.2}
    ]
  }
}
```

---

## Configuration

All settings go in `DEV_INSIGHTS_CONFIG` in your `settings.py`. Defaults shown below:

```python
DEV_INSIGHTS_CONFIG = {
    # Thresholds for severity colors (text mode) and panel indicators
    'THRESHOLDS': {
        'total_time_ms': {'warn': 1000, 'crit': 3000},
        'query_count': {'warn': 20, 'crit': 50},
        'duplicate_query_count': {'warn': 5, 'crit': 10},
    },
    'SLOW_QUERY_THRESHOLD_MS': 100,

    # Stack traces for slow/duplicate/setup queries (adds overhead)
    'ENABLE_TRACEBACKS': False,
    'TRACEBACK_DEPTH': 5,

    # Collectors to enable
    'ENABLED_COLLECTORS': ['db', 'connection'],  # add 'template' to enable

    # Output
    'OUTPUT_FORMAT': 'text',        # 'text' or 'json'
    'DISPLAY_LIMIT': 100,           # max items per list
    'JSON_PRETTY': True,
    'JSON_INDENT': 2,

    # Logging integration
    'OUTPUT_LOGGER_NAME': None,     # logger name for JSON output
    'OUTPUT_LOG_FILE': None,        # auto-attach FileHandler if logger has no handlers

    # Path filtering
    'EXCLUDE_PATHS': [],            # e.g. ['/static/', '/favicon.ico']

    # HTML panel
    'PANEL_HISTORY_SIZE': 50,       # number of recent requests to keep in memory
}
```

---

## Collectors

| Collector | Config key | What it does |
|-----------|-----------|--------------|
| **DBCollector** | `'db'` | Query count, DB time, exact duplicates, similar queries (N+1), slow query detection. Optional stack traces, captured when each query runs. |
| **ConnectionCollector** | `'connection'` | Detects setup queries (`SET search_path`, `SELECT VERSION`, `SHOW`) and connection reopens. |
| **TemplateCollector** | `'template'` | Measures render time of each Django template. Opt-in — add `'template'` to `ENABLED_COLLECTORS`. |

---

## Logging integration

Send structured JSON to your logging system instead of stdout:

```python
# settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'dev_insights_file': {
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': '/var/log/myapp/dev_insights.json',
            'when': 'midnight',
            'backupCount': 7,
            'formatter': 'json_message',
        },
    },
    'formatters': {
        'json_message': {'format': '%(message)s'}
    },
    'loggers': {
        'dev_insights': {
            'handlers': ['dev_insights_file'],
            'level': 'INFO',
            'propagate': False,
        }
    }
}

DEV_INSIGHTS_CONFIG = {
    'OUTPUT_FORMAT': 'json',
    'OUTPUT_LOGGER_NAME': 'dev_insights',
}
```

Or use the simpler auto-attach pattern:

```python
DEV_INSIGHTS_CONFIG = {
    'OUTPUT_FORMAT': 'json',
    'OUTPUT_LOGGER_NAME': 'dev_insights',
    'OUTPUT_LOG_FILE': '/var/log/myapp/dev_insights.json',
}
```

---

## Multi-tenant / django-tenants

If you use `django-tenants`, place the tenant middleware **before** DevInsights to avoid repeated `SET search_path` queries:

```python
MIDDLEWARE = [
    'django_tenants.middleware.main.TenantMainMiddleware',
    'dev_insights.middleware.DevInsightsMiddleware',
    # ...
]
```

Enable `ENABLE_TRACEBACKS` temporarily to locate the code path causing repeated schema switches.

---

## Duplicates vs. similar queries

- **Duplicates** (`duplicate_query_count`): the very same SQL, parameters included, ran more than once. Same meaning as in 0.3.
- **Similar** (`similar_query_count`): queries with the same *signature* — literals and parameters replaced by `?`, `IN (...)` lists of any size collapsed — ran more than once. This is what catches the classic N+1 (`for book in books: book.author`), where each query differs only in the id. Every duplicate is also similar.

The signature is built from the SQL text, not from the ORM, so it also groups `raw()` queries and SQL issued by third-party code.

### Where the origin points

The origin is the innermost frame of *your* code when the query ran. Frames from Django, from this library and from anything under `site-packages` / `dist-packages` are skipped. That has two consequences:

- **N+1 triggered from a template** (`{{ book.author.name }}` in a loop): the query runs while Django renders, so the origin is the line in your view that calls `render(...)`, not the line in the `.html` file.
- **Your own code installed as a regular package** (in `site-packages`) is skipped like any other dependency: the origin falls back to the first frame outside it, which is usually the view that called it. If nothing of yours is on the stack, there is no origin. Editable installs (`pip install -e`) live outside `site-packages` and are reported normally.

## Recording queries without DEBUG

```python
from dev_insights.recorder import QueryRecorder

with QueryRecorder() as rec:
    client.get("/books/")

metrics = rec.metrics()
metrics["similar_query_count"]       # e.g. 10
metrics["similar_sqls"][0]["origin"] # {"file": "shop/views.py", "line": 12, "func": "book_list"}
```

`QueryRecorder` uses `connection.execute_wrapper`, so it works with `DEBUG = False` (Django's test runner and pytest-django force it). It records queries from the current thread, on every database alias. The origin — the innermost frame of your code, skipping Django, this library and installed packages — is captured when the query runs, once per signature.

## CI guard: a per-view query baseline that only tightens

The package ships a pytest plugin (auto-registered, inert until a test uses it). Mark the tests that exercise your views:

```python
import pytest

@pytest.mark.dev_insights
def test_order_list(client):          # pytest-django's client, or django.test.Client()
    client.get("/orders/")
```

The marker also works on classes, including `django.test.TestCase` subclasses. Every request made through Django's test client during a marked test is measured **per view** (HTTP method + URL name):

| metric | meaning |
|---|---|
| `queries` | total SQL queries of the request |
| `similar_queries` | queries that share a normalized signature with another query of the same request — N+1 suspects |
| `templates` | number of template renders (a count, not a time) |

Record the baseline once and commit it:

```bash
pytest --dev-insights-update-baseline
git add dev_insights_baseline.json
```

```json
{
  "version": 1,
  "views": {
    "GET orders:detail": {"queries": 4, "similar_queries": 0, "templates": 3},
    "GET orders:list": {"queries": 3, "similar_queries": 0, "templates": 2}
  }
}
```

One view per line, so a change in the baseline is a one-line diff in the pull request.

From then on, plain `pytest`:

- **gets worse → the test fails**, with everything in one message:

  ```
  dev-insights: GET orders:list got worse than the baseline (dev_insights_baseline.json)
    queries: 3 -> 26
    similar queries (N+1 suspects): 0 -> 23
    most repeated query (23x): SELECT ... FROM "customer" WHERE "customer"."id" = ? LIMIT ?
      at orders/views.py:41 in order_list
    If this is intended, update the baseline: pytest --dev-insights-update-baseline
  ```
- **gets better → passes**, and the end of the run lists the views that can be tightened;
- **a view with no baseline → fails**, so a new endpoint cannot slip in unmeasured. While adopting the guard on many tests at once, `--dev-insights-new-view=warn` (or the ini key `dev_insights_new_view = warn`) lists them at the end of the run instead of failing.

The baseline holds, per view, the worst request seen in the run (a view hit by several tests is held to its heaviest one). Raising a number means running the update and committing the diff, which is what a reviewer sees.

**Keeping the baseline honest**

- **Run the update on the whole suite.** An update on a partial run (`-k`, `-m`, file or test ids, `--lf`, `-x`) adds new views and raises worse ones, but **never lowers** a view and says `PARTIAL RUN` at the end: a subset of the tests may not reach a view's heaviest request.
- **Views that no longer exist** stay in the file until you prune them, on a full run: `pytest --dev-insights-update-baseline --dev-insights-prune`.
- **Use the same database backend locally and in CI.** SQLite and PostgreSQL can differ in query counts for the same code (savepoints, `RETURNING`, bulk operations). Generate the baseline where CI runs, or with the same backend.

**Caches and test order**

A view that reads from a process-wide cache runs fewer queries once another test has warmed it, so the same test could pass in one order and fail in another. That is the worst thing a CI guard can do. Every measured request therefore starts with Django's own caches cleared: `ContentType` (used by generic relations, permissions and the admin log) and `Site`. Your project's caches need the same treatment. List a function that clears each one:

```ini
# pytest.ini / [tool.pytest.ini_options]
[pytest]
dev_insights_clear_caches =
    myproject.settings_cache.clear
    catalog.cache.reset_category_tree
```

Each function is called before every measured request. If you use Django's cache framework (`django.core.cache`) in views, clear it the same way (for example a small function that calls `cache.clear()`), or use `DummyCache` in test settings.

Options:

| option / ini key | what it does |
|---|---|
| `--dev-insights-update-baseline` | write the measured numbers instead of comparing |
| `--dev-insights-prune` | with the update, on a full run: drop views no test hit |
| `--dev-insights-baseline=PATH` / `dev_insights_baseline` | baseline file (default `dev_insights_baseline.json` in the rootdir) |
| `--dev-insights-new-view=fail\|warn` / `dev_insights_new_view` | a view without a baseline fails (default) or only warns |
| `dev_insights_clear_caches` (ini) | functions that clear your caches before each measured request |

Disable the plugin entirely with `-p no:dev_insights`.

Where the query came from: the `at file:line` in a failure is the innermost frame of your code. For an N+1 triggered while rendering a template, that is the `render(...)` line in the view, not the line in the `.html` file.

Template **render time** is deliberately not in the baseline: it varies between CI machines. The count is deterministic.

Limits: requests are measured on the thread that runs the test (Django's sync test client). `AsyncClient` and `live_server` requests are not measured. Run `--dev-insights-update-baseline` without `pytest-xdist` (`-n`). Checking works with it, and the end-of-run notes (improvements, views without a baseline) are collected from the workers and printed once.

### GitHub Actions

```yaml
name: tests
on: [pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt django-dev-insights pytest pytest-django
      # fails the job if any marked view runs more queries, more N+1 repeats
      # or more template renders than dev_insights_baseline.json allows
      - run: pytest
```

### How it relates to other tools

- **`assertNumQueries` (Django) and `django_assert_num_queries` / `django_assert_max_num_queries` (pytest-django)** check one block against a number you write by hand in each test. The guard keeps the numbers in one generated file, per view, plus similar queries and template renders, and lets them go down without editing tests.
- **[django-zeal](https://github.com/taobojlen/django-zeal)** detects N+1 at the ORM level (it knows it was `Book.author` in a loop) and raises immediately. Use it together with this guard: zeal catches the N+1 pattern; the guard catches a view that got heavier than it was, in any SQL — `raw()`, managers, third-party code — and shows where it ran.
- **[django-perf-rec](https://github.com/adamchainz/django-perf-rec)** records the full list of queries per test and fails on any change. The guard records three numbers per view and fails only when one goes up.

---

## Tips

- The middleware only runs when `DEBUG = True` — it depends on `connection.queries`. To measure without `DEBUG` (in tests, for example), use `QueryRecorder` (below).
- Keep `ENABLE_TRACEBACKS` disabled by default — enable only when actively debugging.
- Use `EXCLUDE_PATHS` to filter static files and health checks from the output.
- The HTML panel stores metrics in memory only — data is cleared on server restart.

---

## Contributing

Contributions are welcome. Please open an issue or PR with a clear description and tests.

---

## License

MIT — see [LICENSE](LICENSE) for details.
