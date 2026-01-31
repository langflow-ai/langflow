# src/backend/base/langflow/services/tracing/arize_phoenix.py

import types

def _convert_to_arize_phoenix_type(value):
    """
    Convert a Python value to a type compatible with Arize Phoenix tracing.
    """
    if isinstance(value, (bool, int, float, str)):
        return value
    elif isinstance(value, types.GeneratorType | type(None)):
        value = str(value)
        return value
    else:
        return str(value)
</newLines>
<newLines>
# src/backend/base/langflow/services/tracing/opik.py

import types

def _convert_to_opik_type(value):
    """
    Convert a Python value to a type compatible with Opik tracing.
    """
    if isinstance(value, (bool, int, float, str)):
        return value
    elif isinstance(value, types.GeneratorType | type(None)):
        value = str(value)
        return value
    else:
        return str(value)
</newLines>
<newLines>
# src/backend/base/langflow/services/tracing/traceloop.py

import types

def _convert_to_traceloop_type(value):
    """
    Convert a Python value to a type compatible with TraceLoop tracing.
    """
    if isinstance(value, (bool, int, float, str)):
        return value
    elif isinstance(value, types.GeneratorType | type(None)):
        value = str(value)
        return value
    else:
        return str(value)