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


def _plugin_autoloaded(config):
    """Is the plugin loaded through the pytest11 entry point in this
    environment? Then the subprocess gets it the same way; otherwise it is
    passed with -p. (Asking pytest avoids stale package metadata.)"""
    return config.pluginmanager.hasplugin("dev_insights")


@pytest.fixture
def project(pytester, monkeypatch, pytestconfig):
    shutil.copytree(PROJECT, str(pytester.path), dirs_exist_ok=True)
    monkeypatch.setenv(
        "PYTHONPATH", ROOT + os.pathsep + os.environ.get("PYTHONPATH", "")
    )
    for var in ("SHOP_N_PLUS_ONE", "SHOP_EXTRA_TEMPLATE"):
        monkeypatch.delenv(var, raising=False)

    autoloaded = _plugin_autoloaded(pytestconfig)

    def run(*args, pytest_django=False):
        extra = [] if autoloaded else ["-p", "dev_insights.pytest_plugin"]
        # the sample project configures Django itself; pytest-django (if
        # installed) would block its database access. randomly would shuffle
        # tests whose order some cases below rely on.
        if not pytest_django:
            extra += ["-p", "no:django"]
        extra += ["-p", "no:randomly"]
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


def test_plugin_is_inert_without_the_marker(pytester, monkeypatch, pytestconfig):
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
    extra = (
        [] if _plugin_autoloaded(pytestconfig) else ["-p", "dev_insights.pytest_plugin"]
    )
    # pytest-django (if installed) imports Django by itself; this test is
    # about what *this* plugin loads
    extra += ["-p", "no:django"]
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


# ---- order independence: caches are cleared before each measured request ----

WARM_THEN_MEASURE = """
import pytest
from django.test import Client


def test_a_warms_caches():
    from django.contrib.contenttypes.models import ContentType
    from shop.cache import author_count
    from shop.models import Book

    ContentType.objects.get_for_model(Book)
    author_count()


@pytest.mark.dev_insights
def test_b_kinds():
    assert Client().get("/kinds/").status_code == 200


@pytest.mark.dev_insights
def test_c_stats():
    assert Client().get("/stats/").status_code == 200
"""


def _views(project):
    return json.loads(_baseline(project))["views"]


def test_contenttype_cache_does_not_make_the_baseline_order_dependent(
    project, pytester
):
    pytester.makepyfile(test_cache=WARM_THEN_MEASURE)
    project(UPDATE, "test_cache.py").assert_outcomes(passed=3)
    # cache warmed by test_a, but the request is measured cold: 1 query
    assert _views(project)["GET shop:kinds"]["queries"] == 1
    # same test alone (cold cache, as with -k, xdist or random order)
    project("test_cache.py", "-k", "test_b_kinds").assert_outcomes(
        passed=1, deselected=2
    )


def test_project_cache_needs_clearing_and_the_ini_hook_does_it(project, pytester):
    pytester.makepyfile(test_cache=WARM_THEN_MEASURE)
    # without registering it, a project cache makes the number order-dependent
    project(UPDATE, "test_cache.py").assert_outcomes(passed=3)
    assert _views(project)["GET shop:stats"]["queries"] == 0
    alone = project("test_cache.py", "-k", "test_c_stats")
    alone.assert_outcomes(failed=1, deselected=2)
    alone.stdout.fnmatch_lines(["*queries: 0 -> 1*"])

    # registered through the ini key: measured cold in both orders
    pytester.makeini("[pytest]\ndev_insights_clear_caches = shop.cache.clear\n")
    os.remove(os.path.join(str(project.path), "dev_insights_baseline.json"))
    project(UPDATE, "test_cache.py").assert_outcomes(passed=3)
    assert _views(project)["GET shop:stats"]["queries"] == 1
    project("test_cache.py", "-k", "test_c_stats").assert_outcomes(
        passed=1, deselected=2
    )


# ---- baseline hygiene ---------------------------------------------------------


def test_partial_update_never_lowers_and_says_so(project, monkeypatch):
    monkeypatch.setenv("SHOP_N_PLUS_ONE", "1")
    project(UPDATE).assert_outcomes(passed=3)
    monkeypatch.delenv("SHOP_N_PLUS_ONE")
    result = project(UPDATE, "-k", "test_books")
    result.assert_outcomes(passed=1, deselected=2)
    result.stdout.fnmatch_lines(["*PARTIAL RUN*never lowered*(1 kept higher)*"])
    assert _views(project)["GET shop:books"]["queries"] == 4

    # the full run tightens
    project(UPDATE).assert_outcomes(passed=3)
    assert _views(project)["GET shop:books"]["queries"] == 1


def test_prune_removes_views_no_test_hit_only_on_full_runs(project):
    project(UPDATE).assert_outcomes(passed=3)
    path = os.path.join(str(project.path), "dev_insights_baseline.json")
    data = json.loads(_baseline(project))
    data["views"]["GET shop:gone"] = {
        "queries": 1,
        "similar_queries": 0,
        "templates": 0,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)

    partial = project(UPDATE, "--dev-insights-prune", "-k", "test_books")
    partial.stdout.fnmatch_lines(["*PARTIAL RUN*--dev-insights-prune was skipped*"])
    assert "GET shop:gone" in _views(project)

    full = project(UPDATE, "--dev-insights-prune")
    full.stdout.fnmatch_lines(["*- GET shop:gone (no test hit it)*"])
    views = _views(project)
    assert "GET shop:gone" not in views and "GET shop:books" in views


def test_prune_requires_update(project):
    result = project("--dev-insights-prune")
    assert result.ret != 0
    result.stderr.fnmatch_lines(["*only works with --dev-insights-update-baseline*"])


def test_new_view_can_warn_instead_of_failing(project):
    result = project("--dev-insights-new-view=warn")
    result.assert_outcomes(passed=3)
    result.stdout.fnmatch_lines(
        ["*3 view(s) have no baseline*", "*GET shop:books queries=1*"]
    )
    baseline = os.path.join(str(project.path), "dev_insights_baseline.json")
    assert not os.path.exists(baseline)
    # the default stays "fail"
    project().assert_outcomes(passed=1, failed=2)


def test_new_view_warn_from_ini(project, pytester):
    pytester.makeini("[pytest]\ndev_insights_new_view = warn\n")
    project().assert_outcomes(passed=3)


# ---- pytest-xdist and pytest-django --------------------------------------------


def test_xdist_improvements_reach_the_controller(project, monkeypatch):
    pytest.importorskip("xdist")
    monkeypatch.setenv("SHOP_N_PLUS_ONE", "1")
    project(UPDATE).assert_outcomes(passed=3)
    monkeypatch.delenv("SHOP_N_PLUS_ONE")
    result = project("-n", "2")
    result.assert_outcomes(passed=3)
    result.stdout.fnmatch_lines(
        [
            "*1 view(s) now do better than the baseline*",
            "*GET shop:books: queries 4 -> 1*",
        ]
    )


def test_xdist_new_views_warning_reaches_the_controller(project):
    pytest.importorskip("xdist")
    result = project("-n", "2", "--dev-insights-new-view=warn")
    result.assert_outcomes(passed=3)
    result.stdout.fnmatch_lines(["*3 view(s) have no baseline*"])


def test_xdist_refuses_update(project):
    pytest.importorskip("xdist")
    result = project(UPDATE, "-n", "2")
    assert result.ret != 0
    result.stderr.fnmatch_lines(["*cannot run with pytest-xdist*"])


PYTEST_DJANGO_CONFTEST = """
import django
import pytest
from django.conf import settings

settings.configure(
    DEBUG=True,  # pytest-django forces it to False during tests
    DATABASES={
        "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}
    },
    INSTALLED_APPS=["django.contrib.contenttypes", "shop"],
    ROOT_URLCONF="urls",
    TEMPLATES=[
        {
            "BACKEND": "django.template.backends.django.DjangoTemplates",
            "APP_DIRS": True,
        }
    ],
    ALLOWED_HOSTS=["testserver"],
    DEFAULT_AUTO_FIELD="django.db.models.AutoField",
)
django.setup()


@pytest.fixture(autouse=True)
def data(db):
    from shop.models import Author, Book

    for i in range(3):
        author = Author.objects.create(name=f"a{i}")
        Book.objects.create(title=f"book {i}", author=author)
"""

PYTEST_DJANGO_TESTS = """
import pytest
from django.test import TestCase


@pytest.mark.dev_insights
def test_books(client):
    assert client.get("/books/").status_code == 200


@pytest.mark.dev_insights
class TestBooks(TestCase):
    def test_books(self):
        self.client.get("/books/")
"""


def test_with_pytest_django_client_and_testcase(project, pytester, monkeypatch):
    """The main use case: pytest-django's client fixture and django.test.TestCase,
    with DEBUG forced to False by pytest-django."""
    pytest.importorskip("pytest_django")
    pytester.makeconftest(PYTEST_DJANGO_CONFTEST)
    os.remove(os.path.join(str(project.path), "test_shop.py"))
    pytester.makepyfile(test_pd=PYTEST_DJANGO_TESTS)

    first = project(pytest_django=True)
    first.assert_outcomes(failed=2)
    first.stdout.fnmatch_lines(["*no baseline for view GET shop:books*"])
    project(UPDATE, pytest_django=True).assert_outcomes(passed=2)
    project(pytest_django=True).assert_outcomes(passed=2)

    monkeypatch.setenv("SHOP_N_PLUS_ONE", "1")
    regressed = project(pytest_django=True)
    regressed.assert_outcomes(failed=2)
    regressed.stdout.fnmatch_lines(["*similar queries (N+1 suspects): 0 -> 3*"])
