import os

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden

from .store import get_history

_PANEL_TEMPLATE = os.path.join(os.path.dirname(__file__), "panel.html")


def panel_view(request):
    """Render the DevInsights HTML panel showing recent request metrics."""
    if not settings.DEBUG:
        return HttpResponseForbidden(
            "DevInsights panel is only available in DEBUG mode."
        )

    history = get_history()

    rows_html = ""
    for m in history:
        path = m.get("path", "")
        total = m.get("total_time_ms", 0)
        db = m.get("db_metrics", {}) or {}
        conn = m.get("connection_metrics", {}) or {}
        tpl = m.get("template_metrics", {}) or {}

        query_count = db.get("query_count", 0)
        db_time = db.get("total_db_time_ms", 0)
        dup_count = db.get("duplicate_query_count", 0)
        slow_count = db.get("slow_query_count", 0)
        tpl_count = tpl.get("template_count", 0)
        tpl_time = tpl.get("total_render_time_ms", 0)
        setup_count = conn.get("total_setup_query_count", 0)

        # Severity class
        if total >= 3000 or query_count >= 50 or dup_count >= 10:
            severity = "crit"
        elif total >= 1000 or query_count >= 20 or dup_count >= 5:
            severity = "warn"
        else:
            severity = "ok"

        # Duplicate details
        dup_details = ""
        for d in db.get("duplicate_sqls", []):
            if isinstance(d, dict):
                sql = _escape(d.get("sql", ""))
                cnt = d.get("count", 0)
                dup_details += f'<div class="detail dup">({cnt}x) {sql}</div>'

        # Slow query details
        slow_details = ""
        for s in db.get("slow_queries", []):
            if isinstance(s, dict):
                sql = _escape(s.get("sql", ""))
                t = s.get("time_ms", 0)
                slow_details += f'<div class="detail slow">[{t}ms] {sql}</div>'

        # Template details
        tpl_details = ""
        for t in tpl.get("templates", []):
            if isinstance(t, dict):
                name = _escape(t.get("name", ""))
                t_ms = t.get("time_ms", 0)
                tpl_details += f'<div class="detail tpl">[{t_ms}ms] {name}</div>'

        details = dup_details + slow_details + tpl_details
        has_details = " has-details" if details else ""

        rows_html += f"""<tr class="{severity}{has_details}">
<td class="path">{_escape(path)}</td>
<td>{total}ms</td>
<td>{query_count}</td>
<td>{db_time}ms</td>
<td>{dup_count}</td>
<td>{slow_count}</td>
<td>{tpl_count}</td>
<td>{tpl_time}ms</td>
<td>{setup_count}</td>
</tr>"""
        if details:
            rows_html += f"""<tr class="details-row {severity}">
<td colspan="9">{details}</td></tr>"""

    with open(_PANEL_TEMPLATE, "r", encoding="utf-8") as f:
        html = f.read()

    html = html.replace("{{ ROWS }}", rows_html)
    html = html.replace("{{ COUNT }}", str(len(history)))
    return HttpResponse(html)


def _escape(s):
    """Minimal HTML escaping."""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
