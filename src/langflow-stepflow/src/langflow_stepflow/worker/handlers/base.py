"""Base classes for input and output handlers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any


class InputHandler(ABC):
    """Abstract base class for input-side value transformations.

    Subclasses declare which fields they handle via ``matches()`` (using
    template metadata and/or value content), optionally set up resources
    via ``activate()``, and transform values in ``prepare()``.
    """

    @abstractmethod
    def matches(self, *, template_field: dict[str, Any], value: Any) -> bool:
        """Return True if this handler should process the given field.

        Args:
            template_field: Template field metadata (type, input_types, etc.).
            value: The current runtime value for this field.
        """
        ...

    @asynccontextmanager
    async def activate(self) -> AsyncIterator[Any]:
        """Set up and tear down handler resources.

        Only entered when at least one field matches. Yields a context value
        that is passed to ``prepare()``. The default implementation yields
        ``None`` (no resources needed).
        """
        yield None

    @abstractmethod
    async def prepare(self, fields: dict[str, tuple[Any, dict[str, Any]]], context: Any) -> dict[str, Any]:
        """Batch-process all matched fields.

        Args:
            fields: Mapping of ``{key: (value, template_field)}`` for every
                parameter whose template field matched this handler.
            context: The value yielded by ``activate()``.

        Returns:
            Mapping of ``{key: resolved_value}`` for fields whose values
            changed. Fields omitted from the result keep their original value.
        """
        ...


class OutputHandler(ABC):
    """Abstract base class for output-side value transformations.

    Subclasses declare which values they handle via ``matches()`` (using
    Python type checks or value inspection) and transform values in
    ``process()``.

    Output handlers are applied during a recursive tree walk of the
    execution result. Each handler processes a single matched value;
    the executor handles recursion into dicts/lists.
    """

    @abstractmethod
    def matches(self, *, value: Any) -> bool:
        """Return True if this handler should process the given value.

        Args:
            value: The Python object to potentially serialize/transform.
        """
        ...

    @abstractmethod
    async def process(self, value: Any) -> Any:
        """Transform a single matched value.

        Args:
            value: The matched Python object.

        Returns:
            The serialized/transformed value (must be JSON-serializable
            or a container of further values for the tree walker).
        """
        ...
