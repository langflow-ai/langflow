from typing import cast

import pandas as pd
from langchain_core.documents import Document
from pandas import DataFrame as pandas_DataFrame

from langflow.schema.data import Data
from langflow.schema.message import Message


class DataFrame(pandas_DataFrame):
    """A pandas DataFrame subclass specialized for handling collections of Data objects.

    This class extends pandas.DataFrame to provide seamless integration between
    Langflow's Data objects and pandas' powerful data manipulation capabilities.

    Args:
        data: Input data in various formats:
            - List[Data]: List of Data objects
            - List[Dict]: List of dictionaries
            - Dict: Dictionary of arrays/lists
            - pandas.DataFrame: Existing DataFrame
            - Any format supported by pandas.DataFrame
        **kwargs: Additional arguments passed to pandas.DataFrame constructor

    Examples:
        >>> # From Data objects
        >>> dataset = DataFrame([Data(data={"name": "John"}), Data(data={"name": "Jane"})])

        >>> # From dictionaries
        >>> dataset = DataFrame([{"name": "John"}, {"name": "Jane"}])

        >>> # From dictionary of lists
        >>> dataset = DataFrame({"name": ["John", "Jane"], "age": [30, 25]})
    """

    def __init__(
        self,
        data: list[dict] | list[Data] | pd.DataFrame | None = None,
        text_key: str = "text",
        default_value: str = "",
        **kwargs,
    ):
        # Initialize pandas DataFrame first without data
        super().__init__(**kwargs)  # Removed data parameter

        # Store attributes as private members to avoid conflicts with pandas
        self._text_key = text_key
        self._default_value = default_value

        if data is None:
            return

        if isinstance(data, list):
            if all(isinstance(x, Data) for x in data):
                data = [d.data for d in data if hasattr(d, "data")]
            elif not all(isinstance(x, dict) for x in data):
                msg = "List items must be either all Data objects or all dictionaries"
                raise ValueError(msg)
            self._update(data, **kwargs)
        elif isinstance(data, dict | pd.DataFrame):  # Fixed type check syntax
            self._update(data, **kwargs)

    def _update(self, data, **kwargs):
        """Helper method to update DataFrame with new data."""
        new_df = pd.DataFrame(data, **kwargs)
        self._update_inplace(new_df)

    # Update property accessors
    @property
    def text_key(self) -> str:
        return self._text_key

    @text_key.setter
    def text_key(self, value: str) -> None:
        if value not in self.columns:
            msg = f"Text key '{value}' not found in DataFrame columns"
            raise ValueError(msg)
        self._text_key = value

    @property
    def default_value(self) -> str:
        return self._default_value

    @default_value.setter
    def default_value(self, value: str) -> None:
        self._default_value = value

    def to_data_list(self) -> list[Data]:
        """Converts the DataFrame back to a list of Data objects."""
        list_of_dicts = self.to_dict(orient="records")
        # suggested change: [Data(**row) for row in list_of_dicts]
        return [Data(data=row) for row in list_of_dicts]

    def add_row(self, data: dict | Data) -> "DataFrame":
        """Adds a single row to the dataset.

        Args:
            data: Either a Data object or a dictionary to add as a new row

        Returns:
            DataFrame: A new DataFrame with the added row

        Example:
            >>> dataset = DataFrame([{"name": "John"}])
            >>> dataset = dataset.add_row({"name": "Jane"})
        """
        if isinstance(data, Data):
            data = data.data
        new_df = self._constructor([data])
        return cast("DataFrame", pd.concat([self, new_df], ignore_index=True))

    def add_rows(self, data: list[dict | Data]) -> "DataFrame":
        """Adds multiple rows to the dataset.

        Args:
            data: List of Data objects or dictionaries to add as new rows

        Returns:
            DataFrame: A new DataFrame with the added rows
        """
        processed_data = []
        for item in data:
            if isinstance(item, Data):
                processed_data.append(item.data)
            else:
                processed_data.append(item)
        new_df = self._constructor(processed_data)
        return cast("DataFrame", pd.concat([self, new_df], ignore_index=True))

    @property
    def _constructor(self):
        def _c(*args, **kwargs):
            return DataFrame(*args, **kwargs).__finalize__(self)

        return _c

    def __bool__(self):
        """Truth value testing for the DataFrame.

        Returns True if the DataFrame has at least one row, False otherwise.
        """
        return not self.empty

    def to_lc_documents(self) -> list[Document]:
        """Converts the DataFrame to a list of Documents.

        Returns:
            list[Document]: The converted list of Documents.
        """
        list_of_dicts = self.to_dict(orient="records")
        documents = []
        for row in list_of_dicts:
            data_copy = row.copy()
            text = data_copy.pop(self._text_key, self._default_value)
            if isinstance(text, str):
                documents.append(Document(page_content=text, metadata=data_copy))
            else:
                documents.append(Document(page_content=str(text), metadata=data_copy))
        return documents

    def _docs_to_dataframe(self, docs):
        """Converts a list of Documents to a DataFrame.

        Args:
            docs: List of Document objects

        Returns:
            DataFrame: A new DataFrame with the converted Documents
        """
        return DataFrame(docs)

    def __eq__(self, other):
        """Override equality to handle comparison with empty DataFrames and non-DataFrame objects."""
        if self.empty:
            return False
        if isinstance(other, list) and not other:  # Empty list case
            return False
        if not isinstance(other, DataFrame | pd.DataFrame):  # Non-DataFrame case
            return False
        return super().__eq__(other)

    def to_data(self) -> Data:
        """Convert this DataFrame to a Data object.

        Returns:
            Data: A Data object containing the DataFrame records under 'results' key.
        """
        dict_list = self.to_dict(orient="records")
        return Data(data={"results": dict_list})

    def to_message(self) -> Message:
        from langflow.schema.message import Message  # Local import to avoid circular import

        # Process DataFrame similar to the _safe_convert method
        # Remove empty rows
        processed_df = self.dropna(how="all")
        # Remove empty lines in each cell
        processed_df = processed_df.replace(r"^\s*$", "", regex=True)
        # Replace multiple newlines with a single newline
        processed_df = processed_df.replace(r"\n+", "\n", regex=True)
        # Replace pipe characters to avoid markdown table issues
        processed_df = processed_df.replace(r"\|", r"\\|", regex=True)
        processed_df = processed_df.map(lambda x: str(x).replace("\n", "<br/>") if isinstance(x, str) else x)
        # Convert to markdown and wrap in a Message
        return Message(text=processed_df.to_markdown(index=False))
