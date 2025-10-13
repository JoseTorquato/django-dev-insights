import time
from django.conf import settings
from .collectors.db import SLOW_QUERY_THRESHOLD_MS, DBCollector
from .formatters import format_output  # 1. IMPORTA a nova função de formatação
from colorama import Fore, Style       # 2. IMPORTA Fore e Style para colorir os detalhes

class DevInsightsMiddleware:
    """
    Middleware que orquestra a coleta de métricas de performance.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        self.collectors = [DBCollector()]

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

        # Imprime detalhes das duplicatas
        if db_metrics.get('duplicate_query_count', 0) > 0:
            print(f"{Fore.YELLOW}    [Duplicated SQLs]:{Style.RESET_ALL}")
            for sql in db_metrics.get('duplicate_sqls', []):
                print(f"{Fore.YELLOW}      -> {sql}{Style.RESET_ALL}")

        # --- NOVA FEATURE: IMPRIME QUERIES LENTAS ---
        if db_metrics.get('slow_query_count', 0) > 0:
            print(f"{Fore.RED}    [Slow Queries (> {SLOW_QUERY_THRESHOLD_MS}ms)]:{Style.RESET_ALL}")
            for slow_query in db_metrics.get('slow_queries', []):
                print(f"{Fore.RED}      -> [{slow_query['time_ms']}ms] {slow_query['sql']}{Style.RESET_ALL}")

        return response
