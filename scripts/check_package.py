"""Check an *installed* django-dev-insights before it is published.

Run it with the interpreter of a clean virtualenv where only the built wheel
was installed, from a directory outside the repository, in isolated mode:

    /tmp/clean/bin/python -I scripts/check_package.py --expected-version 0.4.0

It fails (exit 1) unless:

1. ``dev_insights`` is imported from that environment, not from a source tree;
2. the installed version is the expected one, and ``__version__`` agrees;
3. the ``pytest11`` entry point ``dev_insights`` is registered and points to
   ``dev_insights.pytest_plugin``;
4. the plugin works through that entry point (no ``-p``): a minimal Django
   project fails without a baseline, records one with
   ``--dev-insights-update-baseline`` and then passes.

A published version cannot be replaced: everything that can be wrong with the
package has to show up here, before the upload.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import textwrap
from importlib.metadata import entry_points, version

CONFTEST = """
import django
from django.conf import settings

settings.configure(
    DEBUG=False,
    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
    INSTALLED_APPS=["django.contrib.contenttypes"],
    ROOT_URLCONF="urls",
    ALLOWED_HOSTS=["testserver"],
    DEFAULT_AUTO_FIELD="django.db.models.AutoField",
)
django.setup()
"""

URLS = """
from django.http import HttpResponse
from django.urls import path

urlpatterns = [path("ping/", lambda request: HttpResponse("ok"), name="ping")]
"""

TEST = """
import pytest
from django.test import Client


@pytest.mark.dev_insights
def test_ping():
    assert Client().get("/ping/").status_code == 200
"""


def fail(message):
    print(f"FAIL: {message}")
    sys.exit(1)


def check_import(expected_version, source_tree):
    import dev_insights

    location = os.path.abspath(dev_insights.__file__)
    if source_tree and location.startswith(os.path.abspath(source_tree) + os.sep):
        fail(f"dev_insights imported from the source tree ({location}), not the wheel")
    installed = version("django-dev-insights")
    if installed != expected_version:
        fail(f"installed version {installed} != expected {expected_version}")
    if dev_insights.__version__ != installed:
        fail(f"__version__ {dev_insights.__version__} != metadata {installed}")
    print(f"ok: dev_insights {installed} from {location}")


def check_entry_point():
    eps = entry_points()
    group = (
        eps.select(group="pytest11")
        if hasattr(eps, "select")
        else eps.get("pytest11", [])
    )
    found = {ep.name: ep.value for ep in group}
    if found.get("dev_insights") != "dev_insights.pytest_plugin":
        fail(f"pytest11 entry point 'dev_insights' missing or wrong: {found}")
    print("ok: pytest11 entry point dev_insights = dev_insights.pytest_plugin")


def run_pytest(project, *args):
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *args],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
    )


def check_plugin():
    with tempfile.TemporaryDirectory() as project:
        for name, body in (
            ("conftest.py", CONFTEST),
            ("urls.py", URLS),
            ("test_ping.py", TEST),
        ):
            with open(os.path.join(project, name), "w", encoding="utf-8") as f:
                f.write(textwrap.dedent(body))

        first = run_pytest(project)
        if first.returncode == 0 or "no baseline for view GET ping" not in first.stdout:
            fail(
                "without a baseline the marked test should fail with "
                "'no baseline for view GET ping':\n" + first.stdout + first.stderr
            )
        update = run_pytest(project, "--dev-insights-update-baseline")
        if update.returncode != 0:
            fail("update run failed:\n" + update.stdout + update.stderr)
        with open(
            os.path.join(project, "dev_insights_baseline.json"), encoding="utf-8"
        ) as f:
            views = json.load(f)["views"]
        if views != {"GET ping": {"queries": 0, "similar_queries": 0, "templates": 0}}:
            fail(f"unexpected baseline: {views}")
        again = run_pytest(project)
        if again.returncode != 0:
            fail("run with the baseline failed:\n" + again.stdout + again.stderr)
    print("ok: plugin loaded by entry point: no baseline -> fail, update -> pass")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--expected-version", required=True)
    parser.add_argument(
        "--source-tree", help="repository path; the import must not come from it"
    )
    args = parser.parse_args()
    check_import(args.expected_version, args.source_tree)
    check_entry_point()
    check_plugin()
    print("package OK")


if __name__ == "__main__":
    main()
