import functools
import traceback
import os
import sys

import django
from django.conf import settings

# Frames from these directories are never the origin of a query: they are
# Django itself and this library (its middleware, recorder and patches).
_INTERNAL_DIRS = tuple(
    os.path.normcase(os.path.abspath(d)) + os.sep
    for d in (os.path.dirname(django.__file__), os.path.dirname(__file__))
)
_THIRD_PARTY_MARKERS = (
    os.sep + "site-packages" + os.sep,
    os.sep + "dist-packages" + os.sep,
)


def _is_project_frame(frame_filename):
    """Decide whether a frame belongs to the user's project.

    Rules (in order):
    - If SETTINGS.BASE_DIR is set and the frame is inside it -> True
    - If the frame is outside the virtualenv (sys.prefix / base_prefix) -> True
    - Otherwise treat as external (False).

    This heuristic avoids treating stdlib/venv files (wsgiref, Django internals)
    as project frames.
    """
    try:
        base_dir = getattr(settings, "BASE_DIR", None)
        if base_dir:
            try:
                if os.path.commonpath(
                    [os.path.abspath(frame_filename), os.path.abspath(base_dir)]
                ) == os.path.abspath(base_dir):
                    return True
            except Exception:
                pass
    except Exception:
        base_dir = None

    # Exclude paths that belong to the Python/virtualenv installation
    try:
        prefixes = {
            os.path.abspath(sys.prefix),
            os.path.abspath(getattr(sys, "base_prefix", sys.prefix)),
        }
        abs_path = os.path.abspath(frame_filename)
        for p in prefixes:
            if abs_path.startswith(p):
                return False
    except Exception:
        pass

    # If the frame is not under the venv prefixes, consider it part of the
    # project.
    return True


@functools.lru_cache(maxsize=4096)
def _is_origin_candidate(frame_filename):
    """A frame that can be shown as "where the query was born".

    Excludes Django, this library and anything installed as a package (even a
    virtualenv inside BASE_DIR), then applies the project heuristic above.
    """
    if not frame_filename or frame_filename.startswith("<"):
        return False
    path = os.path.normcase(os.path.abspath(frame_filename))
    if path.startswith(_INTERNAL_DIRS):
        return False
    if any(marker in path for marker in _THIRD_PARTY_MARKERS):
        return False
    return _is_project_frame(frame_filename)


def _display_path(filename):
    try:
        return os.path.relpath(filename)
    except ValueError:  # other drive on Windows
        return filename


def capture_origin():
    """Return the innermost project frame of the current stack, as
    ``{"file", "line", "func"}``, or None.

    Walks the live frames instead of formatting the whole stack, so it is
    cheap enough to call when a query is executed.
    """
    frame = sys._getframe(1)
    while frame is not None:
        filename = frame.f_code.co_filename
        if _is_origin_candidate(filename):
            return {
                "file": _display_path(filename),
                "line": frame.f_lineno,
                "func": frame.f_code.co_name,
            }
        frame = frame.f_back
    return None


def format_origin(origin):
    """``path/to/file.py:12 in func``, or an empty string."""
    if not origin:
        return ""
    return f"{origin['file']}:{origin['line']} in {origin['func']}"


def capture_traceback(depth=5):
    """Capture and return the last `depth` frames as a list of
    (file, line, func, text). Filter frames that likely do not belong to the
    project.
    """
    stack = traceback.extract_stack()[:-2]  # remove internal frames
    # Reverse to show frames from the call origin upwards
    stack = list(reversed(stack))

    filtered = []
    for frame in stack:
        filename = frame.filename
        if _is_origin_candidate(filename):
            filtered.append(
                (frame.filename, frame.lineno, frame.name, (frame.line or "").strip())
            )
        if len(filtered) >= depth:
            break

    # Fallback: if no project frames found, return the first `depth` frames
    if not filtered:
        for frame in stack[:depth]:
            filtered.append(
                (frame.filename, frame.lineno, frame.name, (frame.line or "").strip())
            )

    return filtered


def format_traceback(frames):
    """Format a list of frames into a readable multi-line string."""
    lines = []
    for filename, lineno, func, text in frames:
        rel = _display_path(filename)
        lines.append(f"{rel}:{lineno} in {func} -> {text}")
    return "\n".join(lines)
