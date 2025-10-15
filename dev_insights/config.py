from django.conf import settings

# Grab user's configuration from settings.py or an empty dict if missing.
USER_CONFIG = getattr(settings, "DEV_INSIGHTS_CONFIG", {})

# --- Tool defaults ---
DEFAULTS = {
    "THRESHOLDS": {
        "total_time_ms": {"warn": 1000, "crit": 3000},
        "query_count": {"warn": 20, "crit": 50},
        "duplicate_query_count": {"warn": 5, "crit": 10},
    },
    "SLOW_QUERY_THRESHOLD_MS": 100,
    # Traceback capture (v0.5.0)
    "ENABLE_TRACEBACKS": False,
    "TRACEBACK_DEPTH": 5,
    # Collectors enabled by default. Use e.g. ['db', 'connection'] to enable.
    "ENABLED_COLLECTORS": ["db", "connection"],
    # Output format and display limits
    # OUTPUT_FORMAT: 'text' (human, colored) or 'json' (machine-readable)
    "OUTPUT_FORMAT": "text",
    # DISPLAY_LIMIT: max number of items to show per list (duplicates, slow)
    "DISPLAY_LIMIT": 100,
    # JSON pretty-printing options
    "JSON_PRETTY": True,
    "JSON_INDENT": 2,
    # Logging integration: if OUTPUT_LOGGER_NAME is set, JSON output will be
    # sent to that logger. OUTPUT_LOG_FILE is an optional file path to attach
    # to the logger if it has no handlers.
    "OUTPUT_LOGGER_NAME": None,
    "OUTPUT_LOG_FILE": None,
}


# --- Função para obter a configuração final ---
def get_config(key):
    """Return the user configuration value for a key, or the default."""
    if key in USER_CONFIG:
        # If the user defined the key and it's a dict, merge with the default
        # to ensure all sub-keys exist.
        if isinstance(USER_CONFIG[key], dict):
            default_value = DEFAULTS.get(key, {}).copy()
            default_value.update(USER_CONFIG[key])
            return default_value
        return USER_CONFIG[key]

    return DEFAULTS.get(key)


# --- Exporta as configurações finais que serão usadas pela lib ---
THRESHOLDS = get_config("THRESHOLDS")
SLOW_QUERY_THRESHOLD_MS = get_config("SLOW_QUERY_THRESHOLD_MS")
ENABLE_TRACEBACKS = get_config("ENABLE_TRACEBACKS")
TRACEBACK_DEPTH = get_config("TRACEBACK_DEPTH")
ENABLED_COLLECTORS = get_config("ENABLED_COLLECTORS")
OUTPUT_FORMAT = get_config("OUTPUT_FORMAT")
DISPLAY_LIMIT = get_config("DISPLAY_LIMIT")
JSON_PRETTY = get_config("JSON_PRETTY")
JSON_INDENT = get_config("JSON_INDENT")
OUTPUT_LOGGER_NAME = get_config("OUTPUT_LOGGER_NAME")
OUTPUT_LOG_FILE = get_config("OUTPUT_LOG_FILE")
