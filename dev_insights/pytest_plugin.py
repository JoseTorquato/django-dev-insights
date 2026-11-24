"""pytest plugin: a per-view query baseline that only tightens.

Registered through the ``pytest11`` entry point, but inert until a test asks
for it: nothing from Django or from the middleware is imported, patched or
connected unless a test uses the ``dev_insights`` marker or fixture.

    @pytest.mark.dev_insights
    def test_book_list(client):
        client.get("/books/")

Every request made through Django's test client during such a test is
measured per view (HTTP method + URL name):

- ``queries``: total queries;
- ``similar_queries``: queries that share a normalized signature with another
  query of the same request (N+1 suspects);
- ``templates``: template renders (a count; render *time* varies between CI
  machines and is not part of the baseline).

Each measured request starts with Django's process-wide caches cleared
(ContentType, Site, plus any callable listed in the ini key
``dev_insights_clear_caches``), so its numbers do not depend on which tests
ran before it.

The numbers are compared with a versioned baseline file
(``dev_insights_baseline.json`` by default). A request that goes **above** the
baseline fails the test, with the view, the metric (before -> now), the most
repeated query and where it ran. Lower numbers pass, and the end of the run
says the baseline can be tightened. A view with no baseline fails too (or only
warns, with ``--dev-insights-new-view=warn``).

    pytest --dev-insights-update-baseline            # write / refresh
    pytest --dev-insights-update-baseline --dev-insights-prune   # and drop views
                                                                 # no test hit

The baseline keeps, per view, the highest value seen in the run. An update on
a partial run (``-k``, ``-m``, node ids, ``-x``...) never lowers a view and
never prunes: only a full run can tighten.
"""

import json
import os

import pytest

DEFAULT_BASELINE = "dev_insights_baseline.json"
METRICS = ("queries", "similar_queries", "templates")
LABELS = {
    "queries": "queries",
    "similar_queries": "similar queries (N+1 suspects)",
    "templates": "template renders",
}
UPDATE_FLAG = "--dev-insights-update-baseline"
PRUNE_FLAG = "--dev-insights-prune"
NEW_VIEW_FLAG = "--dev-insights-new-view"


# ---- pytest hooks ------------------------------------------------------------


def pytest_addoption(parser):
    group = parser.getgroup("dev-insights", "django-dev-insights query baseline")
    group.addoption(
        UPDATE_FLAG,
        action="store_true",
        default=False,
        help="write the measured numbers to the baseline file instead of "
        "comparing (tests that use dev_insights do not fail)",
    )
    group.addoption(
        PRUNE_FLAG,
        action="store_true",
        default=False,
        help=f"with {UPDATE_FLAG} on a full run: remove views that no test hit",
    )
    group.addoption(
        "--dev-insights-baseline",
        default=None,
        metavar="PATH",
        help="baseline file (default: ini dev_insights_baseline, "
        f"or {DEFAULT_BASELINE})",
    )
    group.addoption(
        NEW_VIEW_FLAG,
        choices=("fail", "warn"),
        default=None,
        help="a view with no baseline fails the test (default) or only warns",
    )
    parser.addini(
        "dev_insights_baseline",
        default=DEFAULT_BASELINE,
        help="django-dev-insights baseline file, relative to the rootdir",
    )
    parser.addini(
        "dev_insights_new_view",
        default="fail",
        help="fail | warn: what to do with a view that has no baseline",
    )
    parser.addini(
        "dev_insights_clear_caches",
        type="linelist",
        default=[],
        help="dotted paths of callables run before each measured request, to "
        "clear project caches that would make query counts order-dependent",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "dev_insights: measure queries, similar queries and template renders "
        "per view for requests made by the Django test client, and compare "
        "them with the baseline file",
    )
    if config.getoption(UPDATE_FLAG) and getattr(config.option, "numprocesses", None):
        raise pytest.UsageError(
            f"{UPDATE_FLAG} cannot run with pytest-xdist (-n): every worker would "
            "write the baseline. Run the update without -n."
        )
    if config.getoption(PRUNE_FLAG) and not config.getoption(UPDATE_FLAG):
        raise pytest.UsageError(f"{PRUNE_FLAG} only works with {UPDATE_FLAG}")
    new_view = config.getoption(NEW_VIEW_FLAG) or config.getini("dev_insights_new_view")
    if new_view not in ("fail", "warn"):
        raise pytest.UsageError(
            f"dev_insights_new_view must be fail or warn, not {new_view!r}"
        )
    config._dev_insights = Session(config, new_view)
    if config.pluginmanager.hasplugin("xdist"):
        config.pluginmanager.register(_XdistController(config), "dev_insights_xdist")


def pytest_collection_modifyitems(items):
    for item in items:
        if item.get_closest_marker("dev_insights") is None:
            continue
        names = getattr(item, "fixturenames", None)
        if names is not None and "dev_insights" not in names:
            names.append("dev_insights")


def pytest_deselected(items):
    if items:
        config = items[0].config
        session = getattr(config, "_dev_insights", None)
        if session is not None:
            session.partial_reasons.add("tests were deselected (-k / -m)")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    guard = getattr(item, "_dev_insights_guard", None)
    if guard is None or call.when != "call":
        return
    report = outcome.get_result()
    if not report.passed:
        return
    failures = guard.failures()
    if failures:
        report.outcome = "failed"
        report.longrepr = "\n\n".join(failures)


def pytest_sessionfinish(session, exitstatus):
    state = getattr(session.config, "_dev_insights", None)
    if state is None:
        return
    if session.shouldstop or session.shouldfail:
        state.partial_reasons.add("the run stopped early (-x / --maxfail)")
    workeroutput = getattr(session.config, "workeroutput", None)
    if workeroutput is not None:  # pytest-xdist worker: hand over to the controller
        workeroutput["dev_insights"] = state.export()


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    session = getattr(config, "_dev_insights", None)
    if session is None or hasattr(config, "workerinput"):
        return
    for line in session.finish():
        terminalreporter.write_line(line)


class _XdistController:
    """Collects what each xdist worker observed, so the summary (improvements,
    new views) is printed by the controller."""

    def __init__(self, config):
        self.config = config

    def pytest_testnodedown(self, node, error):
        data = getattr(node, "workeroutput", {}).get("dev_insights")
        if data:
            self.config._dev_insights.merge(data)


@pytest.fixture
def dev_insights(request):
    """Measure the requests of this test per view and compare with the baseline."""
    guard = Guard(request.config._dev_insights, request.node.nodeid)
    guard.start()
    request.node._dev_insights_guard = guard
    try:
        yield guard
    finally:
        guard.stop()


# ---- measurement ---------------------------------------------------------------


def _view_key(environ=None, scope=None):
    from django.urls import Resolver404, resolve

    if environ is not None:
        method = environ.get("REQUEST_METHOD", "GET")
        path = environ.get("PATH_INFO", "/")
    elif scope is not None:
        method, path = scope.get("method", "GET"), scope.get("path", "/")
    else:
        return "? <unknown>"
    try:
        match = resolve(path)
    except Resolver404:
        return f"{method} {path} (unresolved)"
    return f"{method} {match.view_name}"


def clear_django_caches():
    """Drop Django's process-wide caches that save queries once warm.

    - ContentType: ``get_for_model`` / ``get_for_id`` keep a per-process cache
      (generic relations, admin log, permissions all go through it).
    - Site: ``Site.objects.get_current()`` caches the current site.

    Without this, a view measured after another test warmed these caches runs
    fewer queries than the same view measured alone, and the baseline would
    depend on test order (-k, xdist, random order). Per-object caches (e.g. a
    user's permission cache) live on the instance and need no clearing.
    """
    from django.apps import apps

    if apps.is_installed("django.contrib.contenttypes"):
        from django.contrib.contenttypes.models import ContentType

        ContentType.objects.clear_cache()
    if apps.is_installed("django.contrib.sites"):
        from django.contrib.sites.models import Site

        Site.objects.clear_cache()


def _import_callable(dotted):
    module_name, _, attr = dotted.rpartition(".")
    if not module_name:
        raise pytest.UsageError(f"dev_insights_clear_caches: {dotted!r} is not dotted")
    import importlib

    return getattr(importlib.import_module(module_name), attr)


class Measurement:
    def __init__(self, view, metrics, templates):
        self.view = view
        self.values = {
            "queries": metrics["query_count"],
            "similar_queries": metrics["similar_query_count"],
            "templates": templates,
        }
        self.top_similar = (
            metrics["similar_sqls"][0] if metrics["similar_sqls"] else None
        )


class Guard:
    """Measures the requests of one test."""

    def __init__(self, session, nodeid):
        self.session = session
        self.nodeid = nodeid
        self.measurements = []
        self._current = None
        self._recorder = None
        self._clearers = []

    def start(self):
        from django.core.signals import request_finished, request_started

        from .recorder import QueryRecorder
        from .template_trace import patch_template_render

        patch_template_render()
        self._clearers = [clear_django_caches] + [
            _import_callable(path)
            for path in self.session.config.getini("dev_insights_clear_caches")
        ]
        self._recorder = QueryRecorder().__enter__()
        request_started.connect(
            self._started, dispatch_uid=f"dev_insights_s_{id(self)}"
        )
        request_finished.connect(
            self._finished, dispatch_uid=f"dev_insights_f_{id(self)}"
        )

    def stop(self):
        from django.core.signals import request_finished, request_started

        request_started.disconnect(dispatch_uid=f"dev_insights_s_{id(self)}")
        request_finished.disconnect(dispatch_uid=f"dev_insights_f_{id(self)}")
        if self._recorder is not None:
            self._recorder.__exit__(None, None, None)
            self._recorder = None

    def _started(self, sender, environ=None, scope=None, **kwargs):
        from .collectors.template import get_render_count

        # every measured request starts cold, whatever ran before it
        for clear in self._clearers:
            clear()
        self._current = (
            _view_key(environ, scope),
            self._recorder.mark(new_origins=True),
            get_render_count(),
        )

    def _finished(self, sender, **kwargs):
        from .collectors.template import get_render_count

        if self._current is None:
            return
        view, start, templates_before = self._current
        self._current = None
        metrics = self._recorder.metrics(start)
        measurement = Measurement(view, metrics, get_render_count() - templates_before)
        self.measurements.append(measurement)
        self.session.observe(measurement, self.nodeid)

    def failures(self):
        """One message per view that got worse (or has no baseline)."""
        if self.session.updating:
            return []
        worst = {}
        for m in self.measurements:
            seen = worst.get(m.view)
            if seen is None or _excess(m, self.session) > _excess(seen, self.session):
                worst[m.view] = m
        messages = []
        for view, m in worst.items():
            message = self.session.compare(m)
            if message:
                messages.append(message)
        return messages


def _excess(measurement, session):
    base = session.baseline.get(measurement.view)
    if base is None:
        return 0
    return sum(max(0, measurement.values[k] - base.get(k, 0)) for k in METRICS)


# ---- baseline ----------------------------------------------------------------


def _format_origin(origin):
    if not origin:
        return ""
    return f"{origin['file']}:{origin['line']} in {origin['func']}"


class Session:
    """Baseline file and what the run observed."""

    def __init__(self, config, new_view="fail"):
        self.config = config
        self.new_view = new_view
        self.updating = bool(config.getoption(UPDATE_FLAG))
        self.pruning = bool(config.getoption(PRUNE_FLAG))
        self._baseline = None
        self.observed = {}  # view -> {metric: max value}
        self.new_views = {}  # view -> values, for --dev-insights-new-view=warn
        self.partial_reasons = set()
        if config.getoption("file_or_dir", None) and not self._args_are_testpaths():
            self.partial_reasons.add("specific paths or test ids were given")
        if config.getoption("lf", False) or config.getoption("failedfirst", False):
            self.partial_reasons.add("--lf / --ff")

    def _args_are_testpaths(self):
        testpaths = self.config.getini("testpaths") or []
        args = self.config.getoption("file_or_dir") or []
        norm = [os.path.normpath(str(a)) for a in args]
        return bool(testpaths) and sorted(norm) == sorted(
            os.path.normpath(str(t)) for t in testpaths
        )

    @property
    def path(self):
        name = self.config.getoption("--dev-insights-baseline") or self.config.getini(
            "dev_insights_baseline"
        )
        root = getattr(self.config, "rootpath", None) or self.config.rootdir
        return os.path.join(str(root), name)

    def display_path(self):
        try:
            return os.path.relpath(self.path)
        except ValueError:
            return self.path

    @property
    def baseline(self):
        if self._baseline is None:
            self._baseline = read_baseline(self.path)
        return self._baseline

    def observe(self, measurement, nodeid=None):
        self._take_max(self.observed, measurement.view, measurement.values)

    @staticmethod
    def _take_max(store, view, values):
        current = store.setdefault(view, dict.fromkeys(METRICS, 0))
        for k in METRICS:
            current[k] = max(current[k], int(values.get(k, 0)))

    # xdist: worker -> controller
    def export(self):
        return {
            "observed": self.observed,
            "new_views": self.new_views,
            "partial_reasons": sorted(self.partial_reasons),
        }

    def merge(self, data):
        for view, values in (data.get("observed") or {}).items():
            self._take_max(self.observed, view, values)
        for view, values in (data.get("new_views") or {}).items():
            self._take_max(self.new_views, view, values)
        self.partial_reasons.update(data.get("partial_reasons") or [])

    def compare(self, m):
        base = self.baseline.get(m.view)
        if base is None:
            if self.new_view == "warn":
                self._take_max(self.new_views, m.view, m.values)
                return ""
            return (
                f"dev-insights: no baseline for view {m.view} "
                f"in {self.display_path()}\n"
                + "".join(f"  {LABELS[k]}: {m.values[k]}\n" for k in METRICS)
                + f"  Record it with: pytest {UPDATE_FLAG}"
            )
        worse = [k for k in METRICS if m.values[k] > base.get(k, 0)]
        if not worse:
            return ""
        lines = [
            f"dev-insights: {m.view} got worse than the baseline "
            f"({self.display_path()})"
        ]
        for k in worse:
            lines.append(f"  {LABELS[k]}: {base.get(k, 0)} -> {m.values[k]}")
        if m.top_similar and ("queries" in worse or "similar_queries" in worse):
            lines.append(
                f"  most repeated query ({m.top_similar['count']}x): "
                f"{m.top_similar['signature']}"
            )
            origin = _format_origin(m.top_similar.get("origin"))
            if origin:
                lines.append(f"    at {origin}")
        lines.append(
            f"  If this is intended, update the baseline: pytest {UPDATE_FLAG}"
        )
        return "\n".join(lines)

    def finish(self):
        """Lines for the terminal summary; writes the file in update mode."""
        if self.updating:
            return self._write() if self.observed or self.pruning else []
        lines = []
        if self.new_views:
            lines.append(
                f"dev-insights: {len(self.new_views)} view(s) have no baseline "
                f"(not failing: {NEW_VIEW_FLAG}=warn):"
            )
            lines += [
                f"  {view} {_fmt_values(values)}"
                for view, values in sorted(self.new_views.items())
            ]
            lines.append(f"  Record them with: pytest {UPDATE_FLAG}")
        improved = []
        for view, values in sorted(self.observed.items()):
            base = self.baseline.get(view)
            if base is None:
                continue
            better = [k for k in METRICS if values[k] < base.get(k, 0)]
            worse = [k for k in METRICS if values[k] > base.get(k, 0)]
            if better and not worse:
                changes = ", ".join(
                    f"{k} {base.get(k, 0)} -> {values[k]}" for k in better
                )
                improved.append(f"  {view}: {changes}")
        if improved:
            lines.append(
                f"dev-insights: {len(improved)} view(s) now do better than the "
                "baseline:"
            )
            lines += improved
            lines.append(
                "  If this run covers every test that hits them, tighten the "
                f"baseline: pytest {UPDATE_FLAG}"
            )
        return lines

    def _write(self):
        old = dict(self.baseline)
        partial = sorted(self.partial_reasons)
        new = dict(old)
        not_lowered = []
        for view, values in self.observed.items():
            if partial and view in old:
                # a subset of the tests may not reach a view's worst request:
                # keep the higher value, only a full run tightens
                merged = {k: max(int(old[view].get(k, 0)), values[k]) for k in METRICS}
                if merged != values:
                    not_lowered.append(view)
                new[view] = merged
            else:
                new[view] = dict(values)
        pruned = []
        if self.pruning and not partial:
            pruned = sorted(set(old) - set(self.observed))
            for view in pruned:
                del new[view]
        write_baseline(self.path, new)
        added = sorted(set(new) - set(old))
        changed = sorted(v for v in new if v in old and old[v] != new[v])
        lines = [f"dev-insights: baseline written to {self.display_path()}"]
        lines += [f"  + {v} {_fmt_values(new[v])}" for v in added]
        lines += [
            f"  ~ {v} {_fmt_values(old[v])} -> {_fmt_values(new[v])}" for v in changed
        ]
        lines += [f"  - {v} (no test hit it)" for v in pruned]
        if not (added or changed or pruned):
            lines.append("  no changes")
        if partial:
            lines.append(
                "dev-insights: PARTIAL RUN (" + "; ".join(partial) + "): "
                "views were added or raised, never lowered"
                + (f" ({len(not_lowered)} kept higher)" if not_lowered else "")
                + (f", and {PRUNE_FLAG} was skipped" if self.pruning else "")
                + ". Run the whole suite to tighten or prune."
            )
        return lines


def _fmt_values(values):
    return " ".join(f"{k}={values.get(k, 0)}" for k in METRICS)


def read_baseline(path):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {view: dict(values) for view, values in (data.get("views") or {}).items()}


def write_baseline(path, views):
    """One view per line, sorted: a regression shows up as a one-line diff."""
    lines = ["{", '  "version": 1,', '  "views": {']
    items = sorted(views.items())
    for i, (view, values) in enumerate(items):
        ordered = {k: int(values.get(k, 0)) for k in METRICS}
        comma = "," if i < len(items) - 1 else ""
        lines.append(f"    {json.dumps(view)}: {json.dumps(ordered)}{comma}")
    lines += ["  }", "}", ""]
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
