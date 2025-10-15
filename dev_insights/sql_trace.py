"""Runtime monkeypatch to attach tracebacks to debug SQL entries.

This patches Django's CursorDebugWrapper.execute and executemany to capture a
stack trace at the moment the SQL is executed and attach it to the last entry
in `connection.queries` as the 'traceback' key. The patch is safe (wrapped in
try/except) and only used when DEBUG + ENABLE_TRACEBACKS are enabled.
"""
import traceback
import functools
import sys

from django.db import connection

from .trace import capture_traceback, format_traceback


def patch_cursor_debug_wrapper():
    try:
        # CursorDebugWrapper is available in Django's db.backends.utils
        from django.db.backends.utils import CursorDebugWrapper
    except Exception:
        return False

    # Only patch once
    if getattr(CursorDebugWrapper, '_dev_insights_patched', False):
        return True

    def _wrap_execute(orig):
        @functools.wraps(orig)
        def wrapper(self, sql, params=None):
            # capture stack at moment of execution
            try:
                frames = capture_traceback()
                tb = format_traceback(frames)
            except Exception:
                tb = None

            result = orig(self, sql, params)

            # Attach traceback to last connection.queries entry if present
            try:
                if connection and hasattr(connection, 'queries') and connection.queries:
                    last = connection.queries[-1]
                    # Only attach if it seems to correspond to this SQL
                    if isinstance(last, dict) and 'sql' in last:
                        last_sql = (last.get('sql') or '').strip()
                        if last_sql and last_sql == (sql or '').strip():
                            if tb:
                                last['traceback'] = tb
                        else:
                            # best-effort: still attach if traceback missing
                            if tb and 'traceback' not in last:
                                last['traceback'] = tb
            except Exception:
                pass

            return result

        return wrapper

    try:
        # Patch execute and executemany
        CursorDebugWrapper.execute = _wrap_execute(CursorDebugWrapper.execute)
        try:
            CursorDebugWrapper.executemany = _wrap_execute(CursorDebugWrapper.executemany)
        except Exception:
            # not all wrappers implement executemany the same way
            pass

        CursorDebugWrapper._dev_insights_patched = True
        return True
    except Exception:
        return False
