"""Unit tests for Agentics DataFrameOps component."""

from __future__ import annotations

import pytest
from lfx.components.agentics.constants import (
    DATAFRAME_OPERATIONS,
    OPERATION_COMPOSE,
    OPERATION_CONCATENATE,
    OPERATION_MERGE,
)
from lfx.components.agentics.dataframe_ops import DataFrameOps


@pytest.mark.unit
class TestDataFrameOpsComponent:
    """Tests for DataFrameOps component."""

    def test_should_have_correct_display_name(self):
        """Test that component has correct display name."""
        assert DataFrameOps.display_name == "DataFrameOps"

    def test_should_have_correct_icon(self):
        """Test that component has correct icon."""
        assert DataFrameOps.icon == "Agentics"

    def test_should_have_required_inputs(self):
        """Test that component has all required inputs."""
        input_names = {i.name for i in DataFrameOps.inputs}

        assert "left_dataframe" in input_names
        assert "right_dataframe" in input_names
        assert "operation_type" in input_names

    def test_should_have_dataframe_output(self):
        """Test that component has DataFrame output."""
        output_names = {o.name for o in DataFrameOps.outputs}
        assert "states" in output_names

    def test_should_have_valid_operation_type_options(self):
        """Test that operation_type dropdown has valid options."""
        operation_input = next((i for i in DataFrameOps.inputs if i.name == "operation_type"), None)
        assert operation_input is not None
        assert operation_input.options == DATAFRAME_OPERATIONS
        assert OPERATION_MERGE in operation_input.options
        assert OPERATION_COMPOSE in operation_input.options
        assert OPERATION_CONCATENATE in operation_input.options

    def test_should_have_merge_as_default_operation(self):
        """Test that merge is the default operation type."""
        operation_input = next((i for i in DataFrameOps.inputs if i.name == "operation_type"), None)
        assert operation_input is not None
        assert operation_input.value == OPERATION_MERGE

    def test_should_have_documentation_link(self):
        """Test that component has documentation link."""
        assert DataFrameOps.documentation is not None
        assert "agentics" in DataFrameOps.documentation.lower()
