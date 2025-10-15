from colorama import Fore, Style, init
from .config import THRESHOLDS, OUTPUT_FORMAT, DISPLAY_LIMIT, JSON_PRETTY, JSON_INDENT
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


def format_output(metrics):
    """Format the full output line, with colors.

    Returns either a colored text line or a JSON string depending on
    configuration.
    """
    # If JSON format requested, return a JSON string with truncated lists.
    if OUTPUT_FORMAT == "json":
        payload = dict(metrics)
        # truncate common lists inside db_metrics and connection_metrics
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

    # --- fallback: text/colored output (existing behaviour) ---
    db_metrics = metrics.get("db_metrics", {})
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

    # If any metric is critical, the whole line becomes red
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

    # Build the output string
    path_str = f"Path: {metrics['path']}"
    time_str = f"Total Time: {metrics['total_time_ms']}ms"

    output_str = f"{line_color}[DevInsights] {path_str} | {time_str}"

    if db_metrics:
        queries_str = f"DB Queries: {db_metrics.get('query_count', 0)}"
        db_time_str = f"DB Time: {db_metrics.get('total_db_time_ms', 0.0)}ms"
        output_str += f" | {queries_str} | {db_time_str}"

        duplicate_count = db_metrics.get("duplicate_query_count", 0)
        if duplicate_count > 0:
            # Highlight duplicate warning
            dup_color = get_color_for_metric("duplicate_query_count", duplicate_count)
            output_str += (
                f" | {dup_color}!! DUPLICATES: {duplicate_count} !!"
                f"{Style.RESET_ALL}{line_color}"
            )

    return output_str
