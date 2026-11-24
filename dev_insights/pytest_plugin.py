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

The numbers are compared with a versioned baseline file
(``dev_insights_baseline.json`` by default). A request that goes **above** the
baseline fails the test, with the view, the metric (before -> now), the most
repeated query and where it ran. Lower numbers pass, and the end of the run
says the baseline can be tightened. A view with no baseline fails too, so new
endpoints cannot slip in unmeasured.

    pytest --dev-insights-update-baseline   # write / refresh the baseline

The baseline keeps, per view, the highest value seen in the run (a view hit
by several tests with different data is held to its worst request). Views not
exercised in an update run are kept as they were.
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
        "--dev-insights-baseline",
        default=None,
        metavar="PATH",
        help="baseline file (default: ini dev_insights_baseline, "
        f"or {DEFAULT_BASELINE})",
    )
    parser.addini(
        "dev_insights_baseline",
        default=DEFAULT_BASELINE,
        help="django-dev-insights baseline file, relative to the rootdir",
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
    config._dev_insights = Session(config)


def pytest_collection_modifyitems(items):
    for item in items:
        if item.get_closest_marker("dev_insights") is None:
            continue
        names = getattr(item, "fixturenames", None)
        if names is not None and "dev_insights" not in names:
            names.append("dev_insights")


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


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    session = getattr(config, "_dev_insights", None)
    if session is None:
        return
    for line in session.finish():
        terminalreporter.write_line(line)


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

    def start(self):
        from django.core.signals import request_finished, request_started

        from .recorder import QueryRecorder
        from .template_trace import patch_template_render

        patch_template_render()
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

    def __init__(self, config):
        self.config = config
        self.updating = bool(config.getoption(UPDATE_FLAG))
        self._baseline = None
        self.observed = {}  # view -> {metric: max value}
        self.observed_by = {}  # view -> nodeid of the worst request

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

    def observe(self, measurement, nodeid):
        current = self.observed.setdefault(measurement.view, dict.fromkeys(METRICS, 0))
        for k in METRICS:
            if measurement.values[k] > current[k]:
                current[k] = measurement.values[k]
                self.observed_by[measurement.view] = nodeid

    def compare(self, m):
        base = self.baseline.get(m.view)
        if base is None:
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
        if not self.observed:
            return []
        if self.updating:
            return self._write()
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
        if not improved:
            return []
        return [
            f"dev-insights: {len(improved)} view(s) now do better than the baseline:",
            *improved,
            f"  If this run covers every test that hits them, tighten the baseline: "
            f"pytest {UPDATE_FLAG}",
        ]

    def _write(self):
        old = dict(self.baseline)
        new = dict(old)
        new.update({view: dict(values) for view, values in self.observed.items()})
        write_baseline(self.path, new)
        added = sorted(set(new) - set(old))
        changed = sorted(v for v in self.observed if v in old and old[v] != new[v])
        lines = [f"dev-insights: baseline written to {self.display_path()}"]
        lines += [f"  + {v} {_fmt_values(new[v])}" for v in added]
        lines += [
            f"  ~ {v} {_fmt_values(old[v])} -> {_fmt_values(new[v])}" for v in changed
        ]
        if not added and not changed:
            lines.append("  no changes")
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
