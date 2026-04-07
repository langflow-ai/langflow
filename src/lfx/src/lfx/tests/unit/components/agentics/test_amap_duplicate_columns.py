"""Test for aMap bug: duplicate columns when Keep Source Columns is enabled on re-run."""

from __future__ import annotations

from agentics import AG
from agentics.core.atype import create_pydantic_model
from lfx.components.agentics.helpers.schema_builder import build_schema_fields


class TestAMapDuplicateColumns:
    """Tests for the duplicate column bug when source already contains output schema columns."""

    def test_should_merge_without_error_when_source_has_overlapping_columns(self):
        """Reproduces the exact bug: merge_states fails with 'got multiple values for keyword argument'.

        When the source DataFrame already contains columns matching the output schema.
        """
        # Arrange — simulate a table that was already processed by aMap
        # (source already contains 'full_name' and 'age_group' from a previous run)
        source_fields = build_schema_fields(
            [
                ("customer_id", "Customer ID", "str", False),
                ("email", "Email address", "str", False),
                ("full_name", "Full name", "str", False),
                ("age_group", "Age group", "str", False),
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
                ("full_name", "Full name", "str", False),
                ("age_group", "Age group", "str", False),
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

        # Act & Assert — this should NOT raise TypeError about duplicate keyword arguments
        result = source.merge_states(output)

        # The merge should produce valid results
        result_df = result.to_dataframe()
        assert len(result_df) > 0  # noqa: S101
