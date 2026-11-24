"""A project-level cache, like many real projects have."""

from .models import Author

_cache = {}


def author_count():
    if "n" not in _cache:
        _cache["n"] = Author.objects.count()
    return _cache["n"]


def clear():
    _cache.clear()
