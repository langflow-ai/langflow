class dotdict(dict):  # noqa: N801
    """dotdict allows accessing dictionary elements using dot notation (e.g., dict.key instead of dict['key']).

    It automatically converts nested dictionaries into dotdict instances, enabling dot notation on them as well.

    Note:
        - Only keys that are valid attribute names (e.g., strings that could be variable names) are accessible via dot
          notation.
        - Keys which are not valid Python attribute names or collide with the dict method names (like 'items', 'keys')
          should be accessed using the traditional dict['key'] notation.
    """

    def __getattr__(self, attr):
        """Override dot access to behave like dictionary lookup. Automatically convert nested dicts to dotdicts.

        Args:
            attr (str): Attribute to access.

        Returns:
            The value associated with 'attr' in the dictionary, converted to dotdict if it is a dict.

        Raises:
            AttributeError: If the attribute is not found in the dictionary.
        """
        try:
            value = self[attr]
            if isinstance(value, dict) and not isinstance(value, dotdict):
                value = dotdict(value)
                self[attr] = value  # Update self to nest dotdict for future accesses
        except KeyError as e:
            msg = f"'dotdict' object has no attribute '{attr}'"
            raise AttributeError(msg) from e
        else:
            return value

    def __setattr__(self, key, value) -> None:
        """Override attribute setting to work as dictionary item assignment.

        Args:
            key (str): The key under which to store the value.
            value: The value to store in the dictionary.
        """
        if isinstance(value, dict) and not isinstance(value, dotdict):
            value = dotdict(value)
        self[key] = value

    def __delattr__(self, key) -> None:
        """Override attribute deletion to work as dictionary item deletion.

        Args:
            key (str): The key of the item to delete from the dictionary.

        Raises:
            AttributeError: If the key is not found in the dictionary.
        """
        try:
            del self[key]
        except KeyError as e:
            msg = f"'dotdict' object has no attribute '{key}'"
            raise AttributeError(msg) from e

    def __missing__(self, key):
        """Handle missing keys by returning an empty dotdict. This allows chaining access without raising KeyError.

        Args:
            key: The missing key.

        Returns:
            An empty dotdict instance for the given missing key.
        """
        return dotdict()
