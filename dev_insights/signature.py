"""Normalized SQL signature ("fingerprint").

Two queries that differ only in their literal values or bound parameters get
the same signature. That is what turns the classic N+1 (the same query run
once per row, each time with a different id) into something countable:

    SELECT ... WHERE "book"."author_id" = 1
    SELECT ... WHERE "book"."author_id" = 2     ->  ... WHERE "book"."author_id" = ?

Rules, in order:

- string literals ('...', with '' escapes) become ``?``;
- driver placeholders (``%s``, ``%(name)s``, ``?``) become ``?``;
- numeric literals become ``?`` (digits inside identifiers such as ``t1`` or
  ``"col2"`` are kept);
- ``IN (?, ?, ...)`` of any size collapses to ``IN (...)``;
- repeated ``VALUES`` tuples (bulk inserts) collapse to ``VALUES (...)``;
- whitespace is collapsed.

The signature is for grouping, not for execution: it is never sent to the
database.
"""

import re

_STRING = re.compile(r"'(?:[^']|'')*'")
_PLACEHOLDER = re.compile(r"%\(\w+\)s|%s|\?")
# a number not glued to an identifier, a quoted name or a decimal point
_NUMBER = re.compile(r"(?<![\w.\"`$])-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?(?![\w\"`])")
_IN_LIST = re.compile(r"\bIN\s*\(\s*\?(?:\s*,\s*\?)*\s*\)", re.IGNORECASE)
_TUPLE = r"\(\s*\?(?:\s*,\s*\?)*\s*\)"
_VALUES = re.compile(r"\bVALUES\s*" + _TUPLE + r"(?:\s*,\s*" + _TUPLE + r")*", re.I)
_SPACES = re.compile(r"\s+")


def sql_signature(sql):
    """Return the normalized signature of an SQL string."""
    if not sql:
        return ""
    text = _STRING.sub("?", str(sql))
    text = _PLACEHOLDER.sub("?", text)
    text = _NUMBER.sub("?", text)
    text = _IN_LIST.sub("IN (...)", text)
    text = _VALUES.sub("VALUES (...)", text)
    return _SPACES.sub(" ", text).strip()
