import abc


class BaseCache(abc.ABC):
    """
    Abstract base class for a cache.
    """

    @abc.abstractmethod
    def get(self, key):
        """
        Retrieve an item from the cache.

        Args:
            key: The key of the item to retrieve.

        Returns:
            The value associated with the key, or None if the key is not found.
        """
        pass

    @abc.abstractmethod
    def set(self, key, value):
        """
        Add an item to the cache.

        Args:
            key: The key of the item.
            value: The value to cache.
        """
        pass

    @abc.abstractmethod
    def delete(self, key):
        """
        Remove an item from the cache.

        Args:
            key: The key of the item to remove.
        """
        pass

    @abc.abstractmethod
    def clear(self):
        """
        Clear all items from the cache.
        """
        pass

    @abc.abstractmethod
    def __contains__(self, key):
        """
        Check if the key is in the cache.

        Args:
            key: The key of the item to check.

        Returns:
            True if the key is in the cache, False otherwise.
        """
        pass

    @abc.abstractmethod
    def __getitem__(self, key):
        """
        Retrieve an item from the cache using the square bracket notation.

        Args:
            key: The key of the item to retrieve.

        Returns:
            The value associated with the key, or None if the key is not found.
        """
        pass

    @abc.abstractmethod
    def __setitem__(self, key, value):
        """
        Add an item to the cache using the square bracket notation.

        Args:
            key: The key of the item.
            value: The value to cache.
        """
        pass

    @abc.abstractmethod
    def __delitem__(self, key):
        """
        Remove an item from the cache using the square bracket notation.

        Args:
            key: The key of the item to remove.
        """
        pass
