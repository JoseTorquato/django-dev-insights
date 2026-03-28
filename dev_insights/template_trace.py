"""Runtime monkeypatch to capture template render times.

Patches Django's Template.render to record each render call with its
duration. The data is stored in a thread-local accessed by
TemplateCollector. Only active when DEBUG is True and the 'template'
collector is enabled.
"""

import functools
import time


def patch_template_render():
    try:
        from django.template.base import Template
    except Exception:
        return False

    if getattr(Template, "_dev_insights_patched", False):
        return True

    original_render = Template.render

    @functools.wraps(original_render)
    def wrapped_render(self, context):
        from dev_insights.collectors.template import _record_render

        start = time.perf_counter()
        result = original_render(self, context)
        elapsed_ms = (time.perf_counter() - start) * 1000

        name = getattr(self, "origin", None)
        if name is not None:
            name = getattr(name, "name", None) or str(name)
        if not name:
            # Fallback: use first 80 chars of template source
            source = getattr(self, "source", "") or ""
            name = (source[:80] + "...") if len(source) > 80 else source
            name = name or "<inline>"

        _record_render(name, elapsed_ms)
        return result

    try:
        Template.render = wrapped_render
        Template._dev_insights_patched = True
        return True
    except Exception:
        return False
