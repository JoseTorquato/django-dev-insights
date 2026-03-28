# django-dev-insights

[![PyPI version](https://badge.fury.io/py/django-dev-insights.svg)](https://badge.fury.io/py/django-dev-insights)
[![CI](https://github.com/josetorquato/django-dev-insights/actions/workflows/ci.yml/badge.svg)](https://github.com/josetorquato/django-dev-insights/actions/workflows/ci.yml)

Lightweight, real-time performance diagnostics for Django development — per-request metrics printed to your console, emitted as structured JSON, or viewed in a built-in HTML panel.

---

## Why this project

In real-world Django apps a single view can inadvertently issue dozens or hundreds of SQL queries. Finding the source of those queries is time-consuming. `django-dev-insights` gives you an immediate, per-request snapshot so you can find and fix hot spots during development.

**Real results:**

- Page load reduced from **28s → 3.8s** by identifying and removing 200+ duplicated queries.
- Page load reduced from **8s → 1.8s** by locating an N+1 pattern visible only with large datasets.

---

## Features

- **Per-request metrics**: total time, DB time, query count.
- **Duplicate SQL detection** with optional stack traces — finds N+1 patterns instantly.
- **Slow query detection** (configurable threshold) with optional stack traces.
- **Connection collector**: detects setup queries (`SET search_path`, `SELECT VERSION`) and connection reopens.
- **Template collector**: measures render time of each Django template per request.
- **HTML panel**: browse recent request metrics at `/__devinsights__/` — dark theme, severity colors, expandable detail rows, path filtering.
- **Path filtering**: skip noisy requests (`/static/`, `/favicon.ico`) via `EXCLUDE_PATHS`.
- **Two output modes**: colored `text` for interactive development and structured `json` for logs/CI.
- **Logging integration**: emit JSON to Python's `logging` system with optional file rotation.

---

## Installation

```bash
pip install django-dev-insights
```

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
[DevInsights] Path: /users/45 | Total: 4821.37ms | DB Queries: 36 | DB Time: 4120.5ms | !! DUPLICATES: 12 !!
    [Duplicated SQLs]:
      -> (4x) SELECT "users"."id", ...
         Traceback:
         app/views.py:123 in user_detail -> User.objects.filter(...)
    [Slow Queries (> 100ms)]:
      -> [732.1ms] SELECT "reports"."id", ...
    [Templates]: 3 rendered in 45.2ms
      -> [30.1ms] templates/base.html
      -> [12.0ms] templates/users/detail.html
```

### JSON output

Structured payload per request — useful for logs, CI, or tooling:

```json
{
  "path": "/api/users/",
  "total_time_ms": 281.93,
  "db_metrics": {
    "query_count": 12,
    "total_db_time_ms": 266.0,
    "duplicate_sqls": [],
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
| **DBCollector** | `'db'` | Query count, DB time, duplicate detection (N+1), slow query detection. Optional stack traces. |
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

## Tips

- Only runs when `DEBUG = True` — the middleware depends on `connection.queries`.
- Keep `ENABLE_TRACEBACKS` disabled by default — enable only when actively debugging.
- Use `EXCLUDE_PATHS` to filter static files and health checks from the output.
- The HTML panel stores metrics in memory only — data is cleared on server restart.

---

## Contributing

Contributions are welcome. Please open an issue or PR with a clear description and tests.

---

## License

MIT — see [LICENSE](LICENSE) for details.
