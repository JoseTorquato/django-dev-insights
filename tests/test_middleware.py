import os
import sys
import importlib
from unittest.mock import patch
from django.conf import settings


def setup_module(module):
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    if not settings.configured:
        settings.configure(DEBUG=True, DEV_INSIGHTS_CONFIG={})


def reload_config(new_config=None):
    settings.DEV_INSIGHTS_CONFIG = new_config or {}
    import dev_insights.config
    import dev_insights.formatters
    import dev_insights.middleware

    importlib.reload(dev_insights.config)
    importlib.reload(dev_insights.formatters)
    importlib.reload(dev_insights.middleware)


# Dynamically create fake collectors that produce the right metric key names
def _make_fake_collector(collector_cls_name, metrics):
    """Create a fake collector whose __class__.__name__ matches the real one."""

    class _Fake:
        def start_collect(self):
            pass

        def finish_collect(self):
            pass

        def get_metrics(self):
            return metrics

    _Fake.__name__ = collector_cls_name
    _Fake.__qualname__ = collector_cls_name
    return _Fake()


class Req:
    def __init__(self, path="/test/"):
        self.path = path


class TestExcludePaths:
    def test_excluded_path_skips_processing(self):
        reload_config({"EXCLUDE_PATHS": ["/static/", "/health/"]})
        from dev_insights.middleware import DevInsightsMiddleware

        calls = []

        def get_response(req):
            calls.append(req.path)
            return "ok"

        mw = DevInsightsMiddleware(get_response)
        mw.collectors = []

        result = mw(Req("/static/css/style.css"))
        assert result == "ok"
        # Should have been called but no output processing
        assert len(calls) == 1

    def test_non_excluded_path_is_processed(self, capsys):
        reload_config({"EXCLUDE_PATHS": ["/static/"], "OUTPUT_FORMAT": "text"})
        from dev_insights.middleware import DevInsightsMiddleware

        def get_response(req):
            return "ok"

        mw = DevInsightsMiddleware(get_response)
        mw.collectors = [
            _make_fake_collector(
                "DBCollector",
                {
                    "query_count": 1,
                    "total_db_time_ms": 1.0,
                    "duplicate_sqls": [],
                    "duplicate_query_count": 0,
                    "slow_queries": [],
                    "slow_query_count": 0,
                },
            ),
        ]

        mw(Req("/api/users/"))
        captured = capsys.readouterr()
        assert "[DevInsights]" in captured.out

    def test_empty_exclude_paths_processes_all(self, capsys):
        reload_config({"EXCLUDE_PATHS": [], "OUTPUT_FORMAT": "text"})
        from dev_insights.middleware import DevInsightsMiddleware

        def get_response(req):
            return "ok"

        mw = DevInsightsMiddleware(get_response)
        mw.collectors = []
        mw(Req("/anything/"))
        captured = capsys.readouterr()
        assert "[DevInsights]" in captured.out


class TestDebugModeGuard:
    def test_skips_when_debug_false(self):
        reload_config()
        from dev_insights.middleware import DevInsightsMiddleware

        def get_response(req):
            return "response"

        mw = DevInsightsMiddleware(get_response)

        with patch.object(settings, "DEBUG", False):
            result = mw(Req("/api/test/"))
        assert result == "response"


class TestTextOutputComplete:
    """Verify that text output includes detail sections after the refactor."""

    def test_text_output_includes_duplicates(self, capsys):
        reload_config({"OUTPUT_FORMAT": "text"})
        from dev_insights.middleware import DevInsightsMiddleware

        def get_response(req):
            return "ok"

        mw = DevInsightsMiddleware(get_response)
        mw.collectors = [
            _make_fake_collector(
                "DBCollector",
                {
                    "query_count": 5,
                    "total_db_time_ms": 10.0,
                    "duplicate_sqls": [{"sql": "SELECT * FROM t", "count": 3}],
                    "duplicate_query_count": 3,
                    "slow_queries": [],
                    "slow_query_count": 0,
                },
            ),
        ]

        mw(Req("/api/"))
        captured = capsys.readouterr()
        assert "Duplicated SQLs" in captured.out
        assert "SELECT * FROM t" in captured.out

    def test_text_output_includes_slow_queries(self, capsys):
        reload_config({"OUTPUT_FORMAT": "text", "SLOW_QUERY_THRESHOLD_MS": 50})
        from dev_insights.middleware import DevInsightsMiddleware

        def get_response(req):
            return "ok"

        mw = DevInsightsMiddleware(get_response)
        mw.collectors = [
            _make_fake_collector(
                "DBCollector",
                {
                    "query_count": 1,
                    "total_db_time_ms": 200.0,
                    "duplicate_sqls": [],
                    "duplicate_query_count": 0,
                    "slow_queries": [{"sql": "SELECT heavy", "time_ms": 200.0}],
                    "slow_query_count": 1,
                },
            ),
        ]

        mw(Req("/api/"))
        captured = capsys.readouterr()
        assert "Slow Queries" in captured.out
        assert "SELECT heavy" in captured.out
