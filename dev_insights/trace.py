import traceback
import os
import sys

from django.conf import settings


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
        if _is_project_frame(filename):
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
        rel = os.path.relpath(filename)
        lines.append(f"{rel}:{lineno} in {func} -> {text}")
    return "\n".join(lines)
