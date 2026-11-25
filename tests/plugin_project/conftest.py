"""Settings of the sample project used by tests/test_pytest_plugin.py.

DEBUG is False on purpose: that is what test runners do.
"""

import django
import pytest
from django.conf import settings

settings.configure(
    DEBUG=False,
    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
    INSTALLED_APPS=["django.contrib.contenttypes", "shop"],
    ROOT_URLCONF="urls",
    TEMPLATES=[
        {"BACKEND": "django.template.backends.django.DjangoTemplates", "APP_DIRS": True}
    ],
    ALLOWED_HOSTS=["testserver"],
    DEFAULT_AUTO_FIELD="django.db.models.AutoField",
    USE_TZ=True,
)
django.setup()


@pytest.fixture(autouse=True)
def data():
    from shop.models import create_and_seed

    create_and_seed()
