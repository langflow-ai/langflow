import pandas as pd
import pytest
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame


@pytest.fixture
def sample_data_objects() -> list[Data]:
    """Fixture providing a list of sample Data objects."""
    return [
        Data(data={"name": "John", "age": 30, "city": "New York"}),
        Data(data={"name": "Jane", "age": 25, "city": "Boston"}),
        Data(data={"name": "Bob", "age": 35, "city": "Chicago"}),
    ]


@pytest.fixture
def sample_dataset(sample_data_objects) -> DataFrame:
    """Fixture providing a sample DataFrame instance."""
    return DataFrame(sample_data_objects)


def test_from_data_list_basic():
    """Test basic functionality of from_data_list."""
    data_objects = [Data(data={"name": "John", "age": 30}), Data(data={"name": "Jane", "age": 25})]
    dataset = DataFrame(data_objects)

    assert isinstance(dataset, DataFrame)
    assert isinstance(dataset, pd.DataFrame)
    expected_len = 2
    assert len(dataset) == expected_len
    assert list(dataset.columns) == ["name", "age"]
    assert dataset.iloc[0]["name"] == "John"
    expected_age = 25
    assert dataset.iloc[1]["age"] == expected_age


def test_from_data_list_empty():
    """Test from_data_list with empty input."""
    dataset = DataFrame([])
    assert isinstance(dataset, DataFrame)
    assert len(dataset) == 0


def test_from_data_list_missing_fields():
    """Test from_data_list with inconsistent data fields."""
    data_objects = [
        Data(data={"name": "John", "age": 30}),
        Data(data={"name": "Jane", "city": "Boston"}),  # Missing age
    ]
    dataset = DataFrame(data_objects)

    assert isinstance(dataset, DataFrame)
    assert set(dataset.columns) == {"name", "age", "city"}
    assert pd.isna(dataset.iloc[1]["age"])
    assert pd.isna(dataset.iloc[0]["city"])


def test_from_data_list_nested_data():
    """Test from_data_list with nested dictionary data."""
    data_objects = [
        Data(data={"name": "John", "address": {"city": "New York", "zip": "10001"}}),
        Data(data={"name": "Jane", "address": {"city": "Boston", "zip": "02108"}}),
    ]
    dataset = DataFrame(data_objects)

    assert isinstance(dataset, DataFrame)
    assert isinstance(dataset["address"][0], dict)
    assert dataset["address"][0]["city"] == "New York"


def test_to_data_list_basic(sample_dataset, sample_data_objects):
    """Test basic functionality of to_data_list."""
    result = sample_dataset.to_data_list()

    assert isinstance(result, list)
    assert all(isinstance(item, Data) for item in result)
    assert len(result) == len(sample_data_objects)

    # Check if data is preserved
    for original, converted in zip(sample_data_objects, result, strict=False):
        assert original.data == converted.data


def test_to_data_list_empty():
    """Test to_data_list with empty DataFrame."""
    empty_dataset = DataFrame()
    result = empty_dataset.to_data_list()
    assert isinstance(result, list)
    assert len(result) == 0


def test_to_data_list_modified_data(sample_dataset):
    """Test to_data_list after DataFrame modifications."""
    # Modify the dataset
    sample_dataset["new_column"] = [1, 2, 3]
    sample_dataset.iloc[0, sample_dataset.columns.get_loc("age")] = 31

    result = sample_dataset.to_data_list()

    assert isinstance(result, list)
    assert all(isinstance(item, Data) for item in result)
    assert result[0].data["new_column"] == 1
    expected_age = 31
    assert result[0].data["age"] == expected_age


def test_dataset_pandas_operations(sample_dataset):
    """Test that pandas operations work correctly on DataFrame."""
    # Test filtering
    filtered = sample_dataset[sample_dataset["age"] > 30]
    assert isinstance(filtered, DataFrame), f"Expected DataFrame, got {type(filtered)}"
    expected_len = 1
    assert len(filtered) == expected_len
    assert filtered.iloc[0]["name"] == "Bob"

    # Test aggregation
    mean_age = sample_dataset["age"].mean()
    expected_mean = 30
    assert mean_age == expected_mean

    # Test groupby
    grouped = sample_dataset.groupby("city").agg({"age": "mean"})
    assert isinstance(grouped, pd.DataFrame)
    expected_len = 3
    assert len(grouped) == expected_len


def test_dataset_with_null_values():
    """Test handling of null values in DataFrame."""
    data_objects = [Data(data={"name": "John", "age": None}), Data(data={"name": None, "age": 25})]
    dataset = DataFrame(data_objects)

    assert pd.isna(dataset.iloc[0]["age"])
    assert pd.isna(dataset.iloc[1]["name"])

    # Test that null values are preserved when converting back
    result = dataset.to_data_list()
    assert pd.isna(result[0].data["age"]), f"Expected NaN, got {result[0].data['age']}"
    assert pd.isna(result[1].data["name"]), f"Expected NaN, got {result[1].data['name']}"


def test_dataset_type_preservation():
    """Test that data types are preserved through conversion."""
    data_objects = [
        Data(
            data={
                "int_val": 1,
                "float_val": 1.5,
                "str_val": "test",
                "bool_val": True,
                "list_val": [1, 2, 3],
                "dict_val": {"key": "value"},
            }
        )
    ]
    dataset = DataFrame(data_objects)
    result = dataset.to_data_list()

    assert isinstance(result[0].data["int_val"], int)
    assert isinstance(result[0].data["float_val"], float)
    assert isinstance(result[0].data["str_val"], str)
    assert isinstance(result[0].data["bool_val"], bool)
    assert isinstance(result[0].data["list_val"], list)
    assert isinstance(result[0].data["dict_val"], dict)


def test_add_row_with_dict(sample_dataset):
    """Test adding a single row using a dictionary."""
    new_row = {"name": "Alice", "age": 28, "city": "Seattle"}
    result = sample_dataset.add_row(new_row)

    assert isinstance(result, DataFrame)
    assert len(result) == len(sample_dataset) + 1
    assert result.iloc[-1]["name"] == "Alice"
    expected_age = 28
    assert result.iloc[-1]["age"] == expected_age
    assert result.iloc[-1]["city"] == "Seattle"


def test_add_row_with_data_object(sample_dataset):
    """Test adding a single row using a Data object."""
    new_row = Data(data={"name": "Alice", "age": 28, "city": "Seattle"})
    result = sample_dataset.add_row(new_row)

    assert isinstance(result, DataFrame)
    assert len(result) == len(sample_dataset) + 1
    assert result.iloc[-1]["name"] == "Alice"
    expected_age = 28
    assert result.iloc[-1]["age"] == expected_age
    assert result.iloc[-1]["city"] == "Seattle"


def test_add_rows_with_dicts(sample_dataset):
    """Test adding multiple rows using dictionaries."""
    new_rows = [{"name": "Alice", "age": 28, "city": "Seattle"}, {"name": "Charlie", "age": 32, "city": "Portland"}]
    result = sample_dataset.add_rows(new_rows)

    assert isinstance(result, DataFrame)
    assert len(result) == len(sample_dataset) + 2
    assert result.iloc[-2]["name"] == "Alice"
    assert result.iloc[-1]["name"] == "Charlie"


def test_add_rows_with_data_objects(sample_dataset):
    """Test adding multiple rows using Data objects."""
    new_rows = [
        Data(data={"name": "Alice", "age": 28, "city": "Seattle"}),
        Data(data={"name": "Charlie", "age": 32, "city": "Portland"}),
    ]
    result = sample_dataset.add_rows(new_rows)

    assert isinstance(result, DataFrame)
    assert len(result) == len(sample_dataset) + 2
    assert result.iloc[-2]["name"] == "Alice"
    assert result.iloc[-1]["name"] == "Charlie"


def test_add_rows_mixed_types(sample_dataset):
    """Test adding multiple rows using a mix of dictionaries and Data objects."""
    new_rows = [
        {"name": "Alice", "age": 28, "city": "Seattle"},
        Data(data={"name": "Charlie", "age": 32, "city": "Portland"}),
    ]
    result = sample_dataset.add_rows(new_rows)

    assert isinstance(result, DataFrame)
    assert len(result) == len(sample_dataset) + 2
    assert result.iloc[-2]["name"] == "Alice"
    assert result.iloc[-1]["name"] == "Charlie"


def test_init_with_data_objects():
    """Test initialization with Data objects."""
    data_objects = [Data(data={"name": "John", "age": 30}), Data(data={"name": "Jane", "age": 25})]
    dataset = DataFrame(data_objects)

    assert isinstance(dataset, DataFrame)
    expected_len = 2
    assert len(dataset) == expected_len
    assert list(dataset.columns) == ["name", "age"]
    assert dataset.iloc[0]["name"] == "John"
    expected_age = 25
    assert dataset.iloc[1]["age"] == expected_age


def test_init_with_dicts():
    """Test initialization with dictionaries."""
    data_dicts = [{"name": "John", "age": 30}, {"name": "Jane", "age": 25}]
    dataset = DataFrame(data_dicts)

    assert isinstance(dataset, DataFrame)
    expected_len = 2
    assert len(dataset) == expected_len
    assert list(dataset.columns) == ["name", "age"]
    assert dataset.iloc[0]["name"] == "John"
    expected_age = 25
    assert dataset.iloc[1]["age"] == expected_age


def test_init_with_dict_of_lists():
    """Test initialization with a dictionary of lists."""
    data = {"name": ["John", "Jane"], "age": [30, 25]}
    dataset = DataFrame(data)

    assert isinstance(dataset, DataFrame)
    expected_len = 2
    assert len(dataset) == expected_len
    assert list(dataset.columns) == ["name", "age"]
    assert dataset.iloc[0]["name"] == "John"
    expected_age = 25
    assert dataset.iloc[1]["age"] == expected_age


def test_init_with_pandas_dataframe():
    """Test initialization with a pandas DataFrame."""
    test_df = pd.DataFrame({"name": ["John", "Jane"], "age": [30, 25]})
    dataset = DataFrame(test_df)

    assert isinstance(dataset, DataFrame)
    expected_len = 2
    assert len(dataset) == expected_len
    assert list(dataset.columns) == ["name", "age"]
    assert dataset.iloc[0]["name"] == "John"
    expected_age = 25
    assert dataset.iloc[1]["age"] == expected_age


def test_init_with_none():
    """Test initialization with None."""
    dataset = DataFrame(None)
    assert isinstance(dataset, DataFrame)
    assert len(dataset) == 0


def test_init_with_invalid_list():
    """Test initialization with invalid list items."""
    invalid_data = [
        {"name": "John", "age": 30},
        Data(data={"name": "Jane", "age": 25}),  # Mixed types should fail
    ]
    with pytest.raises(ValueError, match="List items must be either all Data objects or all dictionaries"):
        DataFrame(invalid_data)


def test_init_with_kwargs():
    """Test initialization with additional kwargs."""
    data = {"name": ["John", "Jane"], "age": [30, 25]}
    dataset = DataFrame(data=data, index=["a", "b"])

    assert isinstance(dataset, DataFrame)
    expected_len = 2
    assert len(dataset) == expected_len
    assert list(dataset.index) == ["a", "b"]
    assert dataset.loc["a"]["name"] == "John"
    expected_age = 25
    assert dataset.loc["b"]["age"] == expected_age
