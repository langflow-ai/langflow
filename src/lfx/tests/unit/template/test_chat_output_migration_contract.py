"""Check the Chat Output predicate against the contract shared with the editor."""

import json
from pathlib import Path

import pytest
from lfx.template.field_migrations import can_migrate_chat_output_input

MIGRATION_CASES = json.loads(
    (Path(__file__).parents[2] / "data" / "component_compat" / "chat_output_migration_cases.json").read_text(
        encoding="utf-8"
    )
)


@pytest.mark.parametrize("case", MIGRATION_CASES["cases"], ids=[case["name"] for case in MIGRATION_CASES["cases"]])
def test_shared_chat_output_migration_contract(case):
    values = MIGRATION_CASES["defaults"] | case
    assert (
        can_migrate_chat_output_input(
            values["component_class_name"], values["field_name"], values["current_field"], values["saved_field"]
        )
        is values["expected"]
    )
