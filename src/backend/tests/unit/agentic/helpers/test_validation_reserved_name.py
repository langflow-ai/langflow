"""Reject generated component code that uses the reserved synthetic Tool sentinel.

Defense-in-depth on top of the runtime ComponentToolkit fix.

Production failure (2026-05-27): the assistant produced a
``RandomMenuItemComponent`` whose ``outputs`` listed
``Output(name="component_as_tool", method="get_random_menu_item",
tool_mode=True)``. ``component_as_tool`` is the name of the synthetic
output the wiring layer adds when a component is flipped to Tool Mode;
the runtime ``ComponentToolkit._should_skip_output`` filter dropped
that user output as if it were the synthetic, leaving the agent with
zero tools. The runtime is now defensive (the filter is precise),
but the cleanest fix is to reject the bad code at GENERATION time so
the retry loop produces a correctly named output instead of relying on
runtime tolerance.

These tests pin the validation contract — the retry loop's error
matcher relies on the exact phrase ``reserved`` so it can route the
error to the most targeted corrective prompt instead of asking the LLM
to debug a generic ValidationError.
"""

from __future__ import annotations

from langflow.agentic.helpers.validation import validate_component_code

_RESERVED_NAME_CODE = (
    "from lfx.custom import Component\n"
    "from lfx.io import MultilineInput, Output\n"
    "from lfx.schema import Message\n"
    "\n"
    "class RandomMenuItemComponent(Component):\n"
    "    display_name = 'Random Menu Item'\n"
    "    description = 'Returns a random menu item.'\n"
    "    inputs = [MultilineInput(name='menu_items', display_name='Menu', value='a\\nb')]\n"
    "    outputs = [\n"
    "        Output(\n"
    "            name='component_as_tool',\n"
    "            display_name='Random Menu Item Tool',\n"
    "            method='get_random_menu_item',\n"
    "            tool_mode=True,\n"
    "        ),\n"
    "    ]\n"
    "    def get_random_menu_item(self) -> Message:\n"
    "        return Message(text='Caipirinha')\n"
)

_RESERVED_METHOD_CODE = (
    "from lfx.custom import Component\n"
    "from lfx.io import Output\n"
    "from lfx.schema import Message\n"
    "\n"
    "class BadMethod(Component):\n"
    "    inputs = []\n"
    "    outputs = [Output(name='result', display_name='X', method='to_toolkit')]\n"
    "    def to_toolkit(self) -> Message:\n"
    "        return Message(text='oops')\n"
)

_GOOD_CODE = (
    "from lfx.custom import Component\n"
    "from lfx.io import MultilineInput, Output\n"
    "from lfx.schema import Message\n"
    "\n"
    "class RandomMenuItem(Component):\n"
    "    display_name = 'Random Menu Item'\n"
    "    description = 'Returns a random menu item.'\n"
    "    inputs = [MultilineInput(name='menu_items', display_name='Menu', value='a\\nb')]\n"
    "    outputs = [\n"
    "        Output(name='item', display_name='Item', method='get_random_menu_item', tool_mode=True),\n"
    "    ]\n"
    "    def get_random_menu_item(self) -> Message:\n"
    "        return Message(text='Caipirinha')\n"
)


class TestRejectReservedOutputName:
    def test_should_reject_output_name_component_as_tool(self):
        result = validate_component_code(_RESERVED_NAME_CODE)
        assert result.is_valid is False, (
            "Validation must reject the reserved output name `component_as_tool` so "
            "the generator's retry loop can ask the LLM to pick a real name instead "
            "of producing a tool that silently fails to wire."
        )
        assert "component_as_tool" in (result.error or ""), (
            "Error message must mention the offending name so the retry prompt can "
            f"correct it precisely. Got: {result.error!r}"
        )
        assert "reserved" in (result.error or "").lower(), (
            "Error must call the name `reserved` so the retry prompt's pattern "
            f"matcher routes to the targeted correction. Got: {result.error!r}"
        )

    def test_should_reject_method_to_toolkit(self):
        result = validate_component_code(_RESERVED_METHOD_CODE)
        assert result.is_valid is False, (
            "`method='to_toolkit'` is the synthetic-tool method that the "
            "Component base provides. Using it as a user-defined output method "
            "shadows the synthetic and breaks tool exposure."
        )
        assert "to_toolkit" in (result.error or ""), result.error

    def test_should_accept_well_named_output(self):
        result = validate_component_code(_GOOD_CODE)
        assert result.is_valid is True, f"Well-named component rejected: {result.error!r}"
        assert result.class_name == "RandomMenuItem"
