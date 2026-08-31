"""Test for GitHub issue #8791: Race condition when component-tool is invoked concurrently.

When an Agent invokes the same component-based tool multiple times concurrently,
the same component instance is reused, causing inputs to be overwritten between
concurrent invocations (data corruption).
"""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

from lfx.base.tools.component_tool import ComponentToolkit, send_message_noop
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import DataInput, MessageTextInput
from lfx.io import Output
from lfx.schema.data import Data
from lfx.schema.message import Message


class SlowLabelComponent(Component):
    """Test component that simulates a tool with processing delay.

    Records input values before and after a delay to detect
    if concurrent invocations overwrite each other's inputs.
    """

    display_name = "Slow Label Tool"
    description = "Adds a label to a product with simulated delay."
    name = "SlowLabelComponent"

    inputs = [
        MessageTextInput(name="product_id", display_name="Product ID", tool_mode=True),
        MessageTextInput(name="label", display_name="Label", tool_mode=True),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="process"),
    ]

    def process(self) -> Data:
        import time

        captured_id = self.product_id
        captured_label = self.label
        time.sleep(0.2)
        return Data(
            data={
                "product_id_before": captured_id,
                "label_before": captured_label,
                "product_id_after": self.product_id,
                "label_after": self.label,
            }
        )


def test_should_isolate_inputs_when_tool_invoked_concurrently():
    """Bug #8791: concurrent tool invocations must not share mutable state.

    GIVEN: A component converted to a StructuredTool via ComponentToolkit
    WHEN:  The tool is invoked concurrently with different inputs
    THEN:  Each invocation must see its own inputs (no cross-contamination)
    """
    # Arrange
    component = SlowLabelComponent()
    toolkit = ComponentToolkit(component=component)
    tools = toolkit.get_tools()
    assert len(tools) == 1
    tool = tools[0]

    results = []

    def invoke_tool(product_id: str, label: str) -> None:
        result = tool.invoke({"product_id": product_id, "label": label})
        results.append(result)

    # Act - invoke the same tool concurrently with different inputs
    with ThreadPoolExecutor(max_workers=2) as executor:
        future1 = executor.submit(invoke_tool, "PROD-001", "Electronics")
        future2 = executor.submit(invoke_tool, "PROD-002", "Clothing")
        future1.result()
        future2.result()

    # Assert - each invocation must retain its own inputs throughout execution
    assert len(results) == 2

    for result in results:
        # Inputs captured before and after the delay must be identical
        assert result["product_id_before"] == result["product_id_after"], (
            f"product_id changed during execution: '{result['product_id_before']}' -> '{result['product_id_after']}'"
        )
        assert result["label_before"] == result["label_after"], (
            f"label changed during execution: '{result['label_before']}' -> '{result['label_after']}'"
        )

    # Both products must have been processed (not duplicated)
    product_ids = {r["product_id_before"] for r in results}
    assert product_ids == {"PROD-001", "PROD-002"}, (
        f"Expected both products to be processed independently, got: {product_ids}"
    )


def test_deepcopy_with_non_picklable_state():
    """Deepcopy must not fail when the component carries non-picklable objects.

    Real components receive services (e.g. _tracing_service) that hold
    threading.RLock instances.  __deepcopy__ must handle these gracefully.
    """
    component = SlowLabelComponent(_tracing_service=_FakeServiceWithLock())
    # Must not raise "cannot pickle '_thread.RLock' object"
    clone = deepcopy(component)

    # The clone must be a distinct object
    assert clone is not component
    # The non-picklable service should be shared (shallow-copied), not duplicated
    assert clone._tracing_service is component._tracing_service  # type: ignore[attr-defined]


def test_should_isolate_inputs_when_component_has_non_picklable_state():
    """End-to-end: concurrent tool invocation must work even with non-picklable state.

    Combines both bugs: race condition (#8791) + RLock deepcopy failure.
    The component has a _tracing_service with RLock AND is invoked concurrently.
    """
    # Arrange
    component = SlowLabelComponent(_tracing_service=_FakeServiceWithLock())
    toolkit = ComponentToolkit(component=component)
    tools = toolkit.get_tools()
    tool = tools[0]

    results = []

    def invoke_tool(product_id: str, label: str) -> None:
        result = tool.invoke({"product_id": product_id, "label": label})
        results.append(result)

    # Act - invoke concurrently with a component that has non-picklable state
    with ThreadPoolExecutor(max_workers=2) as executor:
        future1 = executor.submit(invoke_tool, "P1", "LabelA")
        future2 = executor.submit(invoke_tool, "P2", "LabelB")
        future1.result()
        future2.result()

    # Assert - no race condition AND no pickle error
    assert len(results) == 2
    for result in results:
        assert result["product_id_before"] == result["product_id_after"]
        assert result["label_before"] == result["label_after"]

    product_ids = {r["product_id_before"] for r in results}
    assert product_ids == {"P1", "P2"}


def test_deepcopy_with_non_picklable_input_value():
    """Deepcopy must not fail when an input value is non-picklable.

    Some components receive complex objects (e.g. LangChain models/clients)
    in their inputs that hold threading.RLock instances.
    """

    class MockComponentWithLockValue(Component):
        inputs = [DataInput(name="input_with_lock")]

        def build(self):
            return "ok"

    component = MockComponentWithLockValue()
    lock_val = _FakeServiceWithLock()
    component.set(input_with_lock=lock_val)

    # Must not raise "cannot pickle '_thread.RLock' object"
    clone = deepcopy(component)

    assert clone is not component
    # The non-picklable value should be shared (shallow-copied fallback)
    assert clone.input_with_lock is lock_val


def test_should_isolate_inputs_when_input_has_non_picklable_value():
    """End-to-end: concurrent tool invocation must work even with non-picklable input values.

    Verified that the tool isolation still works when one of the inputs
    carries a non-picklable object (forcing the shallow-copy fallback in deepcopy).
    """

    class SlowToolWithLock(SlowLabelComponent):
        inputs = [
            *SlowLabelComponent.inputs,
            DataInput(name="lock_input", tool_mode=True),
        ]

    # Arrange
    lock_val = _FakeServiceWithLock()
    component = SlowToolWithLock()
    component.set(lock_input=lock_val)  # Set the non-picklable value on the component
    toolkit = ComponentToolkit(component=component)
    tools = toolkit.get_tools()
    tool = tools[0]

    results = []

    def invoke_tool(product_id: str, label: str) -> None:
        # We don't pass lock_input here to avoid Pydantic validation of tool arguments
        # The deepcopy(component) inside tool.invoke() will still encounter lock_val
        result = tool.invoke({"product_id": product_id, "label": label})
        results.append(result)

    # Act
    with ThreadPoolExecutor(max_workers=2) as executor:
        future1 = executor.submit(invoke_tool, "P1", "L1")
        future2 = executor.submit(invoke_tool, "P2", "L2")
        future1.result()
        future2.result()

    # Assert
    assert len(results) == 2
    for result in results:
        assert result["product_id_before"] == result["product_id_after"]
        assert result["label_before"] == result["label_after"]

    product_ids = {r["product_id_before"] for r in results}
    assert product_ids == {"P1", "P2"}


def test_deepcopy_preserves_component_reference_cycles():
    """Component.__deepcopy__ must register itself in memo before copying _components.

    A feedback loop links components through _components in a cycle (A -> B -> A).
    If the memo entry is set only after the recursive deepcopy calls, the cycle is
    duplicated into a second copy instead of preserved.
    """
    a = SlowLabelComponent(_id="a")
    b = SlowLabelComponent(_id="b")
    a._components = [b]
    b._components = [a]

    a_copy = deepcopy(a)
    b_copy = a_copy._components[0]

    # The cycle must round-trip back to the same copied objects.
    assert b_copy._components[0] is a_copy
    # And the copies must be distinct from the originals.
    assert a_copy is not a
    assert b_copy is not b


def test_should_keep_send_message_when_sync_tool_calls_overlap():
    """Bug #14088: an overlapping tool call must not leave send_message replaced.

    GIVEN: A component-backed tool whose invocations overlap in time
    WHEN:  They interleave as A starts, B starts, A finishes, B finishes
    THEN:  The shared component still carries its original send_message
    """
    # Arrange - gates let the test drive the interleaving instead of racing for it
    gates = {"a": threading.Event(), "b": threading.Event()}
    entered = {"a": threading.Event(), "b": threading.Event()}

    class GatedComponent(Component):
        display_name = "Gated Tool"
        description = "Blocks inside the tool call until its gate is released."
        name = "GatedComponent"

        inputs = [MessageTextInput(name="tag", display_name="Tag", tool_mode=True)]
        outputs = [Output(display_name="Result", name="result", method="process")]

        def process(self) -> Data:
            entered[self.tag].set()
            gates[self.tag].wait(timeout=5)
            return Data(data={"tag": self.tag})

    component = GatedComponent()
    original_send_message = component.send_message
    tool = ComponentToolkit(component=component).get_tools()[0]

    # Act
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(tool.invoke, {"tag": "a"})
        assert entered["a"].wait(timeout=5)
        second = executor.submit(tool.invoke, {"tag": "b"})
        assert entered["b"].wait(timeout=5)

        gates["a"].set()
        first.result(timeout=5)
        gates["b"].set()
        second.result(timeout=5)

    # Assert
    assert component.send_message is not send_message_noop, "send_message was left as the tool-mode no-op"
    assert component.send_message == original_send_message


async def test_should_keep_send_message_when_async_tool_calls_overlap():
    """Bug #14088, async wrapper: same interleaving, same guarantee.

    GIVEN: A component-backed tool with an async output method
    WHEN:  Two calls interleave as A starts, B starts, A finishes, B finishes
    THEN:  The shared component still carries its original send_message
    """
    # Arrange
    gates = {"a": asyncio.Event(), "b": asyncio.Event()}
    entered = {"a": asyncio.Event(), "b": asyncio.Event()}

    class AsyncGatedComponent(Component):
        display_name = "Async Gated Tool"
        description = "Blocks inside the tool call until its gate is released."
        name = "AsyncGatedComponent"

        inputs = [MessageTextInput(name="tag", display_name="Tag", tool_mode=True)]
        outputs = [Output(display_name="Result", name="result", method="process")]

        async def process(self) -> Data:
            entered[self.tag].set()
            await asyncio.wait_for(gates[self.tag].wait(), timeout=5)
            return Data(data={"tag": self.tag})

    component = AsyncGatedComponent()
    original_send_message = component.send_message
    tool = ComponentToolkit(component=component).get_tools()[0]

    # Act
    first = asyncio.create_task(tool.ainvoke({"tag": "a"}))
    await asyncio.wait_for(entered["a"].wait(), timeout=5)
    second = asyncio.create_task(tool.ainvoke({"tag": "b"}))
    await asyncio.wait_for(entered["b"].wait(), timeout=5)

    gates["a"].set()
    await asyncio.wait_for(first, timeout=5)
    gates["b"].set()
    await asyncio.wait_for(second, timeout=5)

    # Assert
    assert component.send_message is not send_message_noop, "send_message was left as the tool-mode no-op"
    assert component.send_message == original_send_message


async def test_should_leave_message_delivery_unchanged_when_running_as_tool():
    """A tool call must not patch send_message anywhere - not on the copy, not on the shared component.

    Message suppression during tool runs has been inactive since #11994 and reviving it
    is a user-visible change tracked separately. This pins the current behavior so it
    cannot come back by accident.

    GIVEN: A component whose output method sends a message while running as a tool
    WHEN:  The tool is invoked
    THEN:  The message reaches the component's own send_message, and the shared component
           still holds that same method afterwards
    """
    # Arrange - delivered records every message that reaches the component's send_message
    delivered: list[str] = []

    class MessagingComponent(Component):
        display_name = "Messaging Tool"
        description = "Sends a message while running."
        name = "MessagingComponent"

        inputs = [MessageTextInput(name="tag", display_name="Tag", tool_mode=True)]
        outputs = [Output(display_name="Result", name="result", method="process")]

        async def send_message(self, message: Message, *_args, **_kwargs):
            delivered.append(message.text)
            return message

        async def process(self) -> Data:
            echoed = await self.send_message(Message(text=f"message from {self.tag}"))
            return Data(data={"tag": self.tag, "echoed": echoed.text})

    component = MessagingComponent()
    original_send_message = component.send_message
    tool = ComponentToolkit(component=component).get_tools()[0]

    # Act
    result = await tool.ainvoke({"tag": "a"})

    # Assert - the copy ran with the component's own send_message, not with a no-op
    assert delivered == ["message from a"]
    assert result["echoed"] == "message from a"
    # And the shared component was never patched
    assert component.send_message == original_send_message
    assert component.send_message is not send_message_noop


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeServiceWithLock:
    """Mimics a service that holds a threading.RLock (like ServiceManager)."""

    def __init__(self):
        self._lock = threading.RLock()


class _KwOnlyNew:
    """Mimics a Langfuse-like object whose __new__ has required keyword-only args (not deep-copyable)."""

    def __new__(cls, *, required_a, required_b):
        instance = super().__new__(cls)
        instance.required_a = required_a
        instance.required_b = required_b
        return instance


def test_deepcopy_with_non_deepcopyable_output_value():
    """Deepcopy must not fail when an output.value holds a non-deepcopyable object.

    Regression: a Langfuse handler attached via tracing callbacks lands in an
    output.value; its __new__ needs keyword-only args, so deepcopy of the
    component-as-tool raised and failed every tool call. The fallback must share it.
    """
    component = SlowLabelComponent()
    undeepcopyable = _KwOnlyNew(required_a=1, required_b=2)
    component._outputs_map["result"].value = undeepcopyable

    clone = deepcopy(component)

    assert clone is not component
    assert clone._outputs_map["result"].value is undeepcopyable
