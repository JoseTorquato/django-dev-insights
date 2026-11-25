"""QueryRecorder against a real database (SQLite in memory), no DEBUG needed."""

import inspect

import pytest
from django.db import connection, reset_queries
from django.test.utils import override_settings

from dev_insights.recorder import QueryRecorder
from testapp.db import create_tables, seed
from testapp.models import Author, Book

THIS_FILE = "test_recorder.py"


@pytest.fixture(autouse=True)
def tables():
    create_tables()
    seed(authors=3)


def n_plus_one():
    names = []
    for book in Book.objects.order_by("id"):
        names.append(book.author.name)  # one query per book: the N+1
    return names


N_PLUS_ONE_LINE = inspect.getsourcelines(n_plus_one)[1] + 3


def test_n_plus_one_by_foreign_key_is_similar_not_duplicate():
    with QueryRecorder() as rec:
        assert len(n_plus_one()) == 3
    m = rec.metrics()
    assert m["query_count"] == 4
    # 0.3.0 semantics kept: different ids are not exact duplicates
    assert m["duplicate_query_count"] == 0
    assert m["similar_query_count"] == 3
    top = m["similar_sqls"][0]
    assert top["count"] == 3
    assert '"testapp_author"' in top["signature"] and "= ?" in top["signature"]


def test_origin_points_to_the_line_that_ran_the_query():
    with QueryRecorder() as rec:
        n_plus_one()
    origin = rec.metrics()["similar_sqls"][0]["origin"]
    assert origin["file"].endswith(THIS_FILE)
    assert origin["line"] == N_PLUS_ONE_LINE
    assert origin["func"] == "n_plus_one"


def test_origin_skips_django_and_this_library():
    with QueryRecorder() as rec:
        list(Author.objects.all())
    origin = rec.entries[0]["origin"]
    assert "django" + "/db" not in origin["file"].replace("\\", "/")
    assert "dev_insights" not in origin["file"]
    assert origin["file"].endswith(THIS_FILE)


def test_origin_captured_only_on_first_occurrence_of_each_signature():
    with QueryRecorder() as rec:
        n_plus_one()
    author_entries = [e for e in rec.entries if '"testapp_author"' in e["sql"]]
    assert len(author_entries) == 3
    assert "origin" in author_entries[0]
    assert all("origin" not in e for e in author_entries[1:])


def test_in_lists_of_different_sizes_are_similar():
    with QueryRecorder() as rec:
        ids = list(Author.objects.values_list("id", flat=True))
        list(Author.objects.filter(id__in=ids[:1]))
        list(Author.objects.filter(id__in=ids[:2]))
        list(Author.objects.filter(id__in=ids))
    m = rec.metrics()
    in_groups = [s for s in m["similar_sqls"] if "IN (...)" in s["signature"]]
    assert len(in_groups) == 1 and in_groups[0]["count"] == 3
    assert m["duplicate_query_count"] == 0


def test_raw_queries_are_grouped_too():
    ids = list(Author.objects.values_list("id", flat=True))
    with QueryRecorder() as rec:
        for pk in ids:
            list(Author.objects.raw("SELECT * FROM testapp_author WHERE id = %s", [pk]))
    m = rec.metrics()
    assert m["similar_query_count"] == 3
    assert m["similar_sqls"][0]["signature"] == (
        "SELECT * FROM testapp_author WHERE id = ?"
    )


def test_exact_duplicates_still_counted_exactly():
    pk = Author.objects.values_list("id", flat=True).first()
    with QueryRecorder() as rec:
        for _ in range(3):
            Author.objects.get(pk=pk)
    m = rec.metrics()
    assert m["duplicate_query_count"] == 3
    assert m["similar_query_count"] == 3
    assert str(pk) in m["duplicate_sqls"][0]["sql"], "SQL shown with its parameters"


@override_settings(DEBUG=False)
def test_works_without_debug():
    """pytest-django and Django's runner force DEBUG=False: connection.queries
    stays empty, the recorder still sees everything."""
    reset_queries()
    with QueryRecorder() as rec:
        n_plus_one()
    assert connection.queries == []
    assert rec.metrics()["similar_query_count"] == 3


def test_mark_slices_per_block():
    with QueryRecorder() as rec:
        list(Author.objects.all())
        start = rec.mark()
        n_plus_one()
    assert rec.metrics(start)["query_count"] == 4
    assert rec.metrics()["query_count"] == 5


def test_recorder_is_removed_on_exit():
    with QueryRecorder() as rec:
        list(Author.objects.all())
    list(Author.objects.all())
    assert len(rec.entries) == 1
    assert connection.execute_wrappers == []


def test_middleware_in_debug_reports_similar_from_connection_queries(capsys):
    """Development path (DEBUG=True, connection.queries) is unchanged and now
    also shows the N+1 as similar queries."""
    import importlib

    from django.conf import settings
    from django.http import HttpResponse

    settings.DEV_INSIGHTS_CONFIG = {}
    import dev_insights.config
    import dev_insights.formatters
    import dev_insights.middleware

    for mod in (dev_insights.config, dev_insights.formatters, dev_insights.middleware):
        importlib.reload(mod)

    class Request:
        path = "/books/"

    def view(request):
        n_plus_one()
        return HttpResponse("ok")

    mw = dev_insights.middleware.DevInsightsMiddleware(view)
    mw(Request())
    out = capsys.readouterr().out
    assert "SIMILAR (N+1?): 3" in out
    assert "DUPLICATES" not in out


def test_sql_trace_attaches_origin_at_execution_time():
    """With ENABLE_TRACEBACKS (DEBUG path), the origin stored with each query is
    the line that ran it, so the collector no longer needs the middleware's
    stack."""
    from django.db.backends.utils import CursorDebugWrapper

    from dev_insights.sql_trace import patch_cursor_debug_wrapper

    original = (CursorDebugWrapper.execute, CursorDebugWrapper.executemany)
    CursorDebugWrapper._dev_insights_patched = False
    try:
        patch_cursor_debug_wrapper()
        reset_queries()
        n_plus_one()
        last = connection.queries[-1]
        assert last["origin"]["line"] == N_PLUS_ONE_LINE
        assert last["origin"]["file"].endswith(THIS_FILE)
        assert THIS_FILE in last["traceback"].splitlines()[0]
    finally:
        CursorDebugWrapper.execute, CursorDebugWrapper.executemany = original
        CursorDebugWrapper._dev_insights_patched = False
