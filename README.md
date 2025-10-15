# django-dev-insights

[![PyPI version](https://badge.fury.io/py/django-dev-insights.svg)](https://badge.fury.io/py/django-dev-insights)

Lightweight, developer-focused request insights for Django — real-time, per-request diagnostics printed to your console or emitted as structured JSON.

This middleware is intended for development. It helps you quickly spot common performance issues such as excessive DB queries, duplicated queries (N+1 patterns), slow queries, and connection setup queries.

---

## Why this project

In real-world Django apps a single view can inadvertently issue dozens or hundreds of SQL queries. Finding the source of those queries is often time-consuming. `django-dev-insights` gives you an immediate, per-request snapshot so you can find and fix hot spots quickly during development.

Key outcomes reported in real cases:

- Reduced a page load from 28s → 3.8s by identifying and removing >200 duplicated queries.
- Reduced a page load from 8s → 1.8s by locating an N+1 query pattern visible only with large datasets.

---

## Features

- Per-request metrics: total time, DB time, query count.
- Duplicate SQL detection with example stack traces (optional).
- Slow query detection (configurable threshold) with optional stack traces.
- Connection collector: detects setup queries (e.g. `SET search_path`) and connection reopens.
- Two output modes: human-friendly colored `text` and structured `json` (with truncation and pretty-print options).
- Optional integration with the Python `logging` system to emit JSON to a logger or a file.

---

## Installation

Install the package from PyPI:

```bash
pip install django-dev-insights
```

Optional: install `colorama` for colored terminal output (recommended for Windows):

```bash
pip install colorama
```

---

## Quickstart

Add the middleware to your `settings.py`. For best results put it high in the stack so it can measure the full request lifecycle (usually as the first middleware):

```python
# settings.py
MIDDLEWARE = [
    'dev_insights.middleware.DevInsightsMiddleware',
    # ... other middleware
]
```

Run your development server (`python manage.py runserver`) and you will see per-request reports printed to your console (when `DEBUG = True`).

---

## Output modes

The middleware supports two output modes controllable via the `DEV_INSIGHTS_CONFIG` settings:

- `text` (default): colored, human-readable lines plus expanded sections (duplicates, slow queries, connection setup). Useful when developing interactively.
- `json`: single-line (or pretty) structured JSON payload per request. Useful for structured logs, CI, or tooling.

### Example: text output (abridged)

```
[DevInsights] Path: /users/45 | Total: 4821.37ms | DB Queries: 36 | DB Time: 4120.5ms | !! DUPLICATES: 12 !!
    [Duplicated SQLs]:
      -> (4x) SELECT ...
         Traceback:
         path/to/your/file.py:123 in some_view -> model.objects.filter(...)
    [Slow Queries (> 500ms)]:
      -> [732.1ms] SELECT ...
         Traceback:
         path/to/your/other.py:45 in slow_fn -> queryset
```

### Example: JSON output (abridged, pretty-printed)

```json
{
  "path": "/admin/login/",
  "total_time_ms": 281.93,
  "db_metrics": {
    "query_count": 2,
    "total_db_time_ms": 266.0,
    "duplicate_sqls": [],
    "slow_queries": []
  },
  "connection_metrics": {
    "total_setup_query_count": 1,
    "setup_queries": {
      "default": [{"sql": "SET search_path = 'schema','public'"}]
    }
  }
}
```

---

## Configuration

All configuration is provided via the `DEV_INSIGHTS_CONFIG` dict in `settings.py`. The most relevant options are shown below with their defaults.

```python
DEV_INSIGHTS_CONFIG = {
    'THRESHOLDS': {
        'total_time_ms': {'warn': 1000, 'crit': 3000},
        'query_count': {'warn': 20, 'crit': 50},
        'duplicate_query_count': {'warn': 5, 'crit': 10},
    },
    'SLOW_QUERY_THRESHOLD_MS': 100,     # ms
    'ENABLE_TRACEBACKS': False,         # capture stack traces for slow/duplicate/setup queries
    'TRACEBACK_DEPTH': 5,
    'ENABLED_COLLECTORS': ['db', 'connection'],
    'OUTPUT_FORMAT': 'text',            # 'text' or 'json'
    'DISPLAY_LIMIT': 100,              # max items per list (duplicates/slow/setup)
    'JSON_PRETTY': True,               # pretty-print JSON when OUTPUT_FORMAT == 'json'
    'JSON_INDENT': 2,                  # number of spaces for indent
    'OUTPUT_LOGGER_NAME': None,        # if set, JSON output is sent to this logger
    'OUTPUT_LOG_FILE': None,           # optional file attached to the logger if it has no handlers
}
```

Notes:

- `ENABLE_TRACEBACKS` is disabled by default — enable only in development because collecting stack frames increases overhead.
- `DISPLAY_LIMIT` truncates large lists; when truncated, the JSON includes an `_omitted` count indicating how many items were left out.

---

## Logging integration (recommended for structured JSON)

If you want structured JSON to be sent to your logging system (instead of printed to stdout), set `OUTPUT_LOGGER_NAME` to a logger name. If the logger has no handlers and `OUTPUT_LOG_FILE` is provided, the middleware will attach a simple `FileHandler` that writes raw JSON messages.

Recommended: configure the logger in Django's `LOGGING` settings for full control (handlers, rotation, formatters):

```python
# settings.py (LOGGING)
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
        'json_message': {
            'format': '%(message)s'
        }
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

If you rely on simple configuration (no custom Django `LOGGING`), you can provide `OUTPUT_LOG_FILE` and the middleware will attach a `FileHandler` automatically when the logger has no handlers.

---

## Collectors

- `DBCollector` — inspects `connection.queries`, computes `query_count`, `total_db_time_ms`, `slow_queries`, and `duplicate_sqls` (with counts). When `ENABLE_TRACEBACKS=True` it captures a stack trace example for duplicates and slow queries.
- `ConnectionCollector` — inspects each DB connection to detect setup queries (e.g. `SET search_path`) and whether the DB connection object was reopened during the request.

You can enable/disable collectors via `ENABLED_COLLECTORS`.

---

## Tips & Troubleshooting

- Run only with `DEBUG = True`. The middleware depends on `connection.queries` available in Django debug mode.
- If you see many `SET search_path` queries (multi-tenant setups), try enabling `ENABLE_TRACEBACKS` temporarily to locate the code path causing them.
- Keep `ENABLE_TRACEBACKS` disabled when you are not actively debugging to avoid CPU/memory overhead.

---

## Development

- Tests and static checks: add pytest/flake8 as you prefer. This project includes minimal unit coverage; contributions that add tests are welcome.
- To run small integration checks locally, you can import `dev_insights.formatters.format_output` and pass a sample payload to verify JSON/text output.

---

## Contributing

Contributions are welcome. Good first issues:

- Add unit tests for `format_output` (text and JSON modes).
- Add per-type display limits (e.g. separate limits for `duplicates` and `slow_queries`).
- Add RotatingFileHandler support configuration or make the automatic FileHandler use rotation.

Please open an issue or a PR with a clear description and tests where applicable.

---

## License

This project is licensed under the MIT License. See `LICENSE` for details.

---

If you want, I can also:

- add a short `USAGE.md` with examples of `DEV_INSIGHTS_CONFIG` for common workflows; or
- create unit tests that assert JSON pretty-print and file-logging behavior.

# `django-dev-insights`

[![PyPI version](https://badge.fury.io/py/django-dev-insights.svg)](https://badge.fury.io/py/django-dev-insights)

**Insights de performance em tempo real, direto no seu terminal.**

`django-dev-insights` é um middleware leve para Django que fornece um diagnóstico claro e imediato sobre a performance de cada requisição durante o desenvolvimento. Ele foi projetado para ser simples, não intrusivo e focado em expor os gargalos mais comuns: queries de banco de dados excessivas, duplicadas e lentas.

### O Problema que Resolvemos

Em um projeto Django real, uma única página pode, sem querer, gerar dezenas ou centenas de queries ao banco de dados, resultando em tempos de carregamento de vários segundos. `django-dev-insights` foi criado e validado em um cenário de produção complexo, onde ajudou a:

*   **Reduzir o tempo de carregamento de uma página de 28 segundos para 3.8 segundos** ao identificar e eliminar mais de 200 queries duplicadas.
*   **Otimizar uma página de 8 segundos para 1.8 segundos** ao diagnosticar um problema de N+1 que só era visível com um grande volume de dados.

Esta ferramenta te dá os dados para transformar performance de "lenta" para "rápida".

## Instalação

1.  Instale o pacote via `pip`:
    ```bash
    pip install django-dev-insights
    ```

2.  Adicione `colorama`, que é usado para a saída colorida no console:
    ```bash
    pip install colorama
    ```

## Configuração Rápida

Para começar a usar, adicione o middleware ao seu arquivo `settings.py`. É crucial que ele seja o **primeiro** na sua lista de `MIDDLEWARE` para garantir que ele meça o ciclo de vida completo da requisição.
# `django-dev-insights`

[![PyPI version](https://badge.fury.io/py/django-dev-insights.svg)](https://badge.fury.io/py/django-dev-insights)

Insights de performance em tempo real, direto no seu terminal (focado para desenvolvimento).

`django-dev-insights`  e9 um middleware leve para Django que fornece diagn f3sticos por requisi e7 e3o: tempo total, queries ao DB, queries duplicadas (N+1), queries lentas e mais. Foi projetado para ser simples, n e3o intrusivo e configur e1vel.

## Principais features recentes

- v0.4.0: ConnectionCollector — detecta queries de setup (ex.: `SET search_path`, `SELECT VERSION`) por conex e3o e aponta reaberturas de conex e3o.
- v0.5.0: Tracebacks — captura stack traces para queries lentas/duplicadas/setup (opcional, ativado via configura e7 e3o).

Essas features juntam informa e7 f5es que permitem localizar n e3o apenas "o que" est e1 lento, mas tamb e9m "de onde" vem a query no c f3digo.

## Instala e7 e3o

1. Instale via pip:

```bash
pip install django-dev-insights
```

2. (Opcional) `colorama`  e9 usado para sa edda colorida:

```bash
pip install colorama
```

## Configura e7 e3o r e1pida

Adicione o middleware em `settings.py`. Para medir o ciclo completo da requisi e7 e3o, posicione-o antes de middlewares que voc ea quer observar. Se usa `django-tenants`, garanta que o Tenant middleware venha antes (veja abaixo).

```python
# settings.py
MIDDLEWARE = [
    'dev_insights.middleware.DevInsightsMiddleware',
    # ... outros middlewares
]
```

Rode o servidor de desenvolvimento (`python manage.py runserver`) e voc ea ver e1 relat f3rios por requisi e7 e3o no terminal.

## Como ler a sa edda

Exemplo de sa edda (resumida):

```
[DevInsights] Path: /usuarios/45 | Tempo Total: 4821.37ms | DB Queries: 36 | DB Tempo: 4120.5ms | !! DUPLICATAS: 12 !!
    [Duplicated SQLs]:
      -> (4x) SELECT ...
         Traceback:
         path/to/your/file.py:123 in some_view -> model.objects.filter(...)
    [Slow Queries (> 500ms)]:
      -> [732.1ms] SELECT ...
         Traceback:
         path/to/your/other.py:45 in slow_fn -> queryset
    [Connection Setup Queries]:
      -> default: 3 setup queries
         - SET search_path = 'clientschema','public'
           Traceback: path/to/middleware.py:30 in process_request -> set_tenant(...)
```

As linhas principais s e3o coloridas (verde/amarelo/vermelho) conforme limites configur e1veis.

## Configura e7 f5es dispon edveis

Adicione `DEV_INSIGHTS_CONFIG` em `settings.py` para personalizar comportamentos. Exemplo com as op e7 f5es mais relevantes:

```python
DEV_INSIGHTS_CONFIG = {
    'THRESHOLDS': {
        'total_time_ms': {'warn': 1000, 'crit': 3000},
        'query_count': {'warn': 20, 'crit': 50},
        'duplicate_query_count': {'warn': 5, 'crit': 10},
    },
    'SLOW_QUERY_THRESHOLD_MS': 100,   # ms
    'ENABLE_TRACEBACKS': False,       # ativar captura de stack traces (DEBUG apenas)
    'TRACEBACK_DEPTH': 5,             # profundidade do traceback
    'ENABLED_COLLECTORS': ['db', 'connection'],  # quais coletores rodar
}
```

Notas importantes:
- `ENABLE_TRACEBACKS` deve ficar `False` por padr e3o; habilite somente em desenvolvimento porque captura/format de stack aumenta o overhead.
- `ENABLED_COLLECTORS` permite desabilitar o `ConnectionCollector` se voc ea n e3o quiser relatar queries de setup.

## Integra e7 e3o com `django-tenants` / multi-tenant

Se seu projeto usa `django-tenants` (ou outra solu e7 e3o por schemas), voc ea provavelmente ver e1 SQLs como `SET search_path ...` no log. Boas pr e1ticas:

- Coloque o tenant middleware antes de qualquer middleware que acesse o DB (sessions, auth). Exemplo:

```python
MIDDLEWARE = [
    'django_tenants.middleware.main.TenantMainMiddleware',
    'dev_insights.middleware.DevInsightsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    # ...
]
```

- Se voc ea ainda ver `SET search_path` repetido, habilite `ENABLE_TRACEBACKS` temporariamente para localizar o ponto do c f3digo que est e1 chamando a troca de schema.

## Diagn f3stico R e1pido

- Habilite `ENABLE_TRACEBACKS` e `TRACEBACK_DEPTH` alto, reproduza a requisi e7 e3o e observe o traceback que aponta para o arquivo/linha que disparou a SQL.
- Alternativamente, use um patch tempor e1rio que loga stack imediatamente ao detectar SQLs contendo `search_path` (recomendado para investiga e7 f5es locais curtas).

## Boas pr e1ticas

- Use `DevInsights` apenas com `DEBUG = True` (padr e3o) — a coleta de queries depende de `connection.queries` do Django.
- Desabilite tracebacks e coletores quando n e3o estiver depurando para reduzir overhead.

## Contribui e7 f5es

Contribui e7 f5es s e3o bem-vindas. Abra issues para bugs/feature requests ou pull requests com pequenas melhorias (tests, docs, coletores adicionais).

