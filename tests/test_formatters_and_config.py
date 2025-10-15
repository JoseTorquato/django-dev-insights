import os
import sys
import json
import importlib
from django.conf import settings


def setup_module(module):
    # Ensure project root is on sys.path so `dev_insights` package is importable
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    # Configure Django settings once for all tests
    if not settings.configured:
        settings.configure(DEBUG=True, DEV_INSIGHTS_CONFIG={})


def reload_package_config(new_config: dict):
    """Set DEV_INSIGHTS_CONFIG and reload dev_insights modules that read it."""
    settings.DEV_INSIGHTS_CONFIG = new_config
    # reload package modules that read settings at import time
    import dev_insights.config
    import dev_insights.formatters

    importlib.reload(dev_insights.config)
    importlib.reload(dev_insights.formatters)


def make_payload(duplicate_count=0, slow_count=0, setup_count=0):
    payload = {
        "path": "/test",
        "total_time_ms": 12.34,
        "db_metrics": {
            "query_count": 1 + duplicate_count + slow_count,
            "total_db_time_ms": 5.1,
            "duplicate_sqls": [
                {"sql": f"SELECT dup_{i}", "count": 2} for i in range(duplicate_count)
            ],
            "slow_queries": [
                {"sql": f"SELECT slow_{i}", "time_ms": 150.0 + i}
                for i in range(slow_count)
            ],
        },
        "connection_metrics": {
            "total_setup_query_count": setup_count,
            "setup_queries": {
                "default": [{"sql": f"SET x_{i}"} for i in range(setup_count)]
            },
            "connection_reopens": [],
        },
    }
    return payload


def test_config_exports():
    # Import config and verify default exports exist
    import dev_insights.config as config

    assert hasattr(config, "OUTPUT_FORMAT")
    assert hasattr(config, "DISPLAY_LIMIT")


def test_format_output_text_mode_returns_string():
    # Reload package modules with text mode config
    reload_package_config({"OUTPUT_FORMAT": "text"})
    from dev_insights.formatters import format_output

    payload = make_payload(
        duplicate_count=1, slow_count=1, setup_count=0
    )
    s = format_output(payload)
    assert isinstance(s, str)
    assert "[DevInsights]" in s


def test_format_output_json_truncation():
    reload_package_config(
        {
            "OUTPUT_FORMAT": "json",
            "JSON_PRETTY": False,
            "DISPLAY_LIMIT": 1,
        }
    )
    from dev_insights.formatters import format_output

    payload = make_payload(duplicate_count=2, slow_count=2, setup_count=2)
    s = format_output(payload)
    # Should be valid JSON
    data = json.loads(s)

    db = data.get("db_metrics", {})
    # duplicate_sqls should be truncated to 1 item
    assert isinstance(db.get("duplicate_sqls"), list)
    assert len(db.get("duplicate_sqls")) == 1
    assert db.get("duplicate_sqls_omitted", 0) == 1

    # slow_queries truncated
    assert len(db.get("slow_queries")) == 1
    assert db.get("slow_queries_omitted", 0) == 1

    # setup_queries should be truncated per-alias and report omitted
    conn = data.get("connection_metrics", {})
    assert "setup_queries" in conn
    assert conn.get("setup_queries_omitted", 0) >= 1


def test_format_output_json_pretty():
    # Pretty-print enabled with indent 4
    reload_package_config(
        {
            "OUTPUT_FORMAT": "json",
            "JSON_PRETTY": True,
            "JSON_INDENT": 4,
            "DISPLAY_LIMIT": 10,
        }
    )
    from dev_insights.formatters import format_output

    payload = make_payload(duplicate_count=0, slow_count=0, setup_count=0)
    s = format_output(payload)
    # Pretty JSON should contain newlines and indentation
    assert isinstance(s, str)
    assert "\n" in s
    # indentation may vary slightly depending on JSON dump; check for a path key
    assert (
        '"path":' in s
    )


def test_middleware_logs_json_to_file(tmp_path):
    # Prepare a logfile path
    logfile = str(tmp_path / "dev_insights_mw.log")
    # Configure middleware to emit JSON to logger and attach file
    reload_package_config(
        {
            "OUTPUT_FORMAT": "json",
            "JSON_PRETTY": True,
            "OUTPUT_LOGGER_NAME": "dev_insights_test",
            "OUTPUT_LOG_FILE": logfile,
        }
    )

    # Import middleware and build a fake request/response
    from dev_insights.middleware import DevInsightsMiddleware

    def get_response(req):
        return object()

    mw = DevInsightsMiddleware(get_response)

    # Replace collectors with fakes that return expected metrics
    class FakeCollector:
        def __init__(self, name, metrics):
            self._metrics = metrics

        def start_collect(self):
            pass

        def finish_collect(self):
            pass

        def get_metrics(self):
            return self._metrics

    db_metrics = {
        "query_count": 1,
        "total_db_time_ms": 1.0,
        "duplicate_sqls": [],
        "slow_queries": [],
    }
    conn_metrics = {
        "total_setup_query_count": 0,
        "setup_queries": {},
        "connection_reopens": [],
    }

    mw.collectors = [
        FakeCollector("db", db_metrics),
        FakeCollector("connection", conn_metrics),
    ]

    # Build a minimal request object
    class Req:
        path = "/middleware-test/"

    # Call middleware
    mw(Req())

    # Assert logfile was created and contains JSON with the path
    assert os.path.exists(logfile)
    with open(logfile, "r", encoding="utf-8") as f:
        content = f.read()
    assert "/middleware-test/" in content
