"""An input named after a component method must fail loudly, not resolve to the method.

``Component.__getattr__`` only runs when normal attribute lookup fails, so an input named
``index`` made ``self.index`` return the inherited ``CustomComponent.index`` method instead of
the value configured on the node.
"""

import pytest
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MessageTextInput, StrInput
from lfx.schema.data import Data
from lfx.template.field.base import Output


def test_should_reject_an_input_named_after_an_inherited_method():
    class IndexInput(Component):
        inputs = [MessageTextInput(name="index", display_name="Index")]
        outputs = [Output(display_name="Result", name="result", method="build_result")]

        def build_result(self) -> Data:
            return Data(data={"index_value": self.index})

    with pytest.raises(ValueError, match=r"'index'.*Rename the input"):
        IndexInput()


def test_should_reject_an_input_named_after_a_method_the_component_defines():
    class OwnMethodInput(Component):
        inputs = [StrInput(name="lookup", display_name="Lookup")]
        outputs = [Output(display_name="Result", name="result", method="lookup")]

        def lookup(self) -> Data:
            return Data(data={})

    with pytest.raises(ValueError, match="'lookup'"):
        OwnMethodInput()


@pytest.mark.parametrize("name", ["code", "flow_name", "description", "inputs"])
def test_should_accept_an_input_named_after_a_property_or_class_attribute(name):
    class NonCallableCollision(Component):
        inputs = [StrInput(name=name, display_name="Field")]
        outputs = [Output(display_name="Result", name="result", method="build_result")]

        def build_result(self) -> Data:
            return Data(data={})

    component = NonCallableCollision()

    assert name in component.list_inputs()


def test_should_resolve_a_non_colliding_input_to_its_configured_value():
    class PlainInput(Component):
        inputs = [MessageTextInput(name="row_index", display_name="Row index")]
        outputs = [Output(display_name="Result", name="result", method="build_result")]

        def build_result(self) -> Data:
            return Data(data={"row_index": self.row_index})

    component = PlainInput(row_index="configured-42")

    assert component.row_index == "configured-42"
