import re
import keyword
import builtins

PYTHON_KEYWORDS = set(keyword.kwlist)
PYTHON_BUILTINS = set(dir(builtins))

def is_valid_component_name(name: str) -> bool:
    if not isinstance(name, str) or len(name) == 0:
        return False
    if len(name) > 100:
        return False
        
    # Checagem de Palavras Reservadas (Ciclo 2.3)
    if name in PYTHON_KEYWORDS:
        return False

    # NOVO: Checagem de Nomes Built-in (Ciclo 2.4)
    if name in PYTHON_BUILTINS:
        return False

    # Checagem de Caracteres/Estrutura (Ciclo 2.1)
    pattern = r"^[a-zA-Z_][a-zA-Z0-9_]*$" 
    return re.fullmatch(pattern, name) is not None