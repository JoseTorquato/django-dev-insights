"""Dev Insights package.

``__version__`` comes from the installed package metadata, so the version is
written in one place only (``pyproject.toml``). It is resolved on first access:
the pytest plugin imports this package in every pytest run, and should not pay
for a metadata lookup it does not need.
"""


def __getattr__(name):
    if name == "__version__":
        from importlib.metadata import PackageNotFoundError, version

        try:
            return version("django-dev-insights")
        except PackageNotFoundError:  # running from a source tree, not installed
            return "0+unknown"
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
