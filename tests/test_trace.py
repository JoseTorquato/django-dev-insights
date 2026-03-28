import os
import sys
from django.conf import settings


def setup_module(module):
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    if not settings.configured:
        settings.configure(DEBUG=True, DEV_INSIGHTS_CONFIG={})


class TestCaptureTraceback:
    def test_returns_list_of_tuples(self):
        from dev_insights.trace import capture_traceback

        frames = capture_traceback(depth=3)
        assert isinstance(frames, list)
        assert len(frames) <= 3
        for frame in frames:
            assert len(frame) == 4  # (filename, lineno, func, text)

    def test_respects_depth_limit(self):
        from dev_insights.trace import capture_traceback

        frames_short = capture_traceback(depth=1)
        frames_long = capture_traceback(depth=10)
        assert len(frames_short) <= 1
        assert len(frames_long) <= 10

    def test_returns_nonempty_frames(self):
        from dev_insights.trace import capture_traceback

        frames = capture_traceback(depth=10)
        # Should always return at least one frame (project or fallback)
        assert len(frames) >= 1
        # Each frame should have a filename
        for f in frames:
            assert isinstance(f[0], str)
            assert len(f[0]) > 0


class TestFormatTraceback:
    def test_formats_frames_as_string(self):
        from dev_insights.trace import format_traceback

        frames = [
            ("/path/to/file.py", 42, "my_func", "x = 1"),
            ("/path/to/other.py", 10, "other_func", "y = 2"),
        ]
        result = format_traceback(frames)
        assert isinstance(result, str)
        assert "my_func" in result
        assert "other_func" in result
        assert "42" in result

    def test_empty_frames(self):
        from dev_insights.trace import format_traceback

        result = format_traceback([])
        assert result == ""


class TestIsProjectFrame:
    def test_venv_frame_is_not_project(self):
        from dev_insights.trace import _is_project_frame

        # A file inside sys.prefix should be external
        venv_file = os.path.join(sys.prefix, "lib", "something.py")
        assert _is_project_frame(venv_file) is False

    def test_project_frame_detected(self):
        from dev_insights.trace import _is_project_frame

        # This test file itself should be a project frame
        assert _is_project_frame(__file__) is True
