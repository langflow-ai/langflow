from lfx.inputs.input_mixin import ReferenceMixin
from pydantic import BaseModel


class TestInput(ReferenceMixin, BaseModel):
    name: str
    value: str = ""


def test_reference_mixin_default_false():
    inp = TestInput(name="test")
    assert inp.has_references is False


def test_reference_mixin_set_true():
    inp = TestInput(name="test", has_references=True)
    assert inp.has_references is True


def test_reference_mixin_in_dict():
    inp = TestInput(name="test", has_references=True)
    d = inp.model_dump()
    assert "has_references" in d
    assert d["has_references"] is True


def test_reference_mixin_not_in_dict_when_false():
    inp = TestInput(name="test", has_references=False)
    d = inp.model_dump(exclude_defaults=True)
    # has_references should be excluded when False (default)
    assert "has_references" not in d or d.get("has_references") is False
