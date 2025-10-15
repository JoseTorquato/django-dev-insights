import time
from django.conf import settings
from .collectors.db import SLOW_QUERY_THRESHOLD_MS, DBCollector
from .collectors.connection import ConnectionCollector
from .formatters import format_output  # 1. IMPORTA a nova função de formatação
from .sql_trace import patch_cursor_debug_wrapper
from colorama import Fore, Style       # 2. IMPORTA Fore e Style para colorir os detalhes

class DevInsightsMiddleware:
    """
    Middleware que orquestra a coleta de métricas de performance.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        # Instancia os coletores configurados pelo usuário
        from dev_insights.config import ENABLED_COLLECTORS

        collectors_map = {
            'db': DBCollector,
            'connection': ConnectionCollector,
        }

        self.collectors = []
        for name in (ENABLED_COLLECTORS or []):
            cls = collectors_map.get(name)
            if cls:
                try:
                    self.collectors.append(cls())
                except Exception:
                    # falha ao instanciar um collector não deve quebrar o app
                    pass

        # Aplicamos o monkeypatch que injeta tracebacks nas entradas de
        # connection.queries no momento da execução do SQL. Só fazemos isso
        # se o DEBUG estiver ligado e o usuário habilitou ENABLE_TRACEBACKS.
        try:
            from django.conf import settings as _settings
            if getattr(_settings, 'DEBUG', False):
                from dev_insights.config import ENABLE_TRACEBACKS as _enable_tb
                if _enable_tb:
                    patch_cursor_debug_wrapper()
        except Exception:
            # Segurança: se algo falhar não queremos quebrar a aplicação.
            pass

    def __call__(self, request):
        if not settings.DEBUG:
            return self.get_response(request)

        request_start_time = time.time()

        for collector in self.collectors:
            collector.start_collect()

        response = self.get_response(request)

        for collector in self.collectors:
            collector.finish_collect()

        total_request_time = (time.time() - request_start_time) * 1000

        # --- Agregação de Métricas (Permanece igual) ---
        final_metrics = {
            "path": request.path,
            "total_time_ms": round(total_request_time, 2),
        }
        for collector in self.collectors:
            collector_name = collector.__class__.__name__.replace("Collector", "").lower()
            # Nós ainda pegamos todas as métricas, incluindo os detalhes
            final_metrics[f"{collector_name}_metrics"] = collector.get_metrics()

        # --- 3. LÓGICA DE FORMATAÇÃO E PRINT DELEGADA ---
        # A função format_output agora cuida de toda a formatação e cores da linha principal
        output_str = format_output(final_metrics) # A função format_output também precisará ser atualizada
        print(output_str)

        db_metrics = final_metrics.get('db_metrics', {})
        conn_metrics = final_metrics.get('connection_metrics', {})

        # Imprime detalhes das duplicatas
        if db_metrics.get('duplicate_query_count', 0) > 0:
            print(f"{Fore.YELLOW}    [Duplicated SQLs]:{Style.RESET_ALL}")
            for item in db_metrics.get('duplicate_sqls', []):
                # item pode ser string (versões antigas) ou dict com sql/count/traceback
                if isinstance(item, dict):
                    sql = item.get('sql')
                    count = item.get('count')
                    print(f"{Fore.YELLOW}      -> ({count}x) {sql}{Style.RESET_ALL}")
                    tb = item.get('traceback')
                    if tb:
                        print(f"{Fore.YELLOW}         Traceback:\n{tb}{Style.RESET_ALL}")
                else:
                    print(f"{Fore.YELLOW}      -> {item}{Style.RESET_ALL}")

        # --- NOVA FEATURE: IMPRIME QUERIES LENTAS ---
        if db_metrics.get('slow_query_count', 0) > 0:
            print(f"{Fore.RED}    [Slow Queries (> {SLOW_QUERY_THRESHOLD_MS}ms)]:{Style.RESET_ALL}")
            for slow_query in db_metrics.get('slow_queries', []):
                sql = slow_query.get('sql')
                time_ms = slow_query.get('time_ms')
                print(f"{Fore.RED}      -> [{time_ms}ms] {sql}{Style.RESET_ALL}")
                tb = slow_query.get('traceback')
                if tb:
                    print(f"{Fore.RED}         Traceback:\n{tb}{Style.RESET_ALL}")

        # Imprime métricas do ConnectionCollector (queries de setup e reopens)
        if conn_metrics:
            setup_count = conn_metrics.get('total_setup_query_count', 0)
            if setup_count > 0:
                print(f"{Fore.MAGENTA}    [Connection Setup Queries]:{Style.RESET_ALL}")
                for alias, queries in conn_metrics.get('setup_queries', {}).items():
                    if queries:
                        print(f"{Fore.MAGENTA}      -> {alias}: {len(queries)} setup queries{Style.RESET_ALL}")
                        for q in queries:
                            # q pode ser string (antigo) ou dict com sql/traceback
                            if isinstance(q, dict):
                                print(f"{Fore.MAGENTA}         - {q.get('sql')}{Style.RESET_ALL}")
                                tb = q.get('traceback')
                                if tb:
                                    print(f"{Fore.MAGENTA}            Traceback:\n{tb}{Style.RESET_ALL}")
                            else:
                                print(f"{Fore.MAGENTA}         - {q}{Style.RESET_ALL}")

            reopens = conn_metrics.get('connection_reopens', [])
            if reopens:
                print(f"{Fore.MAGENTA}    [Connection Reopens Detected]: {', '.join(reopens)}{Style.RESET_ALL}")

        return response
