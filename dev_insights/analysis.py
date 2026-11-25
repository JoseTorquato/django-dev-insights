"""Turn a list of executed queries into the DB metrics.

Shared by the middleware's DBCollector (which reads ``connection.queries``
under ``DEBUG=True``) and by the QueryRecorder (which works without DEBUG), so
both report exactly the same numbers.

Each entry is a dict with:

- ``sql``: the SQL as displayed (parameters interpolated when available);
- ``time_ms``: execution time in milliseconds;
- ``signature``: normalized signature (see ``dev_insights.signature``);
- ``origin`` (optional): ``{"file", "line", "func"}`` captured at execution;
- ``traceback`` (optional): formatted stack captured at execution.

Two different counts come out of it:

- **duplicates** (unchanged since 0.1): the very same SQL text, parameters
  included, executed more than once;
- **similar** (new in 0.4): the same signature executed more than once — the
  classic N+1, where each query differs only in its parameters. Every exact
  duplicate is also similar.
"""

from collections import OrderedDict


def _first(entries, key):
    for entry in entries:
        value = entry.get(key)
        if value:
            return value
    return None


def _group(entries, key):
    groups = OrderedDict()
    for entry in entries:
        groups.setdefault(entry[key], []).append(entry)
    return groups


def summarize(entries, slow_threshold_ms):
    total_time_ms = 0.0
    slow_queries = []
    for entry in entries:
        total_time_ms += entry["time_ms"]
        if entry["time_ms"] > slow_threshold_ms:
            item = {"sql": entry["sql"], "time_ms": round(entry["time_ms"], 2)}
            for extra in ("traceback", "origin"):
                if entry.get(extra):
                    item[extra] = entry[extra]
            slow_queries.append(item)

    duplicate_sqls = []
    for sql, group in _group(entries, "sql").items():
        if len(group) > 1:
            item = {"sql": sql, "count": len(group)}
            for extra in ("traceback", "origin"):
                value = _first(group, extra)
                if value:
                    item[extra] = value
            duplicate_sqls.append(item)

    similar_sqls = []
    for signature, group in _group(entries, "signature").items():
        if len(group) > 1:
            item = {
                "signature": signature,
                "count": len(group),
                "example": group[0]["sql"],
            }
            for extra in ("traceback", "origin"):
                value = _first(group, extra)
                if value:
                    item[extra] = value
            similar_sqls.append(item)
    # most repeated first: that is the one worth looking at
    similar_sqls.sort(key=lambda item: -item["count"])

    return {
        "query_count": len(entries),
        "total_db_time_ms": round(total_time_ms, 2),
        "slow_queries": slow_queries,
        "slow_query_count": len(slow_queries),
        "duplicate_query_count": sum(item["count"] for item in duplicate_sqls),
        "duplicate_sqls": duplicate_sqls,
        "similar_query_count": sum(item["count"] for item in similar_sqls),
        "similar_sqls": similar_sqls,
    }
