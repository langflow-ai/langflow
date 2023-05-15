from langflow.interface.base import Function


class PythonFunction(Function):
    """Python function"""

    code: str
