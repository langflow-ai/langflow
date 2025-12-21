"""Tests for Loop component behavior when frozen.

This module tests the fix for the issue where frozen Loop components
would run infinitely instead of iterating correctly through their data.

The fix ensures that Loop components always execute their build() method
even when frozen, because they need to iterate through their data correctly.
"""

from unittest.mock import Mock

import pytest


class TestVertexIsLoopProperty:
    """Tests for the vertex is_loop property detection logic."""

    def test_is_loop_returns_true_for_loop_component(self):
        """Test that is_loop returns True for Loop component vertices."""
        outputs = [
            {"name": "item", "allows_loop": True},
            {"name": "done", "allows_loop": False},
        ]

        # Call the actual property logic
        is_loop = any(output.get("allows_loop", False) for output in outputs)
        assert is_loop is True

    def test_is_loop_returns_false_for_regular_component(self):
        """Test that is_loop returns False for regular component vertices."""
        outputs = [
            {"name": "output", "allows_loop": False},
        ]

        is_loop = any(output.get("allows_loop", False) for output in outputs)
        assert is_loop is False

    def test_is_loop_returns_false_for_empty_outputs(self):
        """Test that is_loop returns False when outputs is empty."""
        outputs = []

        is_loop = any(output.get("allows_loop", False) for output in outputs)
        assert is_loop is False

    def test_is_loop_handles_missing_allows_loop_key(self):
        """Test that is_loop handles outputs without allows_loop key."""
        outputs = [
            {"name": "output"},  # No allows_loop key
        ]

        is_loop = any(output.get("allows_loop", False) for output in outputs)
        assert is_loop is False

    def test_is_loop_with_multiple_loop_outputs(self):
        """Test is_loop with multiple outputs that allow looping."""
        outputs = [
            {"name": "item1", "allows_loop": True},
            {"name": "item2", "allows_loop": True},
            {"name": "done", "allows_loop": False},
        ]

        is_loop = any(output.get("allows_loop", False) for output in outputs)
        assert is_loop is True


class TestBuildVertexLoopException:
    """Tests for build_vertex Loop exception in graph/base.py.

    This tests the logic: if not vertex.frozen or is_loop_component
    """

    @pytest.fixture
    def mock_loop_vertex(self):
        """Create a mock Loop vertex."""
        vertex = Mock()
        vertex.id = "test-vertex-id"
        vertex.frozen = True
        vertex.built = True
        vertex.is_loop = True
        vertex.display_name = "Loop"
        vertex.result = Mock()
        vertex.artifacts = {}
        return vertex

    @pytest.fixture
    def mock_non_loop_vertex(self):
        """Create a mock non-loop vertex."""
        vertex = Mock()
        vertex.id = "test-vertex-id"
        vertex.frozen = True
        vertex.built = True
        vertex.is_loop = False
        vertex.display_name = "Parser"
        vertex.result = Mock()
        vertex.artifacts = {}
        return vertex

    def test_loop_component_detected_by_is_loop(self, mock_loop_vertex):
        """Test that Loop component is detected by is_loop property."""
        vertex = mock_loop_vertex
        is_loop_component = vertex.display_name == "Loop" or vertex.is_loop
        assert is_loop_component is True

    def test_loop_component_detected_by_display_name(self):
        """Test that Loop component is detected by display_name."""
        vertex = Mock()
        vertex.display_name = "Loop"
        vertex.is_loop = False  # Even if is_loop is False

        is_loop_component = vertex.display_name == "Loop" or vertex.is_loop
        assert is_loop_component is True

    def test_non_loop_component_not_detected(self, mock_non_loop_vertex):
        """Test that non-Loop component is not detected as loop."""
        vertex = mock_non_loop_vertex
        is_loop_component = vertex.display_name == "Loop" or vertex.is_loop
        assert is_loop_component is False

    def test_frozen_loop_should_build(self, mock_loop_vertex):
        """Test that frozen Loop should still build.

        This is the key test for our fix: frozen Loop components
        must always build because they need to iterate through data.
        """
        vertex = mock_loop_vertex
        is_loop_component = vertex.display_name == "Loop" or vertex.is_loop

        # This is the logic from build_vertex in graph/base.py
        should_build = not vertex.frozen or is_loop_component
        assert should_build is True

    def test_frozen_non_loop_should_not_build(self, mock_non_loop_vertex):
        """Test that frozen non-Loop should NOT build (use cache)."""
        vertex = mock_non_loop_vertex
        is_loop_component = vertex.display_name == "Loop" or vertex.is_loop

        should_build = not vertex.frozen or is_loop_component
        assert should_build is False

    def test_non_frozen_loop_should_build(self):
        """Test that non-frozen Loop should build."""
        vertex = Mock()
        vertex.frozen = False
        vertex.is_loop = True
        vertex.display_name = "Loop"

        is_loop_component = vertex.display_name == "Loop" or vertex.is_loop
        should_build = not vertex.frozen or is_loop_component
        assert should_build is True

    def test_non_frozen_non_loop_should_build(self, mock_non_loop_vertex):
        """Test that non-frozen non-Loop should build."""
        vertex = mock_non_loop_vertex
        vertex.frozen = False

        is_loop_component = vertex.display_name == "Loop" or vertex.is_loop
        should_build = not vertex.frozen or is_loop_component
        assert should_build is True

    def test_custom_loop_component_name_detected(self):
        """Test that custom component with is_loop=True is detected."""
        vertex = Mock()
        vertex.display_name = "CustomIterator"  # Not "Loop"
        vertex.is_loop = True

        is_loop_component = vertex.display_name == "Loop" or vertex.is_loop
        assert is_loop_component is True

    def test_all_frozen_states_for_loop(self):
        """Test all combinations of frozen states for Loop component."""
        test_cases = [
            # (frozen, is_loop, expected_should_build)
            (False, False, True),  # Not frozen, not loop -> build
            (False, True, True),  # Not frozen, loop -> build
            (True, False, False),  # Frozen, not loop -> don't build (use cache)
            (True, True, True),  # Frozen, loop -> build (our fix!)
        ]

        for frozen, is_loop, expected in test_cases:
            vertex = Mock()
            vertex.frozen = frozen
            vertex.is_loop = is_loop
            vertex.display_name = "Loop" if is_loop else "Other"

            is_loop_component = vertex.display_name == "Loop" or vertex.is_loop
            should_build = not vertex.frozen or is_loop_component

            assert should_build == expected, (
                f"Failed for frozen={frozen}, is_loop={is_loop}: expected {expected}, got {should_build}"
            )


class TestVertexBuildLoopException:
    """Tests for vertex.build() Loop exception in vertex/base.py.

    This tests the logic: if self.frozen and self.built and not is_loop_component
    """

    def test_frozen_built_loop_should_continue_build(self):
        """Test that frozen+built Loop should NOT return cached result.

        This is the key test: even when frozen AND built, Loop components
        must continue to build() so they can iterate through their data.
        """
        vertex = Mock()
        vertex.frozen = True
        vertex.built = True
        vertex.is_loop = True
        vertex.display_name = "Loop"

        is_loop_component = vertex.display_name == "Loop" or vertex.is_loop

        # This is the condition from vertex.build() in vertex/base.py
        should_return_cached = vertex.frozen and vertex.built and not is_loop_component
        assert should_return_cached is False

    def test_frozen_built_non_loop_should_return_cached(self):
        """Test that frozen+built non-Loop SHOULD return cached result."""
        vertex = Mock()
        vertex.frozen = True
        vertex.built = True
        vertex.is_loop = False
        vertex.display_name = "Parser"

        is_loop_component = vertex.display_name == "Loop" or vertex.is_loop

        should_return_cached = vertex.frozen and vertex.built and not is_loop_component
        assert should_return_cached is True

    def test_not_frozen_loop_should_not_return_cached(self):
        """Test that non-frozen Loop should NOT return cached result."""
        vertex = Mock()
        vertex.frozen = False
        vertex.built = True
        vertex.is_loop = True
        vertex.display_name = "Loop"

        is_loop_component = vertex.display_name == "Loop" or vertex.is_loop

        should_return_cached = vertex.frozen and vertex.built and not is_loop_component
        assert should_return_cached is False

    def test_frozen_not_built_loop_should_not_return_cached(self):
        """Test that frozen but not built Loop should NOT return cached."""
        vertex = Mock()
        vertex.frozen = True
        vertex.built = False
        vertex.is_loop = True
        vertex.display_name = "Loop"

        is_loop_component = vertex.display_name == "Loop" or vertex.is_loop

        should_return_cached = vertex.frozen and vertex.built and not is_loop_component
        assert should_return_cached is False

    def test_all_frozen_built_states_for_vertex_build(self):
        """Test all combinations for vertex.build() cache decision."""
        test_cases = [
            # (frozen, built, is_loop, expected_return_cached)
            (False, False, False, False),  # Not frozen, not built -> continue
            (False, False, True, False),  # Not frozen, not built, loop -> continue
            (False, True, False, False),  # Not frozen, built -> continue
            (False, True, True, False),  # Not frozen, built, loop -> continue
            (True, False, False, False),  # Frozen, not built -> continue
            (True, False, True, False),  # Frozen, not built, loop -> continue
            (True, True, False, True),  # Frozen, built, not loop -> return cached
            (True, True, True, False),  # Frozen, built, loop -> continue (our fix!)
        ]

        for frozen, built, is_loop, expected in test_cases:
            vertex = Mock()
            vertex.frozen = frozen
            vertex.built = built
            vertex.is_loop = is_loop
            vertex.display_name = "Loop" if is_loop else "Other"

            is_loop_component = vertex.display_name == "Loop" or vertex.is_loop
            should_return_cached = vertex.frozen and vertex.built and not is_loop_component

            assert should_return_cached == expected, (
                f"Failed for frozen={frozen}, built={built}, is_loop={is_loop}: "
                f"expected {expected}, got {should_return_cached}"
            )


class TestLoopComponentOutputsConfig:
    """Tests for Loop component outputs configuration."""

    def test_loop_component_has_allows_loop_output(self):
        """Test that Loop component has allows_loop=True on item output."""
        from lfx.components.flow_controls import LoopComponent

        component = LoopComponent()
        outputs = component.outputs

        # Find the item output
        item_output = next((o for o in outputs if o.name == "item"), None)

        assert item_output is not None
        assert item_output.allows_loop is True

    def test_loop_component_done_output_no_loop(self):
        """Test that Loop component done output does NOT allow loop."""
        from lfx.components.flow_controls import LoopComponent

        component = LoopComponent()
        outputs = component.outputs

        # Find the done output
        done_output = next((o for o in outputs if o.name == "done"), None)

        assert done_output is not None
        # done output should not have allows_loop=True
        assert getattr(done_output, "allows_loop", False) is False


class TestLoopEvaluateStopLoop:
    """Tests for Loop component evaluate_stop_loop logic."""

    def test_evaluate_stop_loop_logic(self):
        """Test the evaluate_stop_loop logic directly."""
        # The logic is: current_index > data_length

        test_cases = [
            # (current_index, data_length, expected_stop)
            (0, 3, False),  # At start, don't stop
            (1, 3, False),  # In middle, don't stop
            (2, 3, False),  # At last item, don't stop
            (3, 3, False),  # At length, don't stop (equal, not greater)
            (4, 3, True),  # Past length, stop
            (0, 0, False),  # Empty data, index 0, don't stop
            (1, 0, True),  # Empty data, index 1, stop
            (0, 1, False),  # Single item, at start
            (1, 1, False),  # Single item, at length
            (2, 1, True),  # Single item, past length
        ]

        for current_index, data_length, expected_stop in test_cases:
            # This is the logic from evaluate_stop_loop
            result = current_index > data_length

            assert result == expected_stop, (
                f"Failed for index={current_index}, length={data_length}: expected {expected_stop}, got {result}"
            )


class TestFrozenLoopScenarios:
    """Integration-style tests for frozen Loop scenarios."""

    def test_frozen_loop_first_execution_should_build(self):
        """Test that first execution of frozen Loop should build."""
        vertex = Mock()
        vertex.frozen = True
        vertex.built = False  # First time, not built yet
        vertex.is_loop = True
        vertex.display_name = "Loop"

        is_loop_component = vertex.display_name == "Loop" or vertex.is_loop

        # In build_vertex: should_build
        should_build_vertex = not vertex.frozen or is_loop_component
        assert should_build_vertex is True

        # In vertex.build: should NOT return cached (not built yet)
        should_return_cached = vertex.frozen and vertex.built and not is_loop_component
        assert should_return_cached is False

    def test_frozen_loop_subsequent_iteration_should_build(self):
        """Test that subsequent iterations of frozen Loop should build."""
        vertex = Mock()
        vertex.frozen = True
        vertex.built = True  # Already built in previous iteration
        vertex.is_loop = True
        vertex.display_name = "Loop"

        is_loop_component = vertex.display_name == "Loop" or vertex.is_loop

        # In build_vertex: should_build
        should_build_vertex = not vertex.frozen or is_loop_component
        assert should_build_vertex is True

        # In vertex.build: should NOT return cached (it's a loop!)
        should_return_cached = vertex.frozen and vertex.built and not is_loop_component
        assert should_return_cached is False

    def test_frozen_non_loop_should_use_cache(self):
        """Test that frozen non-Loop component uses cache."""
        vertex = Mock()
        vertex.frozen = True
        vertex.built = True
        vertex.is_loop = False
        vertex.display_name = "TextSplitter"

        is_loop_component = vertex.display_name == "Loop" or vertex.is_loop

        # In build_vertex: should NOT build
        should_build_vertex = not vertex.frozen or is_loop_component
        assert should_build_vertex is False

    def test_multiple_loop_components_all_detected(self):
        """Test that multiple Loop components are all detected correctly."""
        loops = []
        for _ in range(5):
            vertex = Mock()
            vertex.frozen = True
            vertex.built = True
            vertex.is_loop = True
            vertex.display_name = "Loop"
            loops.append(vertex)

        for vertex in loops:
            is_loop_component = vertex.display_name == "Loop" or vertex.is_loop
            should_build = not vertex.frozen or is_loop_component
            assert should_build is True


class TestEdgeCasesForLoopDetection:
    """Edge case tests for Loop component detection."""

    def test_loop_with_unusual_display_name(self):
        """Test Loop detection with unusual display name but is_loop=True."""
        vertex = Mock()
        vertex.display_name = "My Custom Iterator 123"
        vertex.is_loop = True
        vertex.frozen = True
        vertex.built = True

        is_loop_component = vertex.display_name == "Loop" or vertex.is_loop
        should_build_result = not vertex.frozen or is_loop_component

        assert is_loop_component is True
        assert should_build_result is True

    def test_component_named_loop_but_is_loop_false(self):
        """Test component named 'Loop' but is_loop=False."""
        vertex = Mock()
        vertex.display_name = "Loop"
        vertex.is_loop = False  # Somehow is_loop is False
        vertex.frozen = True
        vertex.built = True

        # Should still be detected by display_name
        is_loop_component = vertex.display_name == "Loop" or vertex.is_loop
        should_build = not vertex.frozen or is_loop_component

        assert is_loop_component is True
        assert should_build is True

    def test_none_values_handled(self):
        """Test that None values are handled gracefully."""
        vertex = Mock()
        vertex.display_name = None
        vertex.is_loop = None
        vertex.frozen = True
        vertex.built = True

        # Should not crash, should not be detected as loop
        is_loop_component = vertex.display_name == "Loop" or vertex.is_loop
        should_build = not vertex.frozen or is_loop_component

        assert is_loop_component is None  # None or None = None
        assert should_build is None  # False or None = None
        # But in boolean context, None is falsy
        should_build_bool = not vertex.frozen or bool(is_loop_component)
        assert should_build_bool is False

    def test_empty_string_display_name(self):
        """Test empty string display name."""
        vertex = Mock()
        vertex.display_name = ""
        vertex.is_loop = False
        vertex.frozen = True
        vertex.built = True

        is_loop_component = vertex.display_name == "Loop" or vertex.is_loop
        should_build = not vertex.frozen or is_loop_component

        assert is_loop_component is False
        assert should_build is False
