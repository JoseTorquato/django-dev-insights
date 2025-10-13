from django.db import connection
from collections import Counter

from dev_insights.config import SLOW_QUERY_THRESHOLD_MS


class DBCollector:
    def __init__(self):
        self.stats = {}

    def start_collect(self):
        self.start_query_count = len(connection.queries)

    def finish_collect(self):
        queries = connection.queries[self.start_query_count:]
        
        self.stats['query_count'] = len(queries)
        
        total_time_ms = 0
        slow_queries = []
        sql_statements = []

        for query in queries:
            query_time_ms = float(query['time']) * 1000
            total_time_ms += query_time_ms
            sql_statements.append(query['sql'])

            # --- NOVA LÓGICA DE QUERIES LENTAS ---
            if query_time_ms > SLOW_QUERY_THRESHOLD_MS:
                slow_queries.append({
                    'sql': query['sql'],
                    'time_ms': round(query_time_ms, 2)
                })

        self.stats['total_db_time_ms'] = round(total_time_ms, 2)
        self.stats['slow_queries'] = slow_queries
        self.stats['slow_query_count'] = len(slow_queries)

        # Lógica de duplicatas permanece a mesma
        sql_counter = Counter(sql_statements)
        duplicate_queries = {sql: count for sql, count in sql_counter.items() if count > 1}
        self.stats['duplicate_query_count'] = sum(duplicate_queries.values())
        self.stats['duplicate_sqls'] = list(duplicate_queries.keys())

    def get_metrics(self):
        return self.stats
