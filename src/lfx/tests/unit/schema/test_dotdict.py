from lfx.schema.dotdict import dotdict


def test_create_dotdict():
    """Test creating a dotdict from a regular dict."""
    sample_dict = {"name": "test", "value": 123, "nested": {"key": "value"}}

    dd = dotdict(sample_dict)

    # Test dot notation access
    assert dd.name == "test"
    assert dd.value == 123
    assert dd.nested.key == "value"

    # Test dict-style access still works
    assert dd["name"] == "test"
    assert dd["value"] == 123
    assert dd["nested"]["key"] == "value"


def test_dotdict_with_complex_structure():
    """Test dotdict with more complex nested structure."""
    sample_input = {
        "_input_type": "MultilineInput",
        "advanced": False,
        "display_name": "Chat Input - Text",
        "dynamic": False,
        "info": "Message to be passed as input.",
        "input_types": ["Message"],
        "list": False,
        "load_from_db": False,
        "multiline": True,
        "name": "ChatInput-xNZ0a|input_value",
        "placeholder": "",
        "required": False,
        "show": True,
        "title_case": False,
        "tool_mode": True,
        "trace_as_input": True,
        "trace_as_metadata": True,
        "type": "str",
        "value": "add 1+1",
    }

    dd = dotdict(sample_input)

    # Test accessing various fields
    assert dd["_input_type"] == "MultilineInput"
    assert dd.advanced is False
    assert dd.display_name == "Chat Input - Text"
    assert dd.input_types == ["Message"]
    assert dd.value == "add 1+1"


def test_dotdict_list_conversion():
    """Test converting a list of dicts to dotdicts."""
    sample_list = [{"name": "item1", "value": 1}, {"name": "item2", "value": 2}, {"name": "item3", "value": 3}]

    # Convert list of dicts to list of dotdicts
    dotdict_list = [dotdict(item) for item in sample_list]

    assert len(dotdict_list) == 3
    assert dotdict_list[0].name == "item1"
    assert dotdict_list[1].value == 2
    assert dotdict_list[2].name == "item3"
