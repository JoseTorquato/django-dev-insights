from django.db import connection
from collections import Counter

from dev_insights.config import (
    SLOW_QUERY_THRESHOLD_MS,
    ENABLE_TRACEBACKS,
    TRACEBACK_DEPTH,
)
from dev_insights.trace import capture_traceback, format_traceback


class DBCollector:
    def __init__(self):
        self.stats = {}

    def start_collect(self):
        self.start_query_count = len(connection.queries)

    def finish_collect(self):
        queries = connection.queries[self.start_query_count :]

        self.stats["query_count"] = len(queries)

        total_time_ms = 0
        slow_queries = []
        sql_statements = []

        for query in queries:
            query_time_ms = float(query["time"]) * 1000
            total_time_ms += query_time_ms
            sql_statements.append(query["sql"])

            # --- New logic for slow queries ---
            if query_time_ms > SLOW_QUERY_THRESHOLD_MS:
                slow_item = {"sql": query["sql"], "time_ms": round(query_time_ms, 2)}
                if ENABLE_TRACEBACKS:
                    frames = capture_traceback(depth=TRACEBACK_DEPTH)
                    slow_item["traceback"] = format_traceback(frames)
                slow_queries.append(slow_item)

        self.stats["total_db_time_ms"] = round(total_time_ms, 2)
        self.stats["slow_queries"] = slow_queries
        self.stats["slow_query_count"] = len(slow_queries)

        # Duplicate detection logic remains the same
        sql_counter = Counter(sql_statements)
        duplicate_queries = {
            sql: count for sql, count in sql_counter.items() if count > 1
        }
        self.stats["duplicate_query_count"] = sum(duplicate_queries.values())
        # For each duplicated SQL we attempt to capture an example traceback
        duplicate_list = []
        seen_example = set()
        if duplicate_queries:
            for query in queries:
                sql = query.get("sql")
                if sql in duplicate_queries and sql not in seen_example:
                    item = {"sql": sql, "count": duplicate_queries[sql]}
                    if ENABLE_TRACEBACKS:
                        frames = capture_traceback(depth=TRACEBACK_DEPTH)
                        item["traceback"] = format_traceback(frames)
                    duplicate_list.append(item)
                    seen_example.add(sql)
        self.stats["duplicate_sqls"] = duplicate_list

    def get_metrics(self):
        return self.stats
