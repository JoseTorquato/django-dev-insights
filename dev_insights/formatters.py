from colorama import Fore, Style, init
from .config import THRESHOLDS

init(autoreset=True)

def get_color_for_metric(metric_name, value):
    """Retorna a cor apropriada com base no valor de uma métrica."""
    if metric_name not in THRESHOLDS:
        return Fore.WHITE

    if value >= THRESHOLDS[metric_name]['crit']:
        return Fore.RED
    if value >= THRESHOLDS[metric_name]['warn']:
        return Fore.YELLOW
    
    return Fore.GREEN

def format_output(metrics):
    """Formata a linha de saída completa com cores."""
    db_metrics = metrics.get('db_metrics', {})
    
    # Decide a cor geral da linha (a cor do problema mais grave)
    line_color = Fore.GREEN
    if get_color_for_metric('total_time_ms', metrics['total_time_ms']) != Fore.GREEN:
        line_color = Fore.YELLOW
    if get_color_for_metric('query_count', db_metrics.get('query_count', 0)) != Fore.GREEN:
        line_color = Fore.YELLOW
    if get_color_for_metric('duplicate_query_count', db_metrics.get('duplicate_query_count', 0)) != Fore.GREEN:
        line_color = Fore.YELLOW
    
    # Se qualquer métrica for crítica, a linha inteira fica vermelha
    if get_color_for_metric('total_time_ms', metrics['total_time_ms']) == Fore.RED or \
       get_color_for_metric('query_count', db_metrics.get('query_count', 0)) == Fore.RED or \
       get_color_for_metric('duplicate_query_count', db_metrics.get('duplicate_query_count', 0)) == Fore.RED:
        line_color = Fore.RED

    # Monta a string de saída
    path_str = f"Path: {metrics['path']}"
    time_str = f"Tempo Total: {metrics['total_time_ms']}ms"
    
    output_str = f"{line_color}[DevInsights] {path_str} | {time_str}"

    if db_metrics:
        queries_str = f"DB Queries: {db_metrics.get('query_count', 0)}"
        db_time_str = f"DB Tempo: {db_metrics.get('total_db_time_ms', 0.0)}ms"
        output_str += f" | {queries_str} | {db_time_str}"
        
        duplicate_count = db_metrics.get('duplicate_query_count', 0)
        if duplicate_count > 0:
            # Destaca o aviso de duplicatas
            dup_color = get_color_for_metric('duplicate_query_count', duplicate_count)
            output_str += f" | {dup_color}!! DUPLICATAS: {duplicate_count} !!{Style.RESET_ALL}{line_color}"

    return output_str
