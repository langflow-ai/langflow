"""Base service classes for lfx package."""

from abc import ABC, abstractmethod


class Service(ABC):
    """Base service class for pluggable implementations.

    Concrete services typically declare ``name`` as a class attribute, which
    satisfies the abstract ``name`` property. The ``ready`` flag is stored on
    ``_ready`` and remains assignable as ``self.ready`` for compatibility with
    existing implementations.
    """

    def __init__(self) -> None:
        self._ready = False

    @property
    @abstractmethod
    def name(self) -> str:
        """Service name."""

    @property
    def ready(self) -> bool:
        """Check if service is ready."""
        return getattr(self, "_ready", False)

    @ready.setter
    def ready(self, value: bool) -> None:
        self._ready = bool(value)

    def set_ready(self) -> None:
        """Mark service as ready."""
        self._ready = True

    def get_schema(self):
        """Build a dictionary listing public methods and their annotations."""
        schema = {}
        ignore = {"teardown", "set_ready"}
        for method in dir(self):
            if method.startswith("_") or method in ignore:
                continue
            func = getattr(self, method)
            if not callable(func):
                continue
            annotations = getattr(func, "__annotations__", {})
            schema[method] = {
                "name": method,
                "parameters": annotations,
                "return": annotations.get("return"),
                "documentation": func.__doc__,
            }
        return schema

    async def teardown(self) -> None:
        """Teardown the service. Override in concrete implementations as needed."""
        return
