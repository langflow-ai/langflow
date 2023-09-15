from contextlib import contextmanager
from typing import Any, Awaitable, Callable, List, Optional
from langflow.services.base import Service

import pandas as pd
from PIL import Image


class Subject:
    """Base class for implementing the observer pattern."""

    def __init__(self):
        self.observers: List[Callable[[], None]] = []

    def attach(self, observer: Callable[[], None]):
        """Attach an observer to the subject."""
        self.observers.append(observer)

    def detach(self, observer: Callable[[], None]):
        """Detach an observer from the subject."""
        self.observers.remove(observer)

    def notify(self):
        """Notify all observers about an event."""
        for observer in self.observers:
            if observer is None:
                continue
            observer()


class AsyncSubject:
    """Base class for implementing the async observer pattern."""

    def __init__(self):
        self.observers: List[Callable[[], Awaitable]] = []

    def attach(self, observer: Callable[[], Awaitable]):
        """Attach an observer to the subject."""
        self.observers.append(observer)

    def detach(self, observer: Callable[[], Awaitable]):
        """Detach an observer from the subject."""
        self.observers.remove(observer)

    async def notify(self):
        """Notify all observers about an event."""
        for observer in self.observers:
            if observer is None:
                continue
            await observer()


class CacheService(Subject, Service):
    """Manages cache for different clients and notifies observers on changes."""

    name = "cache_service"

    def __init__(self):
        super().__init__()
        self._cache = {}
        self.current_client_id = None
        self.current_cache = {}

    @contextmanager
    def set_client_id(self, client_id: str):
        """
        Context manager to set the current client_id and associated cache.

        Args:
            client_id (str): The client identifier.
        """
        previous_client_id = self.current_client_id
        self.current_client_id = client_id
        self.current_cache = self._cache.setdefault(client_id, {})
        try:
            yield
        finally:
            self.current_client_id = previous_client_id
            self.current_cache = self._cache.get(self.current_client_id, {})

    def add(self, name: str, obj: Any, obj_type: str, extension: Optional[str] = None):
        """
        Add an object to the current client's cache.

        Args:
            name (str): The cache key.
            obj (Any): The object to cache.
            obj_type (str): The type of the object.
        """
        object_extensions = {
            "image": "png",
            "pandas": "csv",
        }
        if obj_type in object_extensions:
            _extension = object_extensions[obj_type]
        else:
            _extension = type(obj).__name__.lower()
        self.current_cache[name] = {
            "obj": obj,
            "type": obj_type,
            "extension": extension or _extension,
        }
        self.notify()

    def add_pandas(self, name: str, obj: Any):
        """
        Add a pandas DataFrame or Series to the current client's cache.

        Args:
            name (str): The cache key.
            obj (Any): The pandas DataFrame or Series object.
        """
        if isinstance(obj, (pd.DataFrame, pd.Series)):
            self.add(name, obj.to_csv(), "pandas", extension="csv")
        else:
            raise ValueError("Object is not a pandas DataFrame or Series")

    def add_image(self, name: str, obj: Any, extension: str = "png"):
        """
        Add a PIL Image to the current client's cache.

        Args:
            name (str): The cache key.
            obj (Any): The PIL Image object.
        """
        if isinstance(obj, Image.Image):
            self.add(name, obj, "image", extension=extension)
        else:
            raise ValueError("Object is not a PIL Image")

    def get(self, name: str):
        """
        Get an object from the current client's cache.

        Args:
            name (str): The cache key.

        Returns:
            The cached object associated with the given cache key.
        """
        return self.current_cache[name]

    def get_last(self):
        """
        Get the last added item in the current client's cache.

        Returns:
            The last added item in the cache.
        """
        return list(self.current_cache.values())[-1]


cache_service = CacheService()
