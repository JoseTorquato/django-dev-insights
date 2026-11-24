import os
import sys
import importlib
from unittest.mock import patch, MagicMock
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

    importlib.reload(dev_insights.config)
    importlib.reload(dev_insights.formatters)


# ---------------------------------------------------------------------------
# DBCollector
# ---------------------------------------------------------------------------


class TestDBCollector:
    def _make_queries(self, sqls_with_times):
        """Return a list of query dicts like Django's connection.queries."""
        return [{"sql": sql, "time": str(t)} for sql, t in sqls_with_times]

    def test_basic_query_count(self):
        reload_config()
        from dev_insights.collectors.db import DBCollector

        queries = self._make_queries(
            [
                ("SELECT 1", 0.001),
                ("SELECT 2", 0.002),
            ]
        )

        with patch("dev_insights.collectors.db.connection") as mock_conn:
            mock_conn.queries = []
            collector = DBCollector()
            collector.start_collect()
            mock_conn.queries = queries
            collector.finish_collect()

        metrics = collector.get_metrics()
        assert metrics["query_count"] == 2
        assert metrics["total_db_time_ms"] > 0

    def test_duplicate_detection(self):
        reload_config()
        from dev_insights.collectors.db import DBCollector

        queries = self._make_queries(
            [
                ("SELECT * FROM users", 0.001),
                ("SELECT * FROM users", 0.001),
                ("SELECT * FROM users", 0.001),
                ("SELECT * FROM posts", 0.002),
            ]
        )

        with patch("dev_insights.collectors.db.connection") as mock_conn:
            mock_conn.queries = []
            collector = DBCollector()
            collector.start_collect()
            mock_conn.queries = queries
            collector.finish_collect()

        metrics = collector.get_metrics()
        assert metrics["duplicate_query_count"] == 3
        assert len(metrics["duplicate_sqls"]) == 1
        assert metrics["duplicate_sqls"][0]["sql"] == "SELECT * FROM users"
        assert metrics["duplicate_sqls"][0]["count"] == 3

    def test_slow_query_detection(self):
        reload_config({"SLOW_QUERY_THRESHOLD_MS": 50})
        importlib.reload(__import__("dev_insights.collectors.db", fromlist=["db"]))
        from dev_insights.collectors.db import DBCollector

        queries = self._make_queries(
            [
                ("SELECT fast", 0.001),  # 1ms - not slow
                ("SELECT slow", 0.100),  # 100ms - slow
                ("SELECT very_slow", 0.200),  # 200ms - slow
            ]
        )

        with patch("dev_insights.collectors.db.connection") as mock_conn:
            mock_conn.queries = []
            collector = DBCollector()
            collector.start_collect()
            mock_conn.queries = queries
            collector.finish_collect()

        metrics = collector.get_metrics()
        assert metrics["slow_query_count"] == 2
        assert metrics["slow_queries"][0]["sql"] == "SELECT slow"
        assert metrics["slow_queries"][1]["sql"] == "SELECT very_slow"

    def test_no_queries(self):
        reload_config()
        from dev_insights.collectors.db import DBCollector

        with patch("dev_insights.collectors.db.connection") as mock_conn:
            mock_conn.queries = []
            collector = DBCollector()
            collector.start_collect()
            collector.finish_collect()

        metrics = collector.get_metrics()
        assert metrics["query_count"] == 0
        assert metrics["duplicate_query_count"] == 0
        assert metrics["slow_query_count"] == 0

    def test_uses_traceback_captured_at_execution(self):
        """The traceback shown is the one sql_trace attached when the query
        ran, not a stack taken at the end of the request."""
        reload_config({"ENABLE_TRACEBACKS": True, "SLOW_QUERY_THRESHOLD_MS": 1})
        importlib.reload(__import__("dev_insights.collectors.db", fromlist=["db"]))
        from dev_insights.collectors.db import DBCollector

        origin = {"file": "shop/views.py", "line": 12, "func": "book_list"}
        queries = [
            {"sql": "SELECT dup", "time": "0.001", "traceback": "views.py:12 dup"},
            {"sql": "SELECT dup", "time": "0.001", "traceback": "views.py:99 later"},
            {
                "sql": "SELECT slow_one",
                "time": "0.100",
                "traceback": "views.py:30 slow",
            },
        ]
        queries[0]["origin"] = origin

        with patch("dev_insights.collectors.db.connection") as mock_conn:
            mock_conn.queries = []
            collector = DBCollector()
            collector.start_collect()
            mock_conn.queries = queries
            collector.finish_collect()

        metrics = collector.get_metrics()
        assert metrics["slow_queries"][0]["traceback"] == "views.py:30 slow"
        # the first occurrence's traceback, as recorded at execution time
        assert metrics["duplicate_sqls"][0]["traceback"] == "views.py:12 dup"
        assert metrics["duplicate_sqls"][0]["origin"] == origin
        assert metrics["similar_sqls"][0]["origin"] == origin

    def test_no_traceback_invented_at_end_of_request(self):
        """Without a traceback recorded at execution, none is made up from the
        middleware's own stack (the 0.3.0 behaviour pointed to the wrong
        place)."""
        reload_config({"ENABLE_TRACEBACKS": True, "SLOW_QUERY_THRESHOLD_MS": 1})
        importlib.reload(__import__("dev_insights.collectors.db", fromlist=["db"]))
        from dev_insights.collectors.db import DBCollector

        queries = self._make_queries([("SELECT dup", 0.001), ("SELECT dup", 0.1)])
        with patch("dev_insights.collectors.db.connection") as mock_conn:
            mock_conn.queries = []
            collector = DBCollector()
            collector.start_collect()
            mock_conn.queries = queries
            collector.finish_collect()

        metrics = collector.get_metrics()
        assert "traceback" not in metrics["duplicate_sqls"][0]
        assert "traceback" not in metrics["slow_queries"][0]

    def test_similar_counts_n_plus_one_but_duplicates_stay_exact(self):
        reload_config()
        from dev_insights.collectors.db import DBCollector

        queries = self._make_queries(
            [
                ('SELECT * FROM "book"', 0.001),
                ('SELECT * FROM "author" WHERE "id" = 1', 0.001),
                ('SELECT * FROM "author" WHERE "id" = 2', 0.001),
                ('SELECT * FROM "author" WHERE "id" = 3', 0.001),
            ]
        )
        with patch("dev_insights.collectors.db.connection") as mock_conn:
            mock_conn.queries = []
            collector = DBCollector()
            collector.start_collect()
            mock_conn.queries = queries
            collector.finish_collect()

        metrics = collector.get_metrics()
        assert metrics["duplicate_query_count"] == 0
        assert metrics["similar_query_count"] == 3
        similar = metrics["similar_sqls"][0]
        assert similar["signature"] == 'SELECT * FROM "author" WHERE "id" = ?'
        assert similar["count"] == 3
        assert similar["example"] == 'SELECT * FROM "author" WHERE "id" = 1'


# ---------------------------------------------------------------------------
# ConnectionCollector
# ---------------------------------------------------------------------------


class TestConnectionCollector:
    def test_detects_setup_queries(self):
        reload_config()
        from dev_insights.collectors.connection import ConnectionCollector

        mock_conn = MagicMock()
        mock_conn.queries = [
            {"sql": "SET search_path = 'public'"},
            {"sql": "SELECT VERSION()"},
            {"sql": "SELECT * FROM users"},
        ]
        mock_conn.connection = object()

        with patch("dev_insights.collectors.connection.connections") as mock_conns:
            mock_conns.__iter__ = lambda self: iter(["default"])
            mock_conns.__getitem__ = lambda self, key: mock_conn

            collector = ConnectionCollector()
            # Simulate start with empty queries
            mock_conn.queries = []
            mock_conn.connection = object()
            collector.start_collect()

            # Now add queries
            mock_conn.queries = [
                {"sql": "SET search_path = 'public'"},
                {"sql": "SELECT VERSION()"},
                {"sql": "SELECT * FROM users"},
            ]
            collector.finish_collect()

        metrics = collector.get_metrics()
        assert metrics["total_setup_query_count"] == 2
        setup = metrics["setup_queries"]["default"]
        assert len(setup) == 2
        sqls = [q["sql"] for q in setup]
        assert "SET search_path = 'public'" in sqls
        assert "SELECT VERSION()" in sqls

    def test_detects_connection_reopens(self):
        reload_config()
        from dev_insights.collectors.connection import ConnectionCollector

        mock_conn = MagicMock()
        mock_conn.queries = []
        initial_connection = object()
        mock_conn.connection = initial_connection

        with patch("dev_insights.collectors.connection.connections") as mock_conns:
            mock_conns.__iter__ = lambda self: iter(["default"])
            mock_conns.__getitem__ = lambda self, key: mock_conn

            collector = ConnectionCollector()
            collector.start_collect()

            # Simulate a connection reopen
            mock_conn.connection = object()  # different object
            collector.finish_collect()

        metrics = collector.get_metrics()
        assert "default" in metrics["connection_reopens"]

    def test_no_setup_queries(self):
        reload_config()
        from dev_insights.collectors.connection import ConnectionCollector

        mock_conn = MagicMock()
        mock_conn.queries = []
        conn_obj = object()
        mock_conn.connection = conn_obj

        with patch("dev_insights.collectors.connection.connections") as mock_conns:
            mock_conns.__iter__ = lambda self: iter(["default"])
            mock_conns.__getitem__ = lambda self, key: mock_conn

            collector = ConnectionCollector()
            collector.start_collect()

            mock_conn.queries = [
                {"sql": "SELECT * FROM users"},
                {"sql": "INSERT INTO logs VALUES (1)"},
            ]
            collector.finish_collect()

        metrics = collector.get_metrics()
        assert metrics["total_setup_query_count"] == 0

    def test_show_prefix_detected(self):
        reload_config()
        from dev_insights.collectors.connection import ConnectionCollector

        mock_conn = MagicMock()
        mock_conn.queries = []
        conn_obj = object()
        mock_conn.connection = conn_obj

        with patch("dev_insights.collectors.connection.connections") as mock_conns:
            mock_conns.__iter__ = lambda self: iter(["default"])
            mock_conns.__getitem__ = lambda self, key: mock_conn

            collector = ConnectionCollector()
            collector.start_collect()

            mock_conn.queries = [{"sql": "SHOW server_version"}]
            collector.finish_collect()

        metrics = collector.get_metrics()
        assert metrics["total_setup_query_count"] == 1
