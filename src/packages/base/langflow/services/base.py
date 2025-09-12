from abc import ABC


class Service(ABC):
    name: str
    ready: bool = False

    def get_schema(self):
        """Build a dictionary listing all methods, their parameters, types, return types and documentation."""
        schema = {}
        ignore = ["teardown", "set_ready"]
        for method in dir(self):
            if method.startswith("_") or method in ignore:
                continue
            func = getattr(self, method)
            schema[method] = {
                "name": method,
                "parameters": func.__annotations__,
                "return": func.__annotations__.get("return"),
                "documentation": func.__doc__,
            }
        return schema

    async def teardown(self) -> None:
        return

    def set_ready(self) -> None:
        self.ready = True
