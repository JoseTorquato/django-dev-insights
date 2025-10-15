import traceback
import inspect
import os
import sys

from django.conf import settings


def _is_project_frame(frame_filename):
    """Decide se um frame pertence ao projeto do usuário.

    Regras (na ordem):
    - Se SETTINGS.BASE_DIR estiver definido e o frame estiver dentro dele -> True
    - Se o frame estiver fora do ambiente virtual (sys.prefix / sys.base_prefix) -> True
    - Caso contrário, considera external (False).

    Essa heurística evita tratar arquivos da stdlib/venv (como wsgiref,
    django internals) como "project frames".
    """
    try:
        base_dir = getattr(settings, 'BASE_DIR', None)
        if base_dir:
            try:
                if os.path.commonpath([os.path.abspath(frame_filename), os.path.abspath(base_dir)]) == os.path.abspath(base_dir):
                    return True
            except Exception:
                pass
    except Exception:
        base_dir = None

    # Exclui caminhos que pertencem ao ambiente Python/virtualenv
    try:
        prefixes = {os.path.abspath(sys.prefix), os.path.abspath(getattr(sys, 'base_prefix', sys.prefix))}
        abs_path = os.path.abspath(frame_filename)
        for p in prefixes:
            if abs_path.startswith(p):
                return False
    except Exception:
        pass

    # Se o frame não estiver dentro do venv prefix, considera como pertencente ao projeto
    return True


def capture_traceback(depth=5):
    """Captura e retorna os últimos `depth` frames como lista de (file, line, func, text).
    Filtra frames que provavelmente não pertencem ao projeto.
    """
    stack = traceback.extract_stack()[:-2]  # remove frames internos (capture_traceback e caller)
    # Inverte para mostrar do mais próximo à origem para o mais distante
    stack = list(reversed(stack))

    filtered = []
    for frame in stack:
        filename = frame.filename
        if _is_project_frame(filename):
            filtered.append((frame.filename, frame.lineno, frame.name, (frame.line or '').strip()))
        if len(filtered) >= depth:
            break

    # Fallback: se nenhum frame de projeto, devolve os primeiros `depth` frames originais
    if not filtered:
        for frame in stack[:depth]:
            filtered.append((frame.filename, frame.lineno, frame.name, (frame.line or '').strip()))

    return filtered


def format_traceback(frames):
    """Formata a lista de frames para string multi-line legível."""
    lines = []
    for filename, lineno, func, text in frames:
        lines.append(f"{os.path.relpath(filename)}:{lineno} in {func} -> {text}")
    return '\n'.join(lines)
