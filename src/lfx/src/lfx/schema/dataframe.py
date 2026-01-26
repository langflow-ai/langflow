"""Table class for lfx package - pandas DataFrame subclass for Langflow data structures.

This module provides the Table class (formerly DataFrame) as the base type for tabular data in Langflow.
DataFrame is maintained as an alias for backwards compatibility.
"""

from typing import TYPE_CHECKING, cast

import pandas as pd
from langchain_core.documents import Document
from pandas import DataFrame as pandas_DataFrame

from lfx.schema.data import Data

if TYPE_CHECKING:
    from lfx.schema.message import Message


class Table(pandas_DataFrame):
    """A pandas DataFrame subclass specialized for handling collections of JSON objects.

    This is the base type for Langflow tabular data structures, replacing the legacy DataFrame class.
    DataFrame is maintained as an alias for backwards compatibility.

    This class extends pandas.DataFrame to provide seamless integration between
    Langflow's JSON objects and pandas' powerful data manipulation capabilities.

    Args:
        data: Input data in various formats:
            - List[Data]: List of Data/JSON objects
            - List[Dict]: List of dictionaries
            - Dict: Dictionary of arrays/lists
            - pandas.DataFrame: Existing DataFrame
            - Any format supported by pandas.DataFrame
        **kwargs: Additional arguments passed to pandas.DataFrame constructor

    Examples:
        >>> # From Data objects
        >>> dataset = Table([Data(data={"name": "John"}), Data(data={"name": "Jane"})])

        >>> # From dictionaries
        >>> dataset = Table([{"name": "John"}, {"name": "Jane"}])

        >>> # From dictionary of lists
        >>> dataset = Table({"name": ["John", "Jane"], "age": [30, 25]})
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
        """Helper method to update Table with new data."""
        new_df = pd.DataFrame(data, **kwargs)
        self._update_inplace(new_df)

    # Update property accessors
    @property
    def text_key(self) -> str:
        return self._text_key

    @text_key.setter
    def text_key(self, value: str) -> None:
        if value not in self.columns:
            msg = f"Text key '{value}' not found in Table columns"
            raise ValueError(msg)
        self._text_key = value

    @property
    def default_value(self) -> str:
        return self._default_value

    @default_value.setter
    def default_value(self, value: str) -> None:
        self._default_value = value

    def to_data_list(self) -> list[Data]:
        """Converts the Table back to a list of Data objects."""
        list_of_dicts = self.to_dict(orient="records")
        # suggested change: [Data(**row) for row in list_of_dicts]
        return [Data(data=row) for row in list_of_dicts]

    def add_row(self, data: dict | Data) -> "Table":
        """Adds a single row to the dataset.

        Args:
            data: Either a Data object or a dictionary to add as a new row

        Returns:
            Table: A new Table with the added row

        Example:
            >>> dataset = Table([{"name": "John"}])
            >>> dataset = dataset.add_row({"name": "Jane"})
        """
        if isinstance(data, Data):
            data = data.data
        new_df = self._constructor([data])
        return cast("Table", pd.concat([self, new_df], ignore_index=True))

    def add_rows(self, data: list[dict | Data]) -> "Table":
        """Adds multiple rows to the dataset.

        Args:
            data: List of Data objects or dictionaries to add as new rows

        Returns:
            Table: A new Table with the added rows
        """
        processed_data = []
        for item in data:
            if isinstance(item, Data):
                processed_data.append(item.data)
            else:
                processed_data.append(item)
        new_df = self._constructor(processed_data)
        return cast("Table", pd.concat([self, new_df], ignore_index=True))

    @property
    def _constructor(self):
        def _c(*args, **kwargs):
            return Table(*args, **kwargs).__finalize__(self)

        return _c

    def __bool__(self):
        """Truth value testing for the Table.

        Returns True if the Table has at least one row, False otherwise.
        """
        return not self.empty

    __hash__ = None  # Tables are mutable and shouldn't be hashable

    def to_lc_documents(self) -> list[Document]:
        """Converts the Table to a list of Documents.

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
        """Converts a list of Documents to a Table.

        Args:
            docs: List of Document objects

        Returns:
            Table: A new Table with the converted Documents
        """
        return Table(docs)

    def __eq__(self, other):
        """Override equality to handle comparison with empty Tables and non-Table objects."""
        if self.empty:
            return False
        if isinstance(other, list) and not other:  # Empty list case
            return False
        if not isinstance(other, Table | pd.DataFrame):  # Non-Table case
            return False
        return super().__eq__(other)

    def to_data(self) -> Data:
        """Convert this Table to a Data object.

        Returns:
            Data: A Data object containing the Table records under 'results' key.
        """
        dict_list = self.to_dict(orient="records")
        return Data(data={"results": dict_list})

    def to_message(self) -> "Message":
        from lfx.schema.message import Message

        # Process Table similar to the _safe_convert method
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


# DataFrame class is maintained for backwards compatibility - it is now an alias to Table
# All new code should use Table instead of DataFrame
DataFrame = Table
