from django.conf import settings

# Pega a configuração do usuário do settings.py, ou um dicionário vazio se não existir.
USER_CONFIG = getattr(settings, 'DEV_INSIGHTS_CONFIG', {})

# --- Padrões da Ferramenta ---
DEFAULTS = {
    'THRESHOLDS': {
        'total_time_ms': {'warn': 1000, 'crit': 3000},
        'query_count': {'warn': 20, 'crit': 50},
        'duplicate_query_count': {'warn': 5, 'crit': 10},
    },
    'SLOW_QUERY_THRESHOLD_MS': 100,
}

# --- Função para obter a configuração final ---
def get_config(key):
    """
    Retorna a configuração do usuário para uma chave, ou o padrão se não for fornecida.
    """
    if key in USER_CONFIG:
        # Se o usuário definiu a chave, fazemos um merge com o padrão
        # para garantir que todas as sub-chaves existam.
        if isinstance(USER_CONFIG[key], dict):
            default_value = DEFAULTS.get(key, {}).copy()
            default_value.update(USER_CONFIG[key])
            return default_value
        return USER_CONFIG[key]
    
    return DEFAULTS.get(key)

# --- Exporta as configurações finais que serão usadas pela lib ---
THRESHOLDS = get_config('THRESHOLDS')
SLOW_QUERY_THRESHOLD_MS = get_config('SLOW_QUERY_THRESHOLD_MS')
