"""Record queries without depending on ``DEBUG``.

Django only fills ``connection.queries`` when ``DEBUG=True``, and test runners
(Django's own and pytest-django) force ``DEBUG=False``. ``QueryRecorder`` uses
``connection.execute_wrapper`` instead, which runs for every query on every
connection of the current thread, whatever the value of ``DEBUG``.

    from dev_insights.recorder import QueryRecorder

    with QueryRecorder() as rec:
        client.get("/books/")
    rec.metrics()["similar_query_count"]

The origin of each query (the innermost frame of your project, skipping Django
and this library) is captured at execution time, only on the first occurrence
of each signature: an N+1 of 500 queries walks the stack once.

The middleware does not use this class: in development it keeps reading
``connection.queries``, exactly as before.
"""

import time
from contextlib import ExitStack

from django.db import connections

from .analysis import summarize
from .signature import sql_signature
from .trace import capture_origin


def _display_sql(context, sql, params):
    """SQL with parameters interpolated, as ``connection.queries`` shows it."""
    try:
        conn = context["connection"]
        cursor = context["cursor"]
        return conn.ops.last_executed_query(cursor, sql, params)
    except Exception:
        return sql if params is None else f"{sql} -- params={params!r}"


class QueryRecorder:
    def __init__(self, using=None, capture_origins=True):
        self.using = using
        self.capture_origins = capture_origins
        self.entries = []
        self._seen_signatures = set()
        self._stack = None

    def _aliases(self):
        if self.using is not None:
            return [self.using] if isinstance(self.using, str) else list(self.using)
        return list(connections)

    def __enter__(self):
        self._stack = ExitStack()
        for alias in self._aliases():
            self._stack.enter_context(connections[alias].execute_wrapper(self._wrap))
        return self

    def __exit__(self, *exc):
        stack, self._stack = self._stack, None
        return stack.__exit__(*exc)

    def _wrap(self, execute, sql, params, many, context):
        start = time.perf_counter()
        try:
            return execute(sql, params, many, context)
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            self._record(sql, params, many, context, elapsed_ms)

    def _record(self, sql, params, many, context, elapsed_ms):
        signature = sql_signature(sql)
        entry = {
            "sql": sql if many else _display_sql(context, sql, params),
            "time_ms": elapsed_ms,
            "signature": signature,
            "alias": getattr(context.get("connection"), "alias", None),
        }
        if self.capture_origins and signature not in self._seen_signatures:
            self._seen_signatures.add(signature)
            entry["origin"] = capture_origin()
        self.entries.append(entry)

    def mark(self):
        """Position to slice the entries recorded from now on."""
        return len(self.entries)

    def metrics(self, start=0, end=None, slow_threshold_ms=None):
        if slow_threshold_ms is None:
            from .config import SLOW_QUERY_THRESHOLD_MS

            slow_threshold_ms = SLOW_QUERY_THRESHOLD_MS
        return summarize(self.entries[start:end], slow_threshold_ms)
