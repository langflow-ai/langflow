from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from lfx.components.logic.conditional_router import ConditionalRouterComponent
from lfx.schema.message import Message

from tests.base import ComponentTestBaseWithoutClient


class TestConditionalRouterComponent(ComponentTestBaseWithoutClient):
    """Test cases for ConditionalRouterComponent."""

    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return ConditionalRouterComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "input_text": "test input",
            "operator": "equals",
            "match_text": "test input",
            "case_sensitive": True,
            "true_case_message": Message(content="true result"),
            "false_case_message": Message(content="false result"),
            "max_iterations": 10,
            "default_route": "true_result",
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component doesn't have version-specific files."""
        return []

    async def test_component_initialization(self, component_class, default_kwargs):
        """Test proper initialization of ConditionalRouterComponent."""
        component = await self.component_setup(component_class, default_kwargs)
        assert component.display_name == "If-Else"
        assert "Routes an input message" in component.description
        assert component.name == "ConditionalRouter"
        assert component.icon == "split"
        # Test private iteration tracking attribute
        assert hasattr(component, "_ConditionalRouterComponent__iteration_updated")
        assert component._ConditionalRouterComponent__iteration_updated is False

    async def test_inputs_configuration(self, component_class, default_kwargs):
        """Test that inputs are properly configured."""
        component = await self.component_setup(component_class, default_kwargs)
        expected_inputs = [
            "input_text",
            "operator",
            "match_text",
            "case_sensitive",
            "true_case_message",
            "false_case_message",
            "max_iterations",
            "default_route",
        ]

        assert len(component.inputs) == len(expected_inputs)
        input_names = [inp.name for inp in component.inputs]

        for expected_input in expected_inputs:
            assert expected_input in input_names

    async def test_outputs_configuration(self, component_class, default_kwargs):
        """Test that outputs are properly configured."""
        component = await self.component_setup(component_class, default_kwargs)
        assert len(component.outputs) == 2
        output_names = [out.name for out in component.outputs]
        assert "true_result" in output_names
        assert "false_result" in output_names

    async def test_pre_run_setup(self, component_class, default_kwargs):
        """Test _pre_run_setup method."""
        component = await self.component_setup(component_class, default_kwargs)
        component._ConditionalRouterComponent__iteration_updated = True
        component._pre_run_setup()
        assert component._ConditionalRouterComponent__iteration_updated is False

    @pytest.mark.parametrize(
        ("input_text", "match_text", "operator", "case_sensitive", "expected"),
        [
            # Equals tests
            ("hello", "hello", "equals", True, True),
            ("hello", "Hello", "equals", True, False),
            ("hello", "Hello", "equals", False, True),
            ("hello", "world", "equals", False, False),
            # Not equals tests
            ("hello", "world", "not equals", True, True),
            ("hello", "hello", "not equals", True, False),
            ("Hello", "hello", "not equals", False, False),
            # Contains tests
            ("hello world", "world", "contains", True, True),
            ("hello world", "World", "contains", True, False),
            ("hello world", "World", "contains", False, True),
            ("hello world", "foo", "contains", True, False),
            # Starts with tests
            ("hello world", "hello", "starts with", True, True),
            ("hello world", "Hello", "starts with", True, False),
            ("hello world", "Hello", "starts with", False, True),
            ("hello world", "world", "starts with", True, False),
            # Ends with tests
            ("hello world", "world", "ends with", True, True),
            ("hello world", "World", "ends with", True, False),
            ("hello world", "World", "ends with", False, True),
            ("hello world", "hello", "ends with", True, False),
            # Regex tests - case sensitivity doesn't apply to regex
            ("hello123", r"hello\d+", "regex", True, True),
            ("hello123", r"Hello\d+", "regex", True, False),
            ("hello123", r"Hello\d+", "regex", False, False),  # Still case sensitive for regex
            ("hello", r"invalid[regex", "regex", True, False),  # Invalid regex
            # Numeric comparison tests
            ("10", "5", "greater than", True, True),
            ("5", "10", "greater than", True, False),
            ("10", "10", "greater than or equal", True, True),
            ("5", "10", "greater than or equal", True, False),
            ("5", "10", "less than", True, True),
            ("10", "5", "less than", True, False),
            ("10", "10", "less than or equal", True, True),
            ("15", "10", "less than or equal", True, False),
            # Invalid numeric comparison
            ("abc", "10", "greater than", True, False),
            ("10", "abc", "less than", True, False),
        ],
    )
    async def test_evaluate_condition(
        self, component_class, default_kwargs, input_text, match_text, operator, case_sensitive, expected
    ):
        """Test evaluate_condition method with various inputs."""
        component = await self.component_setup(component_class, default_kwargs)
        result = component.evaluate_condition(input_text, match_text, operator, case_sensitive=case_sensitive)
        assert result == expected

    async def test_evaluate_condition_unknown_operator(self, component_class, default_kwargs):
        """Test evaluate_condition with unknown operator."""
        component = await self.component_setup(component_class, default_kwargs)
        result = component.evaluate_condition("hello", "hello", "unknown_operator", case_sensitive=True)
        assert result is False

    async def test_iterate_and_stop_once_initial_call(self, component_class, default_kwargs):
        """Test iterate_and_stop_once method on initial call."""
        component = await self.component_setup(component_class, default_kwargs)
        # Set up component attributes
        component.max_iterations = 5
        component.default_route = "false_result"

        # Mock the graph object with exclude_branch_conditionally method
        mock_graph = MagicMock()
        mock_exclude = MagicMock()
        mock_graph.exclude_branch_conditionally = mock_exclude

        # Mock the context property and methods
        with (
            patch.object(type(component), "ctx", new_callable=dict),
            patch.object(component, "_id", "test_id"),
            patch.object(component, "update_ctx") as mock_update,
            patch.object(component, "stop") as mock_stop,
            patch.object(type(component), "graph", new_callable=PropertyMock, return_value=mock_graph),
        ):
            component.iterate_and_stop_once("false_result")

            mock_update.assert_called_once_with({"test_id_iteration": 1})
            mock_stop.assert_called_once_with("false_result")
            mock_exclude.assert_called_once_with("test_id", output_name="false_result")
            assert component._ConditionalRouterComponent__iteration_updated is True

    async def test_iterate_and_stop_once_max_iterations_reached(self, component_class, default_kwargs):
        """Test iterate_and_stop_once when max iterations are reached."""
        component = await self.component_setup(component_class, default_kwargs)
        # Set up component attributes
        component.max_iterations = 5
        component.default_route = "false_result"

        # Mock the graph object with conditional exclusion tracking
        mock_graph = MagicMock()
        mock_graph.conditional_exclusion_sources = {}
        mock_graph.conditionally_excluded_vertices = set()
        mock_exclude = MagicMock()
        mock_graph.exclude_branch_conditionally = mock_exclude

        # Mock ctx with existing iterations at the limit
        mock_ctx = {"test_id_iteration": 5}
        with (
            patch.object(type(component), "ctx", new_callable=lambda: mock_ctx),
            patch.object(component, "_id", "test_id"),
            patch.object(component, "update_ctx") as mock_update,
            patch.object(component, "stop") as mock_stop,
            patch.object(type(component), "graph", new_callable=PropertyMock, return_value=mock_graph),
        ):
            component.iterate_and_stop_once("false_result")

            mock_update.assert_called_once_with({"test_id_iteration": 6})
            # Should flip to opposite route when max iterations reached
            mock_stop.assert_called_once_with("true_result")
            # exclude_branch_conditionally should NOT be called when breaking cycle
            mock_exclude.assert_not_called()

    async def test_iterate_and_stop_once_already_updated(self, component_class, default_kwargs):
        """Test iterate_and_stop_once when already updated in this iteration."""
        component = await self.component_setup(component_class, default_kwargs)
        # Set up component state - when already updated, method should return early
        component._ConditionalRouterComponent__iteration_updated = True

        # Mock required attributes and methods
        with (
            patch.object(component, "_id", "test_id"),
            patch.object(component, "update_ctx") as mock_update,
            patch.object(component, "stop") as mock_stop,
        ):
            component.iterate_and_stop_once("false_result")

            # When already updated, neither update_ctx nor stop should be called
            mock_update.assert_not_called()
            mock_stop.assert_not_called()

    async def test_true_response_condition_true(self, component_class, default_kwargs):
        """Test true_response when condition evaluates to True."""
        component = await self.component_setup(component_class, default_kwargs)
        component.input_text = "hello"
        component.match_text = "hello"
        component.operator = "equals"
        component.case_sensitive = True
        component.true_case_message = Message(content="True case")

        with (
            patch.object(component, "iterate_and_stop_once") as mock_iterate,
            patch.object(type(component), "ctx", new_callable=dict),
            patch.object(component, "_id", "test_id"),
        ):
            result = component.true_response()

            assert result == component.true_case_message
            assert component.status == component.true_case_message
            mock_iterate.assert_called_once_with("false_result")

    async def test_true_response_condition_false(self, component_class, default_kwargs):
        """Test true_response when condition evaluates to False."""
        component = await self.component_setup(component_class, default_kwargs)
        component.input_text = "hello"
        component.match_text = "world"
        component.operator = "equals"
        component.case_sensitive = True

        with (
            patch.object(component, "iterate_and_stop_once") as mock_iterate,
            patch.object(type(component), "ctx", new_callable=dict),
            patch.object(component, "_id", "test_id"),
        ):
            result = component.true_response()

            assert isinstance(result, Message)
            assert result.content == ""
            mock_iterate.assert_called_once_with("true_result")

    async def test_false_response_condition_false(self, component_class, default_kwargs):
        """Test false_response when condition evaluates to False."""
        component = await self.component_setup(component_class, default_kwargs)
        component.input_text = "hello"
        component.match_text = "world"
        component.operator = "equals"
        component.case_sensitive = True
        component.false_case_message = Message(content="False case")

        with patch.object(component, "iterate_and_stop_once") as mock_iterate:
            result = component.false_response()

            assert result == component.false_case_message
            assert component.status == component.false_case_message
            mock_iterate.assert_called_once_with("true_result")

    async def test_false_response_condition_true(self, component_class, default_kwargs):
        """Test false_response when condition evaluates to True."""
        component = await self.component_setup(component_class, default_kwargs)
        component.input_text = "hello"
        component.match_text = "hello"
        component.operator = "equals"
        component.case_sensitive = True

        with patch.object(component, "iterate_and_stop_once") as mock_iterate:
            result = component.false_response()

            assert isinstance(result, Message)
            assert result.content == ""
            mock_iterate.assert_called_once_with("false_result")

    async def test_update_build_config_regex_operator(self, component_class, default_kwargs):
        """Test update_build_config when operator is regex."""
        component = await self.component_setup(component_class, default_kwargs)
        build_config = {"case_sensitive": {"show": True}}

        result = component.update_build_config(build_config, "regex", "operator")

        assert "case_sensitive" not in result

    async def test_update_build_config_non_regex_operator(self, component_class, default_kwargs):
        """Test update_build_config when operator is not regex."""
        component = await self.component_setup(component_class, default_kwargs)
        build_config = {}

        # Find the actual case_sensitive input in the component
        case_sensitive_input = next((inp for inp in component.inputs if inp.name == "case_sensitive"), None)
        assert case_sensitive_input is not None  # Ensure it exists

        result = component.update_build_config(build_config, "equals", "operator")

        # The method should add case_sensitive to build_config if it doesn't exist
        assert "case_sensitive" in result
        assert isinstance(result["case_sensitive"], dict)

    async def test_update_build_config_non_operator_field(self, component_class, default_kwargs):
        """Test update_build_config when field is not operator."""
        component = await self.component_setup(component_class, default_kwargs)
        build_config = {"some_field": "value"}

        result = component.update_build_config(build_config, "some_value", "some_field")

        assert result == build_config  # Should return unchanged

    async def test_regex_error_handling(self, component_class, default_kwargs):
        """Test that invalid regex patterns are handled gracefully."""
        component = await self.component_setup(component_class, default_kwargs)
        # Test with an invalid regex pattern
        result = component.evaluate_condition("test", "[invalid", "regex", case_sensitive=True)
        assert result is False

    async def test_numeric_comparison_edge_cases(self, component_class, default_kwargs):
        """Test numeric comparison with edge cases."""
        component = await self.component_setup(component_class, default_kwargs)
        # Float comparison
        result = component.evaluate_condition("10.5", "10", "greater than", case_sensitive=True)
        assert result is True

        # Negative numbers
        result = component.evaluate_condition("-5", "0", "less than", case_sensitive=True)
        assert result is True

        # Scientific notation - need to be more careful with floating point comparison
        result = component.evaluate_condition("100000.0", "100000.0", "equals", case_sensitive=True)
        assert result is True

    async def test_case_insensitive_operations(self, component_class, default_kwargs):
        """Test that case insensitive operations work correctly for string operators."""
        component = await self.component_setup(component_class, default_kwargs)
        test_cases = [
            ("Hello", "hello", "equals", False, True),
            ("Hello World", "WORLD", "contains", False, True),
            ("Hello World", "HELLO", "starts with", False, True),
            ("Hello World", "WORLD", "ends with", False, True),
        ]

        for input_text, match_text, operator, case_sensitive, expected in test_cases:
            result = component.evaluate_condition(input_text, match_text, operator, case_sensitive=case_sensitive)
            assert result == expected, (
                f"Failed for {input_text} {operator} {match_text} (case_sensitive={case_sensitive})"
            )
