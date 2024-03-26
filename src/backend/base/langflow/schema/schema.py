import copy

from langchain_core.documents import Document
from pydantic import BaseModel, model_validator


class Record(BaseModel):
    """
    Represents a record with text and optional data.

    Attributes:
        data (dict, optional): Additional data associated with the record.
    """

    data: dict = {}
    _default_value: str = ""

    @model_validator(mode="before")
    def validate_data(cls, values):
        if not values.get("data"):
            values["data"] = {}
        # Any other keyword should be added to the data dictionary
        for key in values:
            if key not in values["data"] and key != "data":
                values["data"][key] = values[key]
        return values

    @classmethod
    def from_document(cls, document: Document) -> "Record":
        """
        Converts a Document to a Record.

        Args:
            document (Document): The Document to convert.

        Returns:
            Record: The converted Record.
        """
        data = document.metadata
        data["text"] = document.page_content
        return cls(data=data)

    def __add__(self, other: "Record") -> "Record":
        """
        Concatenates the text of two records and combines their data.

        Args:
            other (Record): The other record to concatenate with.

        Returns:
            Record: The concatenated record.
        """
        combined_data = {**self.data, **other.data}
        return Record(data=combined_data)

    def to_lc_document(self) -> Document:
        """
        Converts the Record to a Document.

        Returns:
            Document: The converted Document.
        """
        return Document(page_content=self.text, metadata=self.data)

    def __getattr__(self, key):
        """
        Allows attribute-like access to the data dictionary.
        """
        try:
            if key == "data" or key.startswith("_"):
                return super().__getattr__(key)

            return self.data.get(key, self._default_value)
        except KeyError:
            # Fallback to default behavior to raise AttributeError for undefined attributes
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{key}'")

    def __setattr__(self, key, value):
        """
        Allows attribute-like setting of values in the data dictionary,
        while still allowing direct assignment to class attributes.
        """
        if key == "data" or key.startswith("_"):
            super().__setattr__(key, value)
        else:
            self.data[key] = value

    def __delattr__(self, key):
        """
        Allows attribute-like deletion from the data dictionary.
        """
        if key == "data" or key.startswith("_"):
            super().__delattr__(key)
        else:
            del self.data[key]

    def __deepcopy__(self, memo):
        """
        Custom deepcopy implementation to handle copying of the Record object.
        """
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            setattr(result, k, copy.deepcopy(v, memo))
        return result

    def __str__(self) -> str:
        """
        Returns a string representation of the Record, including text and data.
        """
        # Assuming a method to dump model data as JSON string exists.
        # If it doesn't, you might need to implement it or use json.dumps() directly.
        # build the string considering all keys in the data dictionary
        prefix = "Record("
        suffix = ")"
        text = ", ".join([f"{k}={v}" for k, v in self.data.items()])
        return prefix + text + suffix

    # check which attributes the Record has by checking the keys in the data dictionary
    def __dir__(self):
        return super().__dir__() + list(self.data.keys())


INPUT_FIELD_NAME = "input_value"
