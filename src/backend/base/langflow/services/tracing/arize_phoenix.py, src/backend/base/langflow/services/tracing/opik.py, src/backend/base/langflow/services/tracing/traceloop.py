# File: src/backend/base/langflow/services/tracing/arize_phoenix.py
"""
Arize Phoenix tracing integration.
"""

import types
from typing import Any, Dict

class ArizePhoenixService:
    def __init__(self, client: Any):
        """
        Initialize the Arize Phoenix tracing service.
        """
        self.client = client

    def _convert_to_arize_phoenix_type(self, value: Any) -> Any:
        """
        Convert Python values to types supported by Arize Phoenix.
        """
        if isinstance(value, (bool, int, float, str)):
            return value
        elif isinstance(value, types.GeneratorType | type(None)):
            value = str(value)
        elif isinstance(value, (list, tuple)):
            return type(value)(
                self._convert_to_arize_phoenix_type(v) for v in value
            )
        elif isinstance(value, dict):
            return {
                k: self._convert_to_arize_phoenix_type(v)
                for k, v in value.items()
            }
        else:
            return str(value)
        return value

    def send_trace(self, data: Dict[str, Any]) -> None:
        """
        Send trace data after converting types.
        """
        converted = {
            k: self._convert_to_arize_phoenix_type(v) for k, v in data.items()
        }
        self.client.send(converted)
</newLines>

<newLines>
# File: src/backend/base/langflow/services/tracing/opik.py
"""
Opik tracing integration.
"""

import types
from typing import Any, Dict

class OpikService:
    def __init__(self, client: Any):
        """
        Initialize the Opik tracing service.
        """
        self.client = client

    def _convert_to_opik_type(self, value: Any) -> Any:
        """
        Convert Python values to types supported by Opik.
        """
        if isinstance(value, (bool, int, float, str)):
            return value
        elif isinstance(value, types.GeneratorType | type(None)):
            value = str(value)
        elif isinstance(value, (list, tuple)):
            return type(value)(
                self._convert_to_opik_type(v) for v in value
            )
        elif isinstance(value, dict):
            return {
                k: self._convert_to_opik_type(v)
                for k, v in value.items()
            }
        else:
            return str(value)
        return value

    def send_trace(self, data: Dict[str, Any]) -> None:
        """
        Send trace data after converting types.
        """
        converted = {
            k: self._convert_to_opik_type(v) for k, v in data.items()
        }
        self.client.record(converted)
</newLines>

<newLines>
# File: src/backend/base/langflow/services/tracing/traceloop.py
"""
TraceLoop tracing integration.
"""

import types
from typing import Any, Dict

class TraceLoopService:
    def __init__(self, client: Any):
        """
        Initialize the TraceLoop tracing service.
        """
        self.client = client

    def _convert_to_traceloop_type(self, value: Any) -> Any:
        """
        Convert Python values to types supported by TraceLoop.
        """
        if isinstance(value, (bool, int, float, str)):
            return value
        elif isinstance(value, types.GeneratorType | type(None)):
            value = str(value)
        elif isinstance(value, (list, tuple)):
            return type(value)(
                self._convert_to_traceloop_type(v) for v in value
            )
        elif isinstance(value, dict):
            return {
                k: self._convert_to_traceloop_type(v)
                for k, v in value.items()
            }
        else:
            return str(value)
        return value

    def send_trace(self, data: Dict[str, Any]) -> None:
        """
        Send trace data after converting types.
        """
        converted = {
            k: self._convert_to_traceloop_type(v) for k, v in data.items()
        }
        self.client.log(converted)