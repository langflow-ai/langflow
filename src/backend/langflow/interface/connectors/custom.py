from langflow.interface.base import Function

DEFAULT_CONNECTOR_FUNCTION = """
def connector(text: str) -> str:
    \"\"\"This is a default python function that returns the input text\"\"\"
    return text
"""


class ConnectorFunction(Function):
    """Chain connector"""

    code: str = DEFAULT_CONNECTOR_FUNCTION


CONNECTORS = {
    "ConnectorFunction": ConnectorFunction,
}
