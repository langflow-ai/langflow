import pytest
from lfx.components.processing.data_operations import DataOperationsComponent
from lfx.components.processing.operations import OperationsComponent
from lfx.schema.data import Data


@pytest.mark.parametrize("component_type", [OperationsComponent, DataOperationsComponent])
@pytest.mark.parametrize("value", ["hello", [1, 2], 0, False, None, {"nested": 1}, {}])
@pytest.mark.parametrize("existing", [False, True])
def test_append_update_preserves_business_data_key(component_type, value, existing):
    """Appending or replacing data must not bind to a Data constructor parameter."""
    payload = {"before": 1}
    if existing:
        payload["data"] = "old"
    original = Data(data=payload)
    field = "operation" if component_type is OperationsComponent else "operations"
    component = component_type(
        data=original,
        append_update_data={"data": value},
        **{field: [{"name": "Append or Update"}]},
    )
    assert component.as_data().data == {"before": 1, "data": value}
    assert original.data == payload


@pytest.mark.parametrize("component_type", [OperationsComponent, DataOperationsComponent])
def test_append_update_preserves_constructor_named_payload_keys(component_type):
    """Other Data field names remain business fields instead of configuring the result."""
    component = component_type(
        data=Data(data={"before": 1}),
        append_update_data={"text_key": "custom", "default_value": "fallback", "custom": "content"},
    )
    result = component.append_update()
    assert result.data == {
        "before": 1,
        "text_key": "custom",
        "default_value": "fallback",
        "custom": "content",
    }
    assert result.text_key == "text"
    assert result.default_value == ""


@pytest.mark.parametrize("component_type", [OperationsComponent, DataOperationsComponent])
def test_append_update_ordinary_fields_and_single_item_list(component_type):
    """Preserve normal updates and the supported list-wrapped single input."""
    component = component_type(data=[Data(data={"before": 1})], append_update_data={"before": 2, "new": False})
    assert component.append_update().data == {"before": 2, "new": False}


@pytest.mark.parametrize("component_type", [OperationsComponent, DataOperationsComponent])
def test_append_update_still_rejects_multiple_inputs(component_type):
    """The existing single-input validation remains unchanged."""
    component = component_type(data=[Data(data={"a": 1}), Data(data={"b": 2})], append_update_data={})
    with pytest.raises(ValueError, match="not supported for multiple"):
        component.append_update()
