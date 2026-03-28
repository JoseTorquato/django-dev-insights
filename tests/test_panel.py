import os
import sys
import importlib
from django.conf import settings


def setup_module(module):
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    if not settings.configured:
        settings.configure(
            DEBUG=True,
            DEV_INSIGHTS_CONFIG={},
            ROOT_URLCONF="dev_insights.urls",
        )


def reload_config(new_config=None):
    settings.DEV_INSIGHTS_CONFIG = new_config or {}
    import dev_insights.config
    import dev_insights.store

    importlib.reload(dev_insights.config)
    importlib.reload(dev_insights.store)


class TestStore:
    def test_record_and_get_history(self):
        reload_config()
        from dev_insights.store import record_metrics, get_history, clear_history

        clear_history()
        record_metrics({"path": "/a/", "total_time_ms": 10})
        record_metrics({"path": "/b/", "total_time_ms": 20})

        history = get_history()
        assert len(history) == 2
        # Newest first
        assert history[0]["path"] == "/b/"
        assert history[1]["path"] == "/a/"

    def test_history_respects_max_size(self):
        reload_config({"PANEL_HISTORY_SIZE": 3})
        from dev_insights.store import record_metrics, get_history, clear_history

        clear_history()
        for i in range(5):
            record_metrics({"path": f"/{i}/", "total_time_ms": i})

        history = get_history()
        assert len(history) == 3
        # Should keep only the last 3
        paths = [h["path"] for h in history]
        assert "/4/" in paths
        assert "/3/" in paths
        assert "/2/" in paths

    def test_clear_history(self):
        reload_config()
        from dev_insights.store import record_metrics, get_history, clear_history

        record_metrics({"path": "/x/", "total_time_ms": 1})
        clear_history()
        assert get_history() == []


class TestPanelView:
    def test_returns_html_in_debug_mode(self):
        reload_config()
        from dev_insights.store import record_metrics, clear_history
        from dev_insights.views import panel_view

        clear_history()
        record_metrics(
            {
                "path": "/api/test/",
                "total_time_ms": 42.0,
                "db_metrics": {
                    "query_count": 3,
                    "total_db_time_ms": 10.0,
                    "duplicate_query_count": 0,
                    "duplicate_sqls": [],
                    "slow_query_count": 0,
                    "slow_queries": [],
                },
                "connection_metrics": {
                    "total_setup_query_count": 0,
                    "setup_queries": {},
                    "connection_reopens": [],
                },
            }
        )

        class FakeRequest:
            pass

        response = panel_view(FakeRequest())
        content = response.content.decode()
        assert response.status_code == 200
        assert "DevInsights Panel" in content
        assert "/api/test/" in content
        assert "42.0ms" in content

    def test_forbidden_when_debug_false(self):
        reload_config()
        from dev_insights.views import panel_view
        from unittest.mock import patch as mock_patch

        class FakeRequest:
            pass

        with mock_patch.object(settings, "DEBUG", False):
            response = panel_view(FakeRequest())
        assert response.status_code == 403

    def test_shows_template_metrics(self):
        reload_config()
        from dev_insights.store import record_metrics, clear_history
        from dev_insights.views import panel_view

        clear_history()
        record_metrics(
            {
                "path": "/page/",
                "total_time_ms": 100.0,
                "db_metrics": {},
                "connection_metrics": {},
                "template_metrics": {
                    "template_count": 2,
                    "total_render_time_ms": 15.0,
                    "templates": [
                        {"name": "base.html", "time_ms": 10.0},
                        {"name": "home.html", "time_ms": 5.0},
                    ],
                },
            }
        )

        class FakeRequest:
            pass

        response = panel_view(FakeRequest())
        content = response.content.decode()
        assert "base.html" in content
        assert "home.html" in content

    def test_escapes_html_in_sql(self):
        reload_config()
        from dev_insights.store import record_metrics, clear_history
        from dev_insights.views import panel_view

        clear_history()
        record_metrics(
            {
                "path": "/xss/",
                "total_time_ms": 10.0,
                "db_metrics": {
                    "query_count": 1,
                    "total_db_time_ms": 1.0,
                    "duplicate_query_count": 1,
                    "duplicate_sqls": [
                        {"sql": "<script>alert('xss')</script>", "count": 2}
                    ],
                    "slow_query_count": 0,
                    "slow_queries": [],
                },
                "connection_metrics": {},
            }
        )

        class FakeRequest:
            pass

        response = panel_view(FakeRequest())
        content = response.content.decode()
        # The injected SQL should be escaped in the output
        assert "&lt;script&gt;alert(" in content
        # The raw unescaped payload must NOT appear
        assert "<script>alert(" not in content
