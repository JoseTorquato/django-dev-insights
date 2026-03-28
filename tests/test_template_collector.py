import os
import sys
import importlib
from django.conf import settings


def setup_module(module):
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    if not settings.configured:
        settings.configure(DEBUG=True, DEV_INSIGHTS_CONFIG={})


def reload_config(new_config=None):
    settings.DEV_INSIGHTS_CONFIG = new_config or {}
    import dev_insights.config
    import dev_insights.formatters

    importlib.reload(dev_insights.config)
    importlib.reload(dev_insights.formatters)


class TestTemplateCollector:
    def test_empty_when_no_templates(self):
        from dev_insights.collectors.template import TemplateCollector

        collector = TemplateCollector()
        collector.start_collect()
        collector.finish_collect()

        metrics = collector.get_metrics()
        assert metrics["template_count"] == 0
        assert metrics["total_render_time_ms"] == 0
        assert metrics["templates"] == []

    def test_records_template_renders(self):
        from dev_insights.collectors.template import (
            TemplateCollector,
            _record_render,
        )

        collector = TemplateCollector()
        collector.start_collect()

        # Simulate template renders
        _record_render("base.html", 5.5)
        _record_render("home.html", 12.3)
        _record_render("includes/nav.html", 1.2)

        collector.finish_collect()

        metrics = collector.get_metrics()
        assert metrics["template_count"] == 3
        assert metrics["total_render_time_ms"] == 19.0
        assert len(metrics["templates"]) == 3
        assert metrics["templates"][0]["name"] == "base.html"
        assert metrics["templates"][0]["time_ms"] == 5.5
        assert metrics["templates"][2]["name"] == "includes/nav.html"

    def test_start_clears_previous_data(self):
        from dev_insights.collectors.template import (
            TemplateCollector,
            _record_render,
        )

        collector = TemplateCollector()
        collector.start_collect()
        _record_render("old.html", 10.0)
        collector.finish_collect()
        assert collector.get_metrics()["template_count"] == 1

        # Start again — should clear
        collector.start_collect()
        collector.finish_collect()
        assert collector.get_metrics()["template_count"] == 0


class TestTemplatePatch:
    def test_patches_template_render(self):
        from dev_insights.template_trace import patch_template_render
        from django.template.base import Template

        Template._dev_insights_patched = False
        original = Template.render

        result = patch_template_render()
        assert result is True
        assert Template._dev_insights_patched is True
        assert Template.render is not original

        # Clean up
        Template.render = original
        Template._dev_insights_patched = False

    def test_does_not_patch_twice(self):
        from dev_insights.template_trace import patch_template_render
        from django.template.base import Template

        Template._dev_insights_patched = False

        patch_template_render()
        first = Template.render

        patch_template_render()
        second = Template.render

        assert first is second

        Template._dev_insights_patched = False


class TestTemplateTextOutput:
    def test_text_output_includes_templates(self):
        reload_config({"OUTPUT_FORMAT": "text"})
        from dev_insights.formatters import format_output

        metrics = {
            "path": "/test/",
            "total_time_ms": 50.0,
            "template_metrics": {
                "template_count": 2,
                "total_render_time_ms": 15.0,
                "templates": [
                    {"name": "base.html", "time_ms": 10.0},
                    {"name": "home.html", "time_ms": 5.0},
                ],
            },
        }

        output = format_output(metrics)
        assert "[Templates]" in output
        assert "2 rendered" in output
        assert "base.html" in output
        assert "home.html" in output

    def test_json_output_includes_templates(self):
        import json

        reload_config({"OUTPUT_FORMAT": "json", "JSON_PRETTY": False})
        from dev_insights.formatters import format_output

        metrics = {
            "path": "/test/",
            "total_time_ms": 50.0,
            "template_metrics": {
                "template_count": 1,
                "total_render_time_ms": 8.0,
                "templates": [{"name": "index.html", "time_ms": 8.0}],
            },
        }

        output = format_output(metrics)
        data = json.loads(output)
        assert data["template_metrics"]["template_count"] == 1
        assert data["template_metrics"]["templates"][0]["name"] == "index.html"
