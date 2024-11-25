import pandas as pd

from langflow.schema.data import Data


class DataSet(pd.DataFrame):
    """A pandas DataFrame subclass specialized for handling collections of Data objects.

    This class extends pandas.DataFrame to provide seamless integration between
    Langflow's Data objects and pandas' powerful data manipulation capabilities.

    Key Features:
        - Direct initialization from a list of Data objects
        - Maintains all pandas DataFrame functionality
        - Conversion back to Data objects when needed

    Notes:
        - Nested dictionaries within Data objects are preserved in their column representation
        - All pandas DataFrame operations (groupby, merge, concat, etc.) remain available
        - Column dtypes are inferred from the Data objects' contents

    Examples:
        >>> data_objects = [
        ...     Data(data={"name": "John", "age": 30}),
        ...     Data(data={"name": "Jane", "age": 25})
        ... ]
        >>> dataset = DataSet.from_data_list(data_objects)
        >>> dataset['age'].mean()
        27.5
        >>> original_data = dataset.to_data_list()

    Inheritance:
        This class inherits all functionality from pandas.DataFrame, meaning any
        operation that works on a DataFrame will work on a DataSet:
        - Filtering: dataset[dataset['age'] > 25]
        - Aggregation: dataset.groupby('category').mean()
        - Statistical operations: dataset.describe()
        - etc.
    """

    @classmethod
    def from_data_list(cls, data_list: list[Data]) -> "DataSet":
        """Creates a DataSet from a list of Data objects.

        This method converts a list of Data objects into a DataFrame structure,
        preserving all data from the original Data objects.

        Args:
            data_list (list[Data]): A list of Data objects to convert into a DataFrame.
                Each Data object's internal dictionary becomes a row in the DataFrame.

        Returns:
            DataSet: A new DataSet instance containing all data from the input list.

        Examples:
            >>> data_objects = [
            ...     Data(data={"name": "John", "age": 30}),
            ...     Data(data={"name": "Jane", "age": 25})
            ... ]
            >>> dataset = DataSet.from_data_list(data_objects)
            >>> print(dataset.columns)
            Index(['name', 'age'], dtype='object')

        Notes:
            - Column names are derived from the keys in the Data objects
            - If Data objects have different keys, the resulting DataFrame will have
              NaN values for missing data
            - The original structure of nested data is preserved in the DataFrame
        """
        data_dicts = [d.data for d in data_list]
        return cls(data_dicts)

    def to_data_list(self) -> list[Data]:
        """Converts the DataSet back to a list of Data objects.

        This method transforms each row of the DataFrame back into a Data object,
        reconstructing the original data structure.

        Returns:
            list[Data]: A list of Data objects, where each object corresponds to
                a row in the DataFrame.

        Examples:
            >>> dataset = DataSet({'name': ['John'], 'age': [30]})
            >>> data_objects = dataset.to_data_list()
            >>> print(data_objects[0].data)
            {'name': 'John', 'age': 30}

        Notes:
            - Each row is converted to a dictionary using to_dict()
            - The resulting Data objects will contain all columns as keys in their
              internal dictionary
            - Any modifications made to the DataFrame will be reflected in the
              resulting Data objects
        """
        return [Data(data=row.to_dict()) for _, row in self.iterrows()]
