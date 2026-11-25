"""Shared Django settings for the test suite.

The older test modules call ``settings.configure`` themselves when nothing is
configured yet; configuring here first, with a superset of their settings,
lets the new tests use a real database (SQLite in memory) and a test app.
"""

import os
import sys

import django
from django.conf import settings

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

if not settings.configured:
    settings.configure(
        DEBUG=True,
        DEV_INSIGHTS_CONFIG={},
        ROOT_URLCONF="dev_insights.urls",
        DATABASES={
            "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}
        },
        INSTALLED_APPS=["django.contrib.contenttypes", "testapp"],
        TEMPLATES=[
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "APP_DIRS": True,
            }
        ],
        ALLOWED_HOSTS=["testserver"],
        USE_TZ=True,
        DEFAULT_AUTO_FIELD="django.db.models.AutoField",
    )
    django.setup()

# sample project run in a separate pytest process by test_pytest_plugin.py
collect_ignore = ["plugin_project"]
pytest_plugins = ["pytester"]
