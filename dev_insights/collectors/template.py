import threading

_request_data = threading.local()


def get_template_log():
    """Return the list of template renders captured for the current request."""
    return getattr(_request_data, "template_log", [])


def clear_template_log():
    _request_data.template_log = []


def _record_render(name, render_time_ms):
    if not hasattr(_request_data, "template_log"):
        _request_data.template_log = []
    _request_data.template_log.append(
        {"name": name, "time_ms": round(render_time_ms, 2)}
    )


class TemplateCollector:
    """Collector that measures template rendering times per request."""

    def __init__(self):
        self.stats = {}

    def start_collect(self):
        clear_template_log()

    def finish_collect(self):
        log = get_template_log()
        total_time = sum(entry["time_ms"] for entry in log)
        self.stats = {
            "template_count": len(log),
            "total_render_time_ms": round(total_time, 2),
            "templates": list(log),
        }

    def get_metrics(self):
        return self.stats
