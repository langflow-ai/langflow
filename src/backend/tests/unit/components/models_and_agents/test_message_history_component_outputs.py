from lfx.components.models_and_agents.memory import MemoryComponent


def test_message_history_update_outputs_sets_types_and_selected_for_retrieve_mode():
    component = MemoryComponent()

    node = {"outputs": []}
    updated = component.update_outputs(node, field_name="mode", field_value="Retrieve")

    outputs = updated["outputs"]
    assert len(outputs) == 2

    by_name = {o.name: o for o in outputs}

    assert by_name["messages_text"].types == ["Message"]
    assert by_name["messages_text"].selected == "Message"

    assert by_name["dataframe"].types == ["Table"]
    assert by_name["dataframe"].selected == "Table"


def test_message_history_update_outputs_sets_types_and_hidden_for_store_mode():
    component = MemoryComponent()

    node = {"outputs": []}
    updated = component.update_outputs(node, field_name="mode", field_value="Store")

    outputs = updated["outputs"]
    assert len(outputs) == 1

    output = outputs[0]
    assert output.name == "stored_messages"
    assert output.types == ["Message"]
    assert output.selected == "Message"
    assert output.hidden is True


def test_message_history_update_outputs_ignores_non_mode_field_name():
    component = MemoryComponent()

    sentinel = object()
    node = {"outputs": [sentinel]}

    updated = component.update_outputs(node, field_name="not_mode", field_value="Retrieve")

    assert updated is node
    assert updated["outputs"] == [sentinel]


def test_message_history_update_outputs_clears_outputs_for_unexpected_mode_value():
    component = MemoryComponent()

    sentinel = object()
    node = {"outputs": [sentinel]}

    updated = component.update_outputs(node, field_name="mode", field_value="Delete")

    assert updated is node
    assert updated["outputs"] == []


def test_message_history_update_outputs_overwrites_preexisting_outputs_for_retrieve_mode():
    component = MemoryComponent()

    sentinel = object()
    node = {"outputs": [sentinel]}

    updated = component.update_outputs(node, field_name="mode", field_value="Retrieve")

    outputs = updated["outputs"]
    assert len(outputs) == 2
    assert sentinel not in outputs
