import time
from django.conf import settings
from .collectors.db import SLOW_QUERY_THRESHOLD_MS, DBCollector
from .collectors.connection import ConnectionCollector
from .formatters import format_output
from .sql_trace import patch_cursor_debug_wrapper
from colorama import Fore, Style
from .config import OUTPUT_FORMAT
from .config import OUTPUT_LOGGER_NAME, OUTPUT_LOG_FILE
import logging
from logging import FileHandler


class DevInsightsMiddleware:
    """
    Middleware that orchestrates collection of performance metrics.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        from dev_insights.config import ENABLED_COLLECTORS

        collectors_map = {
            "db": DBCollector,
            "connection": ConnectionCollector,
        }

        self.collectors = []
        for name in ENABLED_COLLECTORS or []:
            cls = collectors_map.get(name)
            if cls:
                try:
                    self.collectors.append(cls())
                except Exception:
                    # don't let collector instantiation break the app
                    pass

        # Apply traceback monkeypatch when DEBUG and enabled by config
        try:
            from django.conf import settings as _settings

            if getattr(_settings, "DEBUG", False):
                from dev_insights.config import ENABLE_TRACEBACKS as _enable_tb

                if _enable_tb:
                    patch_cursor_debug_wrapper()
        except Exception:
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

        # Aggregate metrics
        final_metrics = {
            "path": request.path,
            "total_time_ms": round(total_request_time, 2),
        }
        for collector in self.collectors:
            collector_name = (
                collector.__class__.__name__.replace("Collector", "").lower()
            )
            final_metrics[f"{collector_name}_metrics"] = collector.get_metrics()

        # Format/output
        output_str = format_output(final_metrics)

        # If configured to emit JSON to a logger, do that instead of plain print
        if OUTPUT_FORMAT == "json" and OUTPUT_LOGGER_NAME:
            try:
                logger = logging.getLogger(OUTPUT_LOGGER_NAME)
                # If logger has no handlers and a file is configured, attach one
                if not logger.handlers and OUTPUT_LOG_FILE:
                    fh = FileHandler(OUTPUT_LOG_FILE)
                    fh.setLevel(logging.INFO)
                    fh.setFormatter(logging.Formatter("%(message)s"))
                    logger.addHandler(fh)
                    logger.setLevel(logging.INFO)
                logger.info(output_str)
            except Exception:
                # on any logging failure, fall back to printing
                print(output_str)
        else:
            print(output_str)

        db_metrics = final_metrics.get("db_metrics", {})
        conn_metrics = final_metrics.get("connection_metrics", {})

        # Duplicate details (text only)
        if OUTPUT_FORMAT == "text" and db_metrics.get("duplicate_query_count", 0) > 0:
            print(f"{Fore.YELLOW}    [Duplicated SQLs]:{Style.RESET_ALL}")
            for item in db_metrics.get("duplicate_sqls", []):
                if isinstance(item, dict):
                    sql = item.get("sql")
                    count = item.get("count")
                    print(
                        f"{Fore.YELLOW}      -> ({count}x) {sql}"
                        f"{Style.RESET_ALL}"
                    )
                    tb = item.get("traceback")
                    if tb:
                        print(
                            f"{Fore.YELLOW}         Traceback:\n{tb}"
                            f"{Style.RESET_ALL}"
                        )
                else:
                    print(f"{Fore.YELLOW}      -> {item}{Style.RESET_ALL}")

        # Slow queries (text only)
        if OUTPUT_FORMAT == "text" and db_metrics.get("slow_query_count", 0) > 0:
            msg = "[Slow Queries (> {}ms)]:".format(SLOW_QUERY_THRESHOLD_MS)
            print(f"{Fore.RED}    {msg}{Style.RESET_ALL}")
            for slow_query in db_metrics.get("slow_queries", []):
                sql = slow_query.get("sql")
                time_ms = slow_query.get("time_ms")
                print(f"{Fore.RED}      -> [{time_ms}ms] {sql}{Style.RESET_ALL}")
                tb = slow_query.get("traceback")
                if tb:
                    print(f"{Fore.RED}         Traceback:\n{tb}{Style.RESET_ALL}")

        # Connection metrics
        if conn_metrics:
            setup_count = conn_metrics.get("total_setup_query_count", 0)
            if setup_count > 0 and OUTPUT_FORMAT == "text":
                print(f"{Fore.MAGENTA}    [Connection Setup Queries]:{Style.RESET_ALL}")
                for alias, queries in conn_metrics.get("setup_queries", {}).items():
                    if queries:
                        msg = f"{alias}: {len(queries)} setup queries"
                        print(f"{Fore.MAGENTA}      -> {msg}{Style.RESET_ALL}")
                        for q in queries:
                            if isinstance(q, dict):
                                sql_msg = q.get("sql")
                                print(
                                    f"{Fore.MAGENTA}       - {sql_msg}{Style.RESET_ALL}"
                                )
                                tb = q.get("traceback")
                                if tb:
                                    tb_msg = f"Traceback:\n{tb}"
                                    print(
                                        f"{Fore.MAGENTA}      {tb_msg}{Style.RESET_ALL}"
                                    )
                            else:
                                print(f"{Fore.MAGENTA}         - {q}{Style.RESET_ALL}")

            reopens = conn_metrics.get("connection_reopens", [])
            if reopens:
                print(
                    f"{Fore.MAGENTA}    [Connection Reopens Detected]: "
                    f"{', '.join(reopens)}{Style.RESET_ALL}"
                )

        return response
