import os
import sys
from django.conf import settings


def setup_module(module):
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    if not settings.configured:
        settings.configure(DEBUG=True, DEV_INSIGHTS_CONFIG={})


class TestPatchCursorDebugWrapper:
    def test_patches_execute(self):
        from dev_insights.sql_trace import patch_cursor_debug_wrapper
        from django.db.backends.utils import CursorDebugWrapper

        # Reset patch state
        CursorDebugWrapper._dev_insights_patched = False
        original_execute = CursorDebugWrapper.execute

        result = patch_cursor_debug_wrapper()
        assert result is True
        assert CursorDebugWrapper._dev_insights_patched is True
        # execute should now be wrapped
        assert CursorDebugWrapper.execute is not original_execute

        # Clean up
        CursorDebugWrapper.execute = original_execute
        CursorDebugWrapper._dev_insights_patched = False

    def test_does_not_patch_twice(self):
        from dev_insights.sql_trace import patch_cursor_debug_wrapper
        from django.db.backends.utils import CursorDebugWrapper

        CursorDebugWrapper._dev_insights_patched = False

        patch_cursor_debug_wrapper()
        first_execute = CursorDebugWrapper.execute

        patch_cursor_debug_wrapper()
        second_execute = CursorDebugWrapper.execute

        # Should be the same function (not double-wrapped)
        assert first_execute is second_execute

        # Clean up
        CursorDebugWrapper._dev_insights_patched = False
