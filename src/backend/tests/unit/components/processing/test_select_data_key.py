import pytest
from lfx.components.processing.data_operations import DataOperationsComponent
from lfx.components.processing.operations import OperationsComponent
from lfx.schema.data import Data


@pytest.mark.parametrize("component_type", [OperationsComponent, DataOperationsComponent])
@pytest.mark.parametrize("value", ["hello", [1, 2], 0, False, None])
def test_select_data_key_preserves_non_dictionary_values(component_type, value):
    """The payload key named data must support the same values as other keys."""
    component = component_type(data=Data(data={"data": value}), select_keys_input=["data"])
    assert component.select_keys().data == {"data": value}


@pytest.mark.parametrize("component_type", [OperationsComponent, DataOperationsComponent])
@pytest.mark.parametrize("value", [{"nested": 1}, {}])
def test_select_data_key_keeps_dictionary_unwrapping(component_type, value):
    """Retain the existing inner-dictionary output for compatibility."""
    component = component_type(data=Data(data={"data": value}), select_keys_input=["data"])
    assert component.select_keys().data == value


@pytest.mark.parametrize("component_type", [OperationsComponent, DataOperationsComponent])
def test_select_data_key_with_other_keys_preserves_wrapper(component_type):
    """Multi-key selections do not implicitly unwrap a payload field."""
    payload = {"data": "hello", "other": 2}
    component = component_type(data=Data(data=payload), select_keys_input=["data", "other"])
    assert component.select_keys().data == payload


@pytest.mark.parametrize("component_type", [OperationsComponent, DataOperationsComponent])
def test_select_missing_data_key_reports_missing_key(component_type):
    """Missing payload keys use the ordinary actionable selection error."""
    component = component_type(data=Data(data={"other": 2}), select_keys_input=["data"])
    with pytest.raises(ValueError, match="Select key not found"):
        component.select_keys()


@pytest.mark.parametrize("component_type", [OperationsComponent, DataOperationsComponent])
def test_select_data_key_through_component_output(component_type):
    """The configured output dispatch must preserve a scalar data field."""
    field = "operation" if component_type is OperationsComponent else "operations"
    component = component_type(
        data=Data(data={"data": "hello"}),
        select_keys_input=["data"],
        **{field: [{"name": "Select Keys"}]},
    )
    assert component.as_data().data == {"data": "hello"}


@pytest.mark.parametrize("component_type", [OperationsComponent, DataOperationsComponent])
def test_select_ordinary_key_is_unchanged(component_type):
    """Unrelated keys retain the original selection contract."""
    component = component_type(data=Data(data={"value": 0, "other": 1}), select_keys_input=["value"])
    assert component.select_keys().data == {"value": 0}
