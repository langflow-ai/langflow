"""Test for GitHub issue #8791: Race condition when component-tool is invoked concurrently.

When an Agent invokes the same component-based tool multiple times concurrently,
the same component instance is reused, causing inputs to be overwritten between
concurrent invocations (data corruption).
"""

import threading
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

from lfx.base.tools.component_tool import ComponentToolkit
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import MessageTextInput
from lfx.io import Output
from lfx.schema.data import Data


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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeServiceWithLock:
    """Mimics a service that holds a threading.RLock (like ServiceManager)."""

    def __init__(self):
        self._lock = threading.RLock()
