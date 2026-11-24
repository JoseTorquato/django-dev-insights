# Contributing

Thanks for helping. Please open an issue or a pull request with a clear description and tests.

## Setup

```bash
python -m venv .venv && . .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install Django colorama pytest pytest-cov black flake8
pip install -e .                                  # registers the pytest plugin entry point
```

Supported: Python 3.10+ and Django 4.2–6.1 (see the CI matrix in `.github/workflows/ci.yml`).

## Running the tests

```bash
python -m pytest -q
python -m black --check .
python -m flake8 dev_insights tests .github
```

- The suite configures Django itself (`tests/conftest.py`, SQLite in memory). `pyproject.toml` passes `-p no:django`, so **having pytest-django installed does not break it**.
- `tests/test_pytest_plugin.py` runs the sample project in `tests/plugin_project` in a separate pytest process (`pytester`). The tests that need **pytest-django** (the guard's main use case) or **pytest-xdist** are skipped when those are not installed. To run them too, as the CI does in one job:

  ```bash
  pip install pytest-django pytest-xdist
  python -m pytest -q
  ```

- `tests/plugin_project` is not collected by the main run (`collect_ignore` in `tests/conftest.py`); it only runs inside those subprocesses.

## Pull requests

- One topic per pull request, with a test for each change.
- Code, docs and commit messages in English.
- Add a line to `CHANGELOG.md` under `[Unreleased]`.
