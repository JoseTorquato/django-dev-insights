"""In-memory ring buffer that stores the last N request metrics for the panel."""

import threading
from collections import deque

from .config import PANEL_HISTORY_SIZE

_lock = threading.Lock()
_history = deque(maxlen=PANEL_HISTORY_SIZE or 50)


def record_metrics(metrics):
    """Append a metrics dict to the ring buffer (thread-safe)."""
    with _lock:
        _history.append(metrics)


def get_history():
    """Return a list of recent metrics (newest first)."""
    with _lock:
        return list(reversed(_history))


def clear_history():
    """Clear stored metrics."""
    with _lock:
        _history.clear()
