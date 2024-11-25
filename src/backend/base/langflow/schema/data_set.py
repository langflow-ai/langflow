import pandas as pd

from langflow.schema.data import Data


class DataSet(pd.DataFrame):
    """A DataFrame that can be initialized from a list of Data objects."""

    @classmethod
    def from_data_list(cls, data_list: list[Data]) -> "DataSet":
        """Create a DataSet from a list of Data objects."""
        data_dicts = [d.data for d in data_list]
        return cls(data_dicts)

    def to_data_list(self) -> list[Data]:
        """Convert the DataFrame back to a list of Data objects."""
        return [Data(data=row.to_dict()) for _, row in self.iterrows()]
