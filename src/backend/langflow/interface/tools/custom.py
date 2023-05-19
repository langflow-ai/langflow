from langflow.interface.base import BaseFunction


class PythonFunction(BaseFunction):
    """Python function"""

    code: str
