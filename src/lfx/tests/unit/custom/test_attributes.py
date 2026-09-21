from lfx.custom.attributes import ATTR_FUNC_MAPPING, getattr_return_list_of_str


def test_list_of_str_keeps_list_items_as_strings():
    assert getattr_return_list_of_str(["processing.Operations", 1]) == ["processing.Operations", "1"]


def test_list_of_str_wraps_a_bare_string():
    # ``replacement = "category.Name"`` is a common slip for a one-item list.
    # Dropping it would hide the legacy banner's replacement hint.
    assert getattr_return_list_of_str("models_and_agents.Agent") == ["models_and_agents.Agent"]


def test_list_of_str_returns_empty_for_missing_values():
    assert getattr_return_list_of_str(None) == []
    assert getattr_return_list_of_str("") == []


def test_replacement_attribute_accepts_a_bare_string():
    assert ATTR_FUNC_MAPPING["replacement"]("amazon.AmazonBedrockConverseModel") == [
        "amazon.AmazonBedrockConverseModel"
    ]
