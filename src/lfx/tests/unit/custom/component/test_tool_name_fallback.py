"""Generated custom components must produce tools with meaningful names.

Production failure (user video, 2026-05-27): the assistant generates a
custom component (e.g. ``RandomMenuItem``) and wires it to an Agent as a
tool. The agent receives the tool, but the LLM doesn't reliably call it
because the tool name is the OUTPUT METHOD name. When the LLM-generated
code uses a generic method name like ``output``, ``process``,
``build_output``, ``run``, or ``execute`` (very common — the scaffold
example in the prompt uses ``build_result``/``output``), the tool name
becomes ``output``/``process``/etc., which carries no semantic signal
about what the tool does. The LLM then refuses to call it or calls it
with wrong intent.

Fix: when a single-output component uses a generic method name, derive
the tool name from the component's class name (snake_case) instead. The
component class name IS the user's stated intent (``RandomMenuItem``,
``DrinkPrice``), so it is always more meaningful than ``output``.

Components with multiple outputs or with descriptive method names are
left alone — the existing behavior is correct there.
"""

from __future__ import annotations

import pytest
from lfx.base.tools.component_tool import ComponentToolkit
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MessageTextInput
from lfx.io import Output
from lfx.schema.message import Message

# --- Test components ---------------------------------------------------


class RandomMenuItem(Component):
    """Mirrors the user's failing case: no inputs, generic method name (``output``).

    The class name carries all the semantic signal.
    """

    display_name = "RandomMenuItem"
    description = "Returns a random menu item from the bar."
    name = "RandomMenuItem"

    inputs = []

    outputs = [
        Output(display_name="Item", name="item", method="output"),
    ]

    def output(self) -> Message:
        return Message(text="Caipirinha")


class DrinkPrice(Component):
    """LLM-generated component with the other common generic method name (``process``).

    Has one tool_mode input — the schema is fine, only the tool name is
    uninformative.
    """

    display_name = "DrinkPrice"
    description = "Returns the price of a drink."
    name = "DrinkPrice"

    inputs = [
        MessageTextInput(name="drink", display_name="Drink", tool_mode=True),
    ]

    outputs = [
        Output(display_name="Price", name="price", method="process"),
    ]

    def process(self) -> Message:
        return Message(text="15")


class GetWeather(Component):
    """LLM-generated component that DID name its method well (``get_forecast``).

    The fallback must NOT touch this — the method name is the
    authoritative tool name when it is descriptive.
    """

    display_name = "GetWeather"
    description = "Returns the weather forecast for a city."
    name = "GetWeather"

    inputs = [
        MessageTextInput(name="city", display_name="City", tool_mode=True),
    ]

    outputs = [
        Output(display_name="Forecast", name="forecast", method="get_forecast"),
    ]

    def get_forecast(self) -> Message:
        return Message(text="sunny")


class MultiOutputComponent(Component):
    """A multi-output component with generic-named methods.

    The fallback must NOT apply here — collapsing both tools to the same
    class-derived name would shadow one of them, which is worse than
    uninformative names. Existing behavior (method-name → tool-name) is
    correct.
    """

    display_name = "MultiOutputComponent"
    description = "Two outputs, both with generic method names."
    name = "MultiOutputComponent"

    inputs = []

    outputs = [
        Output(display_name="One", name="one", method="output"),
        Output(display_name="Two", name="two", method="process"),
    ]

    def output(self) -> Message:
        return Message(text="one")

    def process(self) -> Message:
        return Message(text="two")


# --- Tests -------------------------------------------------------------


@pytest.mark.parametrize(
    ("component_cls", "expected_tool_name"),
    [
        (RandomMenuItem, "random_menu_item"),
        (DrinkPrice, "drink_price"),
    ],
)
def test_generic_method_name_falls_back_to_class_name(component_cls, expected_tool_name):
    """Single-output components with a generic method name expose a class-derived tool name.

    Fix for the production "agent can't use my custom tool" failure.
    """
    toolkit = ComponentToolkit(component=component_cls())
    tools = toolkit.get_tools()

    assert len(tools) == 1
    assert tools[0].name == expected_tool_name, (
        f"Tool for {component_cls.__name__} should be named "
        f"{expected_tool_name!r} (derived from class name); "
        f"got {tools[0].name!r}. The generic method name carries no "
        "semantic signal for the LLM."
    )


def test_meaningful_method_name_is_preserved():
    """Descriptive method names must NOT be rewritten by the fallback.

    Overriding them would discard intent the LLM (or component author)
    deliberately encoded.
    """
    toolkit = ComponentToolkit(component=GetWeather())
    tools = toolkit.get_tools()

    assert len(tools) == 1
    assert tools[0].name == "get_forecast", (
        f"GetWeather.get_forecast should map to tool 'get_forecast'; "
        f"got {tools[0].name!r}. The fallback overrode a perfectly good name."
    )


def test_multi_output_component_keeps_method_names():
    """The fallback must only apply to single-output components.

    For multi-output components, collapsing several tools to the same
    class-derived name would shadow one of them, which is a regression.
    """
    toolkit = ComponentToolkit(component=MultiOutputComponent())
    tools = toolkit.get_tools()

    names = {t.name for t in tools}
    assert names == {"output", "process"}, (
        f"Multi-output component must keep distinct method-derived names "
        f"to avoid tool shadowing; got {names}. The fallback must be gated "
        "on `len(outputs) == 1`."
    )


@pytest.mark.parametrize(
    ("class_name", "expected_snake"),
    [
        ("RandomMenuItem", "random_menu_item"),
        ("DrinkPrice", "drink_price"),
        ("HTTPClient", "http_client"),
        ("S3Bucket", "s3_bucket"),
        ("Already_snake", "already_snake"),
        ("MyXMLParser", "my_xml_parser"),
    ],
)
def test_class_to_tool_name_handles_common_casing(class_name, expected_snake):
    """CamelCase→snake_case helper handles acronyms and existing underscores correctly.

    These patterns appear in real LLM-generated components and a bad
    conversion produces tool names that are even less helpful than the
    generic ones.
    """
    from lfx.base.tools.component_tool import _class_name_to_tool_name

    assert _class_name_to_tool_name(class_name) == expected_snake


# --- The REAL production bug --------------------------------------------


class UserDeclaredReservedNameComponent(Component):
    """The component the user actually ran into (2026-05-27).

    The LLM declared ``Output(name="component_as_tool", ...)``. Reproduces
    the ZERO-TOOL failure: the reserved-name filter in
    ``ComponentToolkit._should_skip_output`` was intended only to skip the
    synthetic output that ``to_toolkit()`` adds — but the same filter also
    drops user-declared outputs that happen to share the name, so the
    agent receives an empty tool list and silently does nothing.

    The whole point of the user wiring this component to the agent was to
    give it that one tool. Returning [] is wrong; the user-declared output
    must be exposed as a normal tool (with a method-derived or class-derived
    name).
    """

    display_name = "Random Menu Item"
    description = "Returns a random item from the bar menu."
    name = "UserDeclaredReservedNameComponent"

    inputs = [
        MessageTextInput(name="menu", display_name="Menu", tool_mode=True),
    ]

    outputs = [
        Output(
            name="component_as_tool",  # the reserved name — LLM hallucinated this
            display_name="Random Menu Item Tool",
            method="get_random_menu_item",
            tool_mode=True,
        ),
    ]

    def get_random_menu_item(self) -> Message:
        return Message(text="Caipirinha")


def test_user_declared_reserved_output_name_still_produces_a_tool():
    """The CORE production bug: user-declared reserved-name output must still produce a tool.

    With the fix in place, ``ComponentToolkit.get_tools()`` must still emit
    a usable tool for the user's component even when the LLM-generated
    code declared the output with the reserved name ``component_as_tool``.
    Otherwise the agent receives an empty list and the wired tool silently
    does nothing — which is exactly the failure the user reported across
    three attempts in the production video.
    """
    toolkit = ComponentToolkit(component=UserDeclaredReservedNameComponent())
    tools = toolkit.get_tools()

    assert len(tools) == 1, (
        "A user-declared output named 'component_as_tool' must still produce a tool. "
        f"Got {len(tools)} tool(s). The reserved-name skip filter in "
        "_should_skip_output is over-broad — it must only drop the SYNTHETIC "
        "output that to_toolkit() adds, not user-declared outputs that share the name."
    )
    # The resulting tool should be invocable and named meaningfully.
    tool = tools[0]
    assert tool.name in {"get_random_menu_item", "user_declared_reserved_name_component"}, (
        f"Tool name should be derived from method or class, got {tool.name!r}"
    )
    # And it should actually be callable end-to-end.
    out = tool.invoke({"menu": "ignored"})
    assert "Caipirinha" in str(out)
