from lfx.inputs.inputs import MessageTextInput, MultilineInput, StrInput


def test_str_input_has_references_field():
    inp = StrInput(name="test", value="Hello @Node.output")
    assert hasattr(inp, "has_references")
    inp.has_references = True
    assert inp.has_references is True


def test_message_text_input_has_references_field():
    inp = MessageTextInput(name="test", value="Hello @Node.output")
    assert hasattr(inp, "has_references")


def test_multiline_input_has_references_field():
    inp = MultilineInput(name="test", value="Hello @Node.output")
    assert hasattr(inp, "has_references")


def test_str_input_reference_in_dict():
    inp = StrInput(name="test", value="Hello", has_references=True)
    d = inp.to_dict()
    assert d.get("has_references") is True
