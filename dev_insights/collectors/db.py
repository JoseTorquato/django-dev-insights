from django.db import connection

from dev_insights.analysis import summarize
from dev_insights.config import SLOW_QUERY_THRESHOLD_MS
from dev_insights.signature import sql_signature


class DBCollector:
    """Per-request DB metrics, read from ``connection.queries`` (DEBUG=True).

    Tracebacks and origins are the ones attached to each query *when it was
    executed* (by ``sql_trace``, when ``ENABLE_TRACEBACKS`` is on). They are no
    longer captured here, at the end of the request, where the stack only
    showed the middleware.
    """

    def __init__(self):
        self.stats = {}

    def start_collect(self):
        self.start_query_count = len(connection.queries)

    def finish_collect(self):
        entries = []
        for query in connection.queries[self.start_query_count :]:
            sql = query["sql"]
            entry = {
                "sql": sql,
                "time_ms": float(query["time"]) * 1000,
                "signature": sql_signature(sql),
            }
            if query.get("traceback"):
                entry["traceback"] = query["traceback"]
            if query.get("origin"):
                entry["origin"] = query["origin"]
            entries.append(entry)
        self.stats = summarize(entries, SLOW_QUERY_THRESHOLD_MS)

    def get_metrics(self):
        return self.stats
