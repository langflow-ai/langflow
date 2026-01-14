from lfx.inputs.inputs import PromptInput


def test_prompt_input_has_references_field():
    inp = PromptInput(name="test", value="Hello @Node.output")
    assert hasattr(inp, "has_references")
    inp.has_references = True
    assert inp.has_references is True


def test_prompt_input_reference_in_dict():
    inp = PromptInput(name="test", value="Prompt with {{var}} and @Node.output", has_references=True)
    d = inp.to_dict()
    assert d.get("has_references") is True
