from django.db import connections

from dev_insights.config import ENABLE_TRACEBACKS, TRACEBACK_DEPTH
from dev_insights.trace import capture_traceback, format_traceback


SETUP_PREFIXES = (
    'set ',
    'select version',
    'show ',
)


class ConnectionCollector:
    """Collector agnóstico de conexões.

    Coleta queries de setup executadas em cada conexão (como `SET search_path`,
    `SELECT VERSION`, etc.) e detecta se a conexão foi reaberta durante a
    requisição (mudança no objeto subjacente `connection`).
    """
    def __init__(self):
        self.stats = {}

    def start_collect(self):
        # Registra o estado inicial para cada alias de conexão
        self._start = {}
        for alias in connections:
            conn = connections[alias]
            self._start[alias] = {
                'start_query_count': len(getattr(conn, 'queries', [])),
                'start_conn_id': id(getattr(conn, 'connection', None)),
            }

    def finish_collect(self):
        total_setup = 0
        setup_queries = {}
        reopens = []

        for alias in connections:
            conn = connections[alias]
            start = self._start.get(alias, {'start_query_count': 0, 'start_conn_id': None})
            queries = getattr(conn, 'queries', [])[start['start_query_count']:]

            alias_setup = []
            for q in queries:
                sql = (q.get('sql') or '').strip()
                if not sql:
                    continue
                low = sql.lower()
                # heurística simples: queries que começam com prefixes conhecidos
                # são consideradas queries de setup.
                if low.startswith(SETUP_PREFIXES) or 'set search_path' in low:
                    item = {'sql': sql}
                    if ENABLE_TRACEBACKS:
                        frames = capture_traceback(depth=TRACEBACK_DEPTH)
                        item['traceback'] = format_traceback(frames)
                    alias_setup.append(item)

            setup_queries[alias] = alias_setup
            total_setup += len(alias_setup)

            current_conn_id = id(getattr(conn, 'connection', None))
            # se o id da conexão subjacente mudou para um objeto não-None,
            # consideramos que houve reabertura/reconexão
            if start.get('start_conn_id') != current_conn_id and current_conn_id is not None:
                reopens.append(alias)

        self.stats = {
            'total_setup_query_count': total_setup,
            'setup_queries': setup_queries,
            'connection_reopens': reopens,
        }

    def get_metrics(self):
        return self.stats
