import pytest
from lfx.schema.data import Data
from lfx.utils.data_structure import get_data_structure, get_sample_values


@pytest.mark.parametrize("max_items", [1, 2, 4])
@pytest.mark.parametrize("outer_type", [list, tuple, set])
def test_nested_collection_sample_limit(max_items, outer_type):
    values = outer_type([(1, 2, 3, 4, 5)])

    assert get_sample_values(values, max_items=max_items) == [[1, 2, 3, 4, 5][:max_items]]


@pytest.mark.parametrize("max_sample_size", [1, 2, 4])
def test_data_structure_nested_sample_limit(max_sample_size):
    values = {"rows": [{"items": [1, 2, 3, 4, 5]}, {"items": [6, 7, 8, 9, 10]}]}

    result = get_data_structure(Data(data=values), include_sample_values=True, max_sample_size=max_sample_size)

    expected = [{"items": [1, 2, 3, 4, 5][:max_sample_size]}, {"items": [6, 7, 8, 9, 10][:max_sample_size]}]
    assert result["samples"] == {"rows": expected[:max_sample_size]}
