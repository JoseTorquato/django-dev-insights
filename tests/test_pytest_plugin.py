"""The pytest guard, run end to end in a separate pytest process against the
sample project in tests/plugin_project (Django, SQLite in memory, DEBUG=False).
"""

import json
import os
import re
import shutil

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PROJECT = os.path.join(os.path.dirname(__file__), "plugin_project")
UPDATE = "--dev-insights-update-baseline"


def _entry_point_installed():
    try:
        from importlib.metadata import entry_points
    except ImportError:  # pragma: no cover - Python < 3.8
        return False
    eps = entry_points()
    group = (
        eps.select(group="pytest11")
        if hasattr(eps, "select")
        else eps.get("pytest11", [])
    )
    return any(ep.value == "dev_insights.pytest_plugin" for ep in group)


@pytest.fixture
def project(pytester, monkeypatch):
    shutil.copytree(PROJECT, str(pytester.path), dirs_exist_ok=True)
    monkeypatch.setenv(
        "PYTHONPATH", ROOT + os.pathsep + os.environ.get("PYTHONPATH", "")
    )
    for var in ("SHOP_N_PLUS_ONE", "SHOP_EXTRA_TEMPLATE"):
        monkeypatch.delenv(var, raising=False)

    def run(*args):
        extra = [] if _entry_point_installed() else ["-p", "dev_insights.pytest_plugin"]
        return pytester.runpytest_subprocess(*extra, "-p", "no:cacheprovider", *args)

    run.path = pytester.path
    return run


def _baseline(project):
    with open(
        os.path.join(str(project.path), "dev_insights_baseline.json"), encoding="utf-8"
    ) as f:
        return f.read()


def test_missing_baseline_fails_then_update_writes_it(project):
    result = project()
    result.assert_outcomes(passed=1, failed=2)
    result.stdout.fnmatch_lines(["*no baseline for view GET shop:books*"])

    result = project(UPDATE)
    result.assert_outcomes(passed=3)
    result.stdout.fnmatch_lines(
        ["*baseline written to*", "*+ GET shop:books queries=1*"]
    )
    text = _baseline(project)
    data = json.loads(text)
    # select_related: 1 query; 3 items + the list = 4 template renders
    assert data["views"]["GET shop:books"] == {
        "queries": 1,
        "similar_queries": 0,
        "templates": 4,
    }
    assert data["views"]["GET shop:ping"] == {
        "queries": 0,
        "similar_queries": 0,
        "templates": 0,
    }
    assert "GET /shop-nope/ (unresolved)" in data["views"]
    # one view per line, sorted: friendly diffs
    view_lines = [line for line in text.splitlines() if line.startswith('    "')]
    assert len(view_lines) == 3 and view_lines == sorted(view_lines)

    project().assert_outcomes(passed=3)


def test_n_plus_one_regression_fails_with_view_query_and_origin(project, monkeypatch):
    project(UPDATE).assert_outcomes(passed=3)
    monkeypatch.setenv("SHOP_N_PLUS_ONE", "1")
    result = project("-k", "test_books")
    result.assert_outcomes(failed=1)
    out = result.stdout.str()
    assert "dev-insights: GET shop:books got worse than the baseline" in out
    assert "queries: 1 -> 4" in out
    assert "similar queries (N+1 suspects): 0 -> 3" in out
    assert re.search(r'most repeated query \(3x\): SELECT .*"shop_author".* = \?', out)
    line = 1 + open(
        os.path.join(PROJECT, "shop", "views.py")
    ).read().splitlines().index(
        '        titles.append(f"{book.title} by {book.author.name}")  # N+1 line'
    )
    assert "at shop/views.py:%d in books" % line in out.replace(chr(92), "/"), out
    assert UPDATE in out
    # a failing check never rewrites the baseline
    assert json.loads(_baseline(project))["views"]["GET shop:books"]["queries"] == 1


def test_improvement_passes_and_suggests_tightening(project, monkeypatch):
    monkeypatch.setenv("SHOP_N_PLUS_ONE", "1")
    project(UPDATE).assert_outcomes(passed=3)
    monkeypatch.delenv("SHOP_N_PLUS_ONE")
    result = project()
    result.assert_outcomes(passed=3)
    result.stdout.fnmatch_lines(
        [
            "*1 view(s) now do better than the baseline*",
            "*GET shop:books: queries 4 -> 1*",
        ]
    )


def test_template_count_is_part_of_the_baseline(project, monkeypatch):
    project(UPDATE).assert_outcomes(passed=3)
    monkeypatch.setenv("SHOP_EXTRA_TEMPLATE", "1")
    result = project("-k", "test_books")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*template renders: 4 -> 5*"])
    assert "most repeated query" not in result.stdout.str()


def test_update_keeps_views_not_exercised(project):
    project(UPDATE).assert_outcomes(passed=3)
    project(UPDATE, "-k", "test_ping").assert_outcomes(passed=1, deselected=2)
    assert "GET shop:books" in json.loads(_baseline(project))["views"]


def test_custom_baseline_path(project):
    project(UPDATE, "--dev-insights-baseline", "ci/queries.json").assert_outcomes(
        passed=3
    )
    assert os.path.exists(os.path.join(str(project.path), "ci", "queries.json"))
    assert not os.path.exists(
        os.path.join(str(project.path), "dev_insights_baseline.json")
    )


def test_plugin_is_inert_without_the_marker(pytester, monkeypatch):
    """Installed but unused: no Django import, no patch, no file."""
    monkeypatch.setenv(
        "PYTHONPATH", ROOT + os.pathsep + os.environ.get("PYTHONPATH", "")
    )
    pytester.makepyfile(test_plain="""
        import sys

        def test_nothing_loaded():
            assert "django" not in sys.modules
            assert "dev_insights.recorder" not in sys.modules
        """)
    extra = [] if _entry_point_installed() else ["-p", "dev_insights.pytest_plugin"]
    result = pytester.runpytest_subprocess(*extra, "-p", "no:cacheprovider", UPDATE)
    result.assert_outcomes(passed=1)
    assert not os.path.exists(
        os.path.join(str(pytester.path), "dev_insights_baseline.json")
    )


def test_entry_point_is_declared():
    with open(os.path.join(ROOT, "pyproject.toml"), encoding="utf-8") as f:
        text = f.read()
    assert "[project.entry-points.pytest11]\n" in text
    assert 'dev_insights = "dev_insights.pytest_plugin"' in text


def test_write_baseline_is_valid_sorted_json(tmp_path):
    from dev_insights.pytest_plugin import read_baseline, write_baseline

    path = str(tmp_path / "b.json")
    views = {
        "POST api:orders": {"queries": 7, "similar_queries": 2, "templates": 0},
        "GET shop:books": {"templates": 4, "queries": 1, "similar_queries": 0},
    }
    write_baseline(path, views)
    assert read_baseline(path) == views
    text = open(path, encoding="utf-8").read()
    assert text.index("GET shop:books") < text.index("POST api:orders")
    assert (
        '"GET shop:books": {"queries": 1, "similar_queries": 0, "templates": 4}' in text
    )
