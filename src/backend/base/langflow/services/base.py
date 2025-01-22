from abc import ABC
import psutil
import os


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

def log_memory_usage():
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    logger.debug(f"Memory usage: {mem_info.rss / 1024 / 1024:.2f} MB")

class FlowService:
    async def process_large_flow(self, flow_data):
        log_memory_usage()
        # Process flow
        result = await self._process_flow(flow_data)
        log_memory_usage()
        return result
