# Usage examples — django-dev-insights

This file contains ready-to-copy `DEV_INSIGHTS_CONFIG` snippets for common development workflows.

Paste the selected example into your `settings.py` (or merge with your existing `DEV_INSIGHTS_CONFIG`).

## 1) Default (text, human-friendly)

Best for interactive development. Shows colored lines and expanded detailed sections.

```python
DEV_INSIGHTS_CONFIG = {
    'OUTPUT_FORMAT': 'text',
    'DISPLAY_LIMIT': 100,
    'ENABLE_TRACEBACKS': False,
}
```

## 2) JSON to stdout (pretty-printed)

Good for CI, logs processing, or when you want structured output on the terminal.

```python
DEV_INSIGHTS_CONFIG = {
    'OUTPUT_FORMAT': 'json',
    'JSON_PRETTY': True,
    'JSON_INDENT': 2,
    'DISPLAY_LIMIT': 50,
}
```

## 3) JSON -> logger -> file (recommended for production-like logs)

Configure Django `LOGGING` and tell `dev-insights` to use the logger name. This example sets up a rotating file handler in `LOGGING` and points `dev-insights` at the `dev_insights` logger.

```python
# settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'dev_insights_file': {
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': r'C:\logs\dev_insights.json',
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

If you don't want to edit `LOGGING`, you can use the simpler pattern below: the middleware will attach a basic `FileHandler` if the named logger has no handlers.

```python
DEV_INSIGHTS_CONFIG = {
    'OUTPUT_FORMAT': 'json',
    'OUTPUT_LOGGER_NAME': 'dev_insights',
    'OUTPUT_LOG_FILE': r'C:\logs\dev_insights.json',
}
```

## 4) Enable tracebacks (temporary, for debugging)

Use this when you need to know where a slow or duplicated SQL is coming from. Keep it off by default because it adds overhead.

```python
DEV_INSIGHTS_CONFIG = {
    'ENABLE_TRACEBACKS': True,
    'TRACEBACK_DEPTH': 6,
}
```

## 5) Tuning display limits

Reduce the amount of data shown per request (helpful for very noisy endpoints):

```python
DEV_INSIGHTS_CONFIG = {
    'DISPLAY_LIMIT': 10,  # only show first 10 items in lists (duplicates/slow/setup)
}
```

## 6) Disable the ConnectionCollector

If you don't want setup/reopen detection, disable the connection collector:

```python
DEV_INSIGHTS_CONFIG = {
    'ENABLED_COLLECTORS': ['db'],
}
```

## Quick local test (Python snippet)

Useful to verify JSON/text output without running the full Django server. Run inside your project virtualenv.

```python
from django.conf import settings
if not settings.configured:
    settings.configure(DEBUG=True, DEV_INSIGHTS_CONFIG={'OUTPUT_FORMAT': 'json', 'JSON_PRETTY': True})

from dev_insights.formatters import format_output

payload = {
    'path': '/test',
    'total_time_ms': 10.2,
    'db_metrics': {'query_count': 1, 'total_db_time_ms': 2.1, 'duplicate_sqls': [], 'slow_queries': []},
    'connection_metrics': {'total_setup_query_count': 0, 'setup_queries': {}, 'connection_reopens': []},
}

print(format_output(payload))
```

---

If you'd like, I can add ready-to-run examples for `django-tenants` or an automated script that appends a `dev_insights` logger to your existing `LOGGING` dict.
