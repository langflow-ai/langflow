from typing import cast

import pandas as pd

from langflow.schema.data import Data


class DataSet(pd.DataFrame):
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
        >>> dataset = DataSet([Data(data={"name": "John"}), Data(data={"name": "Jane"})])

        >>> # From dictionaries
        >>> dataset = DataSet([{"name": "John"}, {"name": "Jane"}])

        >>> # From dictionary of lists
        >>> dataset = DataSet({"name": ["John", "Jane"], "age": [30, 25]})
    """

    def __init__(self, data: None | list[dict | Data] | dict | pd.DataFrame = None, **kwargs):
        if data is None:
            super().__init__(**kwargs)
            return

        if isinstance(data, list):
            if all(isinstance(x, Data) for x in data):
                data = [d.data for d in data if hasattr(d, "data")]
            elif not all(isinstance(x, dict) for x in data):
                msg = "List items must be either all Data objects or all dictionaries"
                raise ValueError(msg)
            kwargs["data"] = data
        elif isinstance(data, dict | pd.DataFrame):
            kwargs["data"] = data

        super().__init__(**kwargs)

    def to_data_list(self) -> list[Data]:
        """Converts the DataSet back to a list of Data objects."""
        list_of_dicts = self.to_dict(orient="records")
        return [Data(data=row) for row in list_of_dicts]

    def add_row(self, data: dict | Data) -> "DataSet":
        """Adds a single row to the dataset.

        Args:
            data: Either a Data object or a dictionary to add as a new row

        Returns:
            DataSet: A new DataSet with the added row

        Example:
            >>> dataset = DataSet([{"name": "John"}])
            >>> dataset = dataset.add_row({"name": "Jane"})
        """
        if isinstance(data, Data):
            data = data.data
        new_df = self._constructor([data])
        return cast(DataSet, pd.concat([self, new_df], ignore_index=True))

    def add_rows(self, data: list[dict | Data]) -> "DataSet":
        """Adds multiple rows to the dataset.

        Args:
            data: List of Data objects or dictionaries to add as new rows

        Returns:
            DataSet: A new DataSet with the added rows
        """
        processed_data = []
        for item in data:
            if isinstance(item, Data):
                processed_data.append(item.data)
            else:
                processed_data.append(item)
        new_df = self._constructor(processed_data)
        return cast(DataSet, pd.concat([self, new_df], ignore_index=True))

    @property
    def _constructor(self):
        def _c(*args, **kwargs):
            return DataSet(*args, **kwargs).__finalize__(self)

        return _c
