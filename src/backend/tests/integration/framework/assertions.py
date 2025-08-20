"""Enhanced assertions for integration testing."""

from typing import Any

from langflow.schema.data import Data
from langflow.schema.dataframe import DataFrame
from langflow.schema.message import Message


class AssertionHelpers:
    """Collection of assertion helpers for common testing scenarios."""

    def assert_message(
        self,
        actual: Any,
        expected_text: str | None = None,
        expected_sender: str | None = None,
        expected_session_id: str | None = None,
        contains_text: str | None = None,
    ):
        """Assert message object properties.

        Args:
            actual: Object to test (should be Message)
            expected_text: Expected exact text content
            expected_sender: Expected sender
            expected_session_id: Expected session ID
            contains_text: Text that should be contained in message
        """
        assert isinstance(actual, Message), f"Expected Message, got {type(actual).__name__}"

        if expected_text is not None:
            assert actual.text == expected_text, f"Expected text '{expected_text}', got '{actual.text}'"

        if expected_sender is not None:
            assert actual.sender == expected_sender, f"Expected sender '{expected_sender}', got '{actual.sender}'"

        if expected_session_id is not None:
            assert actual.session_id == expected_session_id, (
                f"Expected session_id '{expected_session_id}', got '{actual.session_id}'"
            )

        if contains_text is not None:
            assert contains_text in actual.text, f"Expected text to contain '{contains_text}', got '{actual.text}'"

    def assert_data(
        self,
        actual: Any,
        expected_data: Any | None = None,
        expected_text: str | None = None,
        has_keys: list[str] | None = None,
    ):
        """Assert Data object properties.

        Args:
            actual: Object to test (should be Data)
            expected_data: Expected data content
            expected_text: Expected text content
            has_keys: Keys that should exist in data
        """
        assert isinstance(actual, Data), f"Expected Data, got {type(actual).__name__}"

        if expected_data is not None:
            assert actual.data == expected_data, f"Expected data {expected_data}, got {actual.data}"

        if expected_text is not None:
            assert actual.text == expected_text, f"Expected text '{expected_text}', got '{actual.text}'"

        if has_keys:
            if isinstance(actual.data, dict):
                for key in has_keys:
                    assert key in actual.data, f"Expected key '{key}' in data {actual.data}"
            else:
                msg = f"Expected data to be dict for key checking, got {type(actual.data)}"
                raise AssertionError(msg)

    def assert_dataframe(
        self,
        actual: Any,
        expected_shape: tuple | None = None,
        expected_columns: list[str] | None = None,
        min_rows: int | None = None,
        max_rows: int | None = None,
    ):
        """Assert DataFrame properties.

        Args:
            actual: Object to test (should be DataFrame)
            expected_shape: Expected (rows, columns) shape
            expected_columns: Expected column names
            min_rows: Minimum number of rows
            max_rows: Maximum number of rows
        """
        assert isinstance(actual, DataFrame), f"Expected DataFrame, got {type(actual).__name__}"

        df = actual.to_pandas() if hasattr(actual, "to_pandas") else actual.data

        if expected_shape is not None:
            assert df.shape == expected_shape, f"Expected shape {expected_shape}, got {df.shape}"

        if expected_columns is not None:
            actual_columns = list(df.columns)
            assert actual_columns == expected_columns, f"Expected columns {expected_columns}, got {actual_columns}"

        if min_rows is not None:
            assert len(df) >= min_rows, f"Expected at least {min_rows} rows, got {len(df)}"

        if max_rows is not None:
            assert len(df) <= max_rows, f"Expected at most {max_rows} rows, got {len(df)}"

    def assert_output_types(self, outputs: dict[str, Any], expected_types: dict[str, type]):
        """Assert that outputs have expected types.

        Args:
            outputs: Dictionary of component outputs
            expected_types: Dictionary mapping output names to expected types
        """
        for output_name, expected_type in expected_types.items():
            assert output_name in outputs, f"Output '{output_name}' not found in {list(outputs.keys())}"
            actual_value = outputs[output_name]
            assert isinstance(actual_value, expected_type), (
                f"Expected {output_name} to be {expected_type.__name__}, got {type(actual_value).__name__}"
            )

    def assert_output_not_empty(self, outputs: dict[str, Any], output_names: list[str] | None = None):
        """Assert that specified outputs are not empty.

        Args:
            outputs: Dictionary of component outputs
            output_names: List of output names to check (all if None)
        """
        names_to_check = output_names or list(outputs.keys())

        for name in names_to_check:
            assert name in outputs, f"Output '{name}' not found in {list(outputs.keys())}"
            value = outputs[name]

            if isinstance(value, str | list | dict):
                assert len(value) > 0, f"Output '{name}' is empty"
            elif isinstance(value, Message | Data | DataFrame):
                # These types should have content
                assert value is not None, f"Output '{name}' is None"
            else:
                assert value is not None, f"Output '{name}' is None"

    def assert_error_output(
        self,
        outputs: dict[str, Any],
        error_output_name: str = "error",
        expected_error_type: type | None = None,
        contains_message: str | None = None,
    ):
        """Assert that component produced an error output.

        Args:
            outputs: Dictionary of component outputs
            error_output_name: Name of error output field
            expected_error_type: Expected error type
            contains_message: Text that should be in error message
        """
        assert error_output_name in outputs, f"Error output '{error_output_name}' not found"
        error = outputs[error_output_name]

        if expected_error_type:
            assert isinstance(error, expected_error_type), (
                f"Expected error type {expected_error_type.__name__}, got {type(error).__name__}"
            )

        if contains_message:
            error_str = str(error)
            assert contains_message in error_str, f"Expected error to contain '{contains_message}', got '{error_str}'"

    def assert_json_response(
        self,
        response,
        expected_status: int = 200,
        required_fields: list[str] | None = None,
        expected_values: dict[str, Any] | None = None,
    ):
        """Assert JSON API response properties.

        Args:
            response: HTTP response object
            expected_status: Expected status code
            required_fields: Fields that must exist in response JSON
            expected_values: Fields that must have specific values
        """
        assert response.status_code == expected_status, (
            f"Expected status {expected_status}, got {response.status_code}. Response: {response.text}"
        )

        try:
            json_data = response.json()
        except Exception as e:
            msg = f"Response is not valid JSON: {response.text}. Error: {e}"
            raise AssertionError(msg)

        if required_fields:
            for field in required_fields:
                assert field in json_data, f"Required field '{field}' not found in response: {json_data}"

        if expected_values:
            for field, expected_value in expected_values.items():
                assert field in json_data, f"Expected field '{field}' not found in response: {json_data}"
                actual_value = json_data[field]
                assert actual_value == expected_value, (
                    f"Expected {field} to be '{expected_value}', got '{actual_value}'"
                )

    def assert_component_contract(
        self,
        component,
        expected_inputs: list[str] | None = None,
        expected_outputs: list[str] | None = None,
        required_attributes: list[str] | None = None,
    ):
        """Assert that component follows expected contract.

        Args:
            component: Component instance to test
            expected_inputs: Expected input names
            expected_outputs: Expected output names
            required_attributes: Required component attributes
        """
        # Check basic component structure
        assert hasattr(component, "inputs"), "Component must have 'inputs' attribute"
        assert hasattr(component, "outputs"), "Component must have 'outputs' attribute"

        if expected_inputs:
            actual_inputs = [inp.name for inp in component.inputs]
            for expected_input in expected_inputs:
                assert expected_input in actual_inputs, (
                    f"Expected input '{expected_input}' not found. Available inputs: {actual_inputs}"
                )

        if expected_outputs:
            actual_outputs = [out.name for out in component.outputs]
            for expected_output in expected_outputs:
                assert expected_output in actual_outputs, (
                    f"Expected output '{expected_output}' not found. Available outputs: {actual_outputs}"
                )

        if required_attributes:
            for attr in required_attributes:
                assert hasattr(component, attr), f"Component missing required attribute '{attr}'"

    def assert_flow_execution(
        self,
        outputs: dict[str, Any],
        expected_output_count: int | None = None,
        required_outputs: list[str] | None = None,
        no_errors: bool = True,
    ):
        """Assert flow execution results.

        Args:
            outputs: Flow execution outputs
            expected_output_count: Expected number of outputs
            required_outputs: Output names that must be present
            no_errors: Whether to assert no error outputs
        """
        if expected_output_count is not None:
            assert len(outputs) == expected_output_count, (
                f"Expected {expected_output_count} outputs, got {len(outputs)}: {list(outputs.keys())}"
            )

        if required_outputs:
            for output_name in required_outputs:
                assert output_name in outputs, (
                    f"Required output '{output_name}' not found. Available outputs: {list(outputs.keys())}"
                )

        if no_errors:
            error_outputs = [k for k, v in outputs.items() if "error" in k.lower()]
            if error_outputs:
                error_details = {k: outputs[k] for k in error_outputs}
                msg = f"Flow execution produced errors: {error_details}"
                raise AssertionError(msg)

    def assert_performance(self, execution_time: float, max_time: float, operation_name: str = "operation"):
        """Assert performance constraints.

        Args:
            execution_time: Actual execution time in seconds
            max_time: Maximum allowed time in seconds
            operation_name: Name of operation being tested
        """
        assert execution_time <= max_time, f"{operation_name} took {execution_time:.2f}s, expected <= {max_time}s"

    def assert_similarity(self, actual: str, expected: str, min_similarity: float = 0.8, method: str = "ratio"):
        """Assert string similarity using difflib.

        Args:
            actual: Actual string
            expected: Expected string
            min_similarity: Minimum similarity ratio (0.0 to 1.0)
            method: Similarity method ('ratio', 'partial_ratio')
        """
        try:
            from difflib import SequenceMatcher

            if method == "ratio":
                similarity = SequenceMatcher(None, actual, expected).ratio()
            # For partial ratio, check if shorter string is in longer one
            elif len(expected) <= len(actual):
                similarity = SequenceMatcher(None, expected, actual).ratio()
            else:
                similarity = SequenceMatcher(None, actual, expected).ratio()

            assert similarity >= min_similarity, (
                f"Similarity {similarity:.2f} below threshold {min_similarity}. "
                f"Expected: '{expected}', Actual: '{actual}'"
            )

        except ImportError:
            # Fallback to simple containment check
            assert expected.lower() in actual.lower() or actual.lower() in expected.lower(), (
                f"Strings not similar enough. Expected: '{expected}', Actual: '{actual}'"
            )
