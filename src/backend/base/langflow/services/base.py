from abc import ABC
from enum import Enum


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


class ServiceType(str, Enum):
    SETTINGS_SERVICE = "settings_service"
    DATABASE_SERVICE = "database_service"
    CACHE_SERVICE = "cache_service"
    STORAGE_SERVICE = "storage_service"
    TELEMETRY_SERVICE = "telemetry_service"
    TRACING_SERVICE = "tracing_service"
    VARIABLE_SERVICE = "variable_service"
    JOB_QUEUE_SERVICE = "job_queue_service"
    OAUTH_SERVICE = "oauth_service"
