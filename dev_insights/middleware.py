import time
import logging
from logging import FileHandler

from django.conf import settings

from .collectors.db import DBCollector
from .collectors.connection import ConnectionCollector
from .collectors.template import TemplateCollector
from .formatters import format_output
from .sql_trace import patch_cursor_debug_wrapper
from .template_trace import patch_template_render
from .config import (
    OUTPUT_FORMAT,
    OUTPUT_LOGGER_NAME,
    OUTPUT_LOG_FILE,
    EXCLUDE_PATHS,
)


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
            "template": TemplateCollector,
        }

        self.collectors = []
        for name in ENABLED_COLLECTORS or []:
            cls = collectors_map.get(name)
            if cls:
                try:
                    self.collectors.append(cls())
                except Exception:
                    pass

        # Apply monkeypatches when DEBUG
        try:
            from django.conf import settings as _settings

            if getattr(_settings, "DEBUG", False):
                from dev_insights.config import ENABLE_TRACEBACKS as _enable_tb

                if _enable_tb:
                    patch_cursor_debug_wrapper()
                if "template" in (ENABLED_COLLECTORS or []):
                    patch_template_render()
        except Exception:
            pass

    def __call__(self, request):
        if not settings.DEBUG:
            return self.get_response(request)

        if EXCLUDE_PATHS and any(request.path.startswith(p) for p in EXCLUDE_PATHS):
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
            collector_name = collector.__class__.__name__.replace(
                "Collector", ""
            ).lower()
            final_metrics[f"{collector_name}_metrics"] = collector.get_metrics()

        # Store metrics for the HTML panel
        from .store import record_metrics

        record_metrics(final_metrics)

        # Format complete output (text or JSON)
        output_str = format_output(final_metrics)

        # If configured to emit JSON to a logger, do that instead of plain print
        if OUTPUT_FORMAT == "json" and OUTPUT_LOGGER_NAME:
            try:
                logger = logging.getLogger(OUTPUT_LOGGER_NAME)
                if not logger.handlers and OUTPUT_LOG_FILE:
                    fh = FileHandler(OUTPUT_LOG_FILE)
                    fh.setLevel(logging.INFO)
                    fh.setFormatter(logging.Formatter("%(message)s"))
                    logger.addHandler(fh)
                    logger.setLevel(logging.INFO)
                logger.info(output_str)
            except Exception:
                print(output_str)
        else:
            print(output_str)

        return response
