"""Test for aMap bug: duplicate columns when Keep Source Columns is enabled on re-run."""

from __future__ import annotations

import pytest

try:
    import agentics  # noqa: F401
except ImportError:
    pytest.skip("agentics-py not installed", allow_module_level=True)

from agentics import AG
from agentics.core.atype import create_pydantic_model
from lfx.components.agentics.helpers.schema_builder import build_schema_fields


@pytest.mark.unit
class TestAMapDuplicateColumns:
    """Tests for the duplicate column bug when source already contains output schema columns."""

    def test_should_merge_without_error_when_source_has_overlapping_columns(self):
        """Reproduces the exact bug: merge_states fails with 'got multiple values for keyword argument'.

        When the source DataFrame already contains columns matching the output schema,
        the fix deduplicates the source by removing overlapping columns before merging.
        """
        # Arrange — simulate a table that was already processed by aMap
        # (source already contains 'full_name' and 'age_group' from a previous run)
        source_fields = build_schema_fields(
            [
                {"name": "customer_id", "description": "Customer ID", "type": "str", "multiple": False},
                {"name": "email", "description": "Email address", "type": "str", "multiple": False},
                {"name": "full_name", "description": "Full name", "type": "str", "multiple": False},
                {"name": "age_group", "description": "Age group", "type": "str", "multiple": False},
            ]
        )
        source_atype = create_pydantic_model(source_fields, name="Source")
        source = AG(
            atype=source_atype,
            states=[
                source_atype(customer_id="1", email="a@test.com", full_name="Alice Smith", age_group="adult"),
                source_atype(customer_id="2", email="b@test.com", full_name="Bob Jones", age_group="senior"),
            ],
        )

        # Output schema has overlapping columns (full_name, age_group)
        output_fields = build_schema_fields(
            [
                {"name": "full_name", "description": "Full name", "type": "str", "multiple": False},
                {"name": "age_group", "description": "Age group", "type": "str", "multiple": False},
            ]
        )
        output_atype = create_pydantic_model(output_fields, name="Target")
        output = AG(
            atype=output_atype,
            states=[
                output_atype(full_name="Alice Updated", age_group="young_adult"),
                output_atype(full_name="Bob Updated", age_group="elderly"),
            ],
        )

        # Act — apply the same deduplication logic used in AMapComponent
        output_field_names = set(output.atype.model_fields.keys())
        source_field_names = set(source.atype.model_fields.keys())
        overlapping = source_field_names & output_field_names
        if overlapping:
            non_overlapping = source_field_names - overlapping
            deduplicated_atype = source.subset_atype(non_overlapping)
            source = source.rebind_atype(deduplicated_atype)
        result = source.merge_states(output)

        # Assert — merge should succeed and produce valid results
        result_df = result.to_dataframe()
        assert len(result_df) > 0
        assert "full_name" in result_df.columns
        assert "age_group" in result_df.columns
        assert "customer_id" in result_df.columns
        assert "email" in result_df.columns
