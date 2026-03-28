from colorama import Fore, Style, init
from .config import (
    THRESHOLDS,
    OUTPUT_FORMAT,
    DISPLAY_LIMIT,
    JSON_PRETTY,
    JSON_INDENT,
    SLOW_QUERY_THRESHOLD_MS,
)
import json

init(autoreset=True)


def _truncate_list(items):
    """Truncate a list to DISPLAY_LIMIT and return (truncated_list, omitted_count)."""
    if items is None:
        return [], 0
    if not isinstance(items, (list, tuple)):
        return items, 0
    limit = DISPLAY_LIMIT or len(items)
    if limit <= 0:
        return [], len(items)
    truncated = list(items)[:limit]
    omitted = max(0, len(items) - len(truncated))
    return truncated, omitted


def get_color_for_metric(metric_name, value):
    """Return the appropriate color based on a metric's value."""
    if metric_name not in THRESHOLDS:
        return Fore.WHITE

    if value >= THRESHOLDS[metric_name]["crit"]:
        return Fore.RED
    if value >= THRESHOLDS[metric_name]["warn"]:
        return Fore.YELLOW

    return Fore.GREEN


def _format_json(metrics):
    """Format metrics as a JSON string with truncated lists."""
    payload = dict(metrics)
    db_metrics = payload.get("db_metrics", {}) or {}
    if "duplicate_sqls" in db_metrics:
        truncated, omitted = _truncate_list(db_metrics.get("duplicate_sqls"))
        db_metrics["duplicate_sqls"] = truncated
        if omitted:
            db_metrics["duplicate_sqls_omitted"] = omitted
    if "slow_queries" in db_metrics:
        truncated, omitted = _truncate_list(db_metrics.get("slow_queries"))
        db_metrics["slow_queries"] = truncated
        if omitted:
            db_metrics["slow_queries_omitted"] = omitted
    payload["db_metrics"] = db_metrics

    conn_metrics = payload.get("connection_metrics", {}) or {}
    if "setup_queries" in conn_metrics:
        truncated_setup = {}
        total_omitted = 0
        for alias, lst in (conn_metrics.get("setup_queries") or {}).items():
            t, omitted = _truncate_list(lst)
            truncated_setup[alias] = t
            total_omitted += omitted
        conn_metrics["setup_queries"] = truncated_setup
        if total_omitted:
            conn_metrics["setup_queries_omitted"] = total_omitted
    payload["connection_metrics"] = conn_metrics

    if JSON_PRETTY:
        return json.dumps(payload, ensure_ascii=False, indent=JSON_INDENT)
    return json.dumps(payload, ensure_ascii=False)


def _format_text(metrics):
    """Format metrics as a colored text string with all detail sections."""
    db_metrics = metrics.get("db_metrics", {}) or {}
    conn_metrics = metrics.get("connection_metrics", {}) or {}

    # Decide the overall line color (the most severe issue color)
    line_color = Fore.GREEN
    if get_color_for_metric("total_time_ms", metrics["total_time_ms"]) != Fore.GREEN:
        line_color = Fore.YELLOW
    if (
        get_color_for_metric("query_count", db_metrics.get("query_count", 0))
        != Fore.GREEN
    ):
        line_color = Fore.YELLOW
    if (
        get_color_for_metric(
            "duplicate_query_count", db_metrics.get("duplicate_query_count", 0)
        )
        != Fore.GREEN
    ):
        line_color = Fore.YELLOW

    if (
        get_color_for_metric("total_time_ms", metrics["total_time_ms"]) == Fore.RED
        or get_color_for_metric("query_count", db_metrics.get("query_count", 0))
        == Fore.RED
        or get_color_for_metric(
            "duplicate_query_count", db_metrics.get("duplicate_query_count", 0)
        )
        == Fore.RED
    ):
        line_color = Fore.RED

    # Build the summary line
    path_str = f"Path: {metrics['path']}"
    time_str = f"Total Time: {metrics['total_time_ms']}ms"
    parts = [f"{line_color}[DevInsights] {path_str} | {time_str}"]

    if db_metrics:
        queries_str = f"DB Queries: {db_metrics.get('query_count', 0)}"
        db_time_str = f"DB Time: {db_metrics.get('total_db_time_ms', 0.0)}ms"
        parts.append(f"{queries_str} | {db_time_str}")

        duplicate_count = db_metrics.get("duplicate_query_count", 0)
        if duplicate_count > 0:
            dup_color = get_color_for_metric("duplicate_query_count", duplicate_count)
            parts.append(
                f"{dup_color}!! DUPLICATES: {duplicate_count} !!"
                f"{Style.RESET_ALL}{line_color}"
            )

    lines = [" | ".join(parts)]

    # Duplicate details
    if db_metrics.get("duplicate_query_count", 0) > 0:
        lines.append(f"{Fore.YELLOW}    [Duplicated SQLs]:{Style.RESET_ALL}")
        for item in db_metrics.get("duplicate_sqls", []):
            if isinstance(item, dict):
                sql = item.get("sql")
                count = item.get("count")
                lines.append(f"{Fore.YELLOW}      -> ({count}x) {sql}{Style.RESET_ALL}")
                tb = item.get("traceback")
                if tb:
                    lines.append(
                        f"{Fore.YELLOW}         Traceback:\n{tb}{Style.RESET_ALL}"
                    )
            else:
                lines.append(f"{Fore.YELLOW}      -> {item}{Style.RESET_ALL}")

    # Slow queries
    if db_metrics.get("slow_query_count", 0) > 0:
        msg = "[Slow Queries (> {}ms)]:".format(SLOW_QUERY_THRESHOLD_MS)
        lines.append(f"{Fore.RED}    {msg}{Style.RESET_ALL}")
        for slow_query in db_metrics.get("slow_queries", []):
            sql = slow_query.get("sql")
            time_ms = slow_query.get("time_ms")
            lines.append(f"{Fore.RED}      -> [{time_ms}ms] {sql}{Style.RESET_ALL}")
            tb = slow_query.get("traceback")
            if tb:
                lines.append(f"{Fore.RED}         Traceback:\n{tb}{Style.RESET_ALL}")

    # Connection metrics
    if conn_metrics:
        setup_count = conn_metrics.get("total_setup_query_count", 0)
        if setup_count > 0:
            lines.append(
                f"{Fore.MAGENTA}    [Connection Setup Queries]:{Style.RESET_ALL}"
            )
            for alias, queries in conn_metrics.get("setup_queries", {}).items():
                if queries:
                    msg = f"{alias}: {len(queries)} setup queries"
                    lines.append(f"{Fore.MAGENTA}      -> {msg}{Style.RESET_ALL}")
                    for q in queries:
                        if isinstance(q, dict):
                            sql_msg = q.get("sql")
                            lines.append(
                                f"{Fore.MAGENTA}       - {sql_msg}{Style.RESET_ALL}"
                            )
                            tb = q.get("traceback")
                            if tb:
                                tb_msg = f"Traceback:\n{tb}"
                                lines.append(
                                    f"{Fore.MAGENTA}      {tb_msg}{Style.RESET_ALL}"
                                )
                        else:
                            lines.append(
                                f"{Fore.MAGENTA}         - {q}{Style.RESET_ALL}"
                            )

        reopens = conn_metrics.get("connection_reopens", [])
        if reopens:
            lines.append(
                f"{Fore.MAGENTA}    [Connection Reopens Detected]: "
                f"{', '.join(reopens)}{Style.RESET_ALL}"
            )

    # Template metrics
    tpl_metrics = metrics.get("template_metrics", {}) or {}
    if tpl_metrics.get("template_count", 0) > 0:
        count = tpl_metrics["template_count"]
        total_ms = tpl_metrics["total_render_time_ms"]
        lines.append(
            f"{Fore.CYAN}    [Templates]: {count} rendered "
            f"in {total_ms}ms{Style.RESET_ALL}"
        )
        for tpl in tpl_metrics.get("templates", []):
            name = tpl.get("name", "<unknown>")
            t_ms = tpl.get("time_ms", 0)
            lines.append(f"{Fore.CYAN}      -> [{t_ms}ms] {name}{Style.RESET_ALL}")

    return "\n".join(lines)


def format_output(metrics):
    """Format the full output, with colors or JSON depending on configuration.

    Returns a complete string ready for output (print or logger).
    """
    if OUTPUT_FORMAT == "json":
        return _format_json(metrics)
    return _format_text(metrics)
