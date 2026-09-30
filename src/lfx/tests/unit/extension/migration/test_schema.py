"""Schema-level invariants for the migration table."""

from __future__ import annotations

import pytest
from lfx.extension.migration.schema import (
    MIGRATION_SCHEMA_VERSION,
    AmbiguousBareName,
    MigrationEntry,
    MigrationTable,
)
from pydantic import ValidationError


@pytest.mark.unit
def test_entry_requires_exactly_one_legacy_form() -> None:
    with pytest.raises(ValidationError):
        MigrationEntry(target="ext:openai:OpenAIEmbeddings@official", added_in="1.10.0")


@pytest.mark.unit
def test_entry_rejects_two_legacy_forms() -> None:
    with pytest.raises(ValidationError):
        MigrationEntry(
            bare_class_name="OpenAIEmbeddings",
            import_path="langflow.components.openai.OpenAIEmbeddings",
            target="ext:openai:OpenAIEmbeddings@official",
            added_in="1.10.0",
        )


@pytest.mark.unit
def test_entry_target_must_be_canonical() -> None:
    with pytest.raises(ValidationError):
        MigrationEntry(
            bare_class_name="OpenAIEmbeddings",
            target="OpenAIEmbeddings",  # not namespaced
            added_in="1.10.0",
        )
    with pytest.raises(ValidationError):
        MigrationEntry(
            bare_class_name="OpenAIEmbeddings",
            target="ext:openai:OpenAIEmbeddings@bogus",  # bad slot
            added_in="1.10.0",
        )


@pytest.mark.unit
def test_entry_legacy_form_kind_property() -> None:
    bare = MigrationEntry(
        bare_class_name="X",
        target="ext:bundle_b:X@official",
        added_in="1",
    )
    assert bare.legacy_form_kind == "bare_class_name"
    assert bare.legacy_value == "X"

    imp = MigrationEntry(
        import_path="x.y.X",
        target="ext:bundle_b:X@official",
        added_in="1",
    )
    assert imp.legacy_form_kind == "import_path"
    assert imp.legacy_value == "x.y.X"

    legacy = MigrationEntry(
        legacy_slot="ext:bundle_b:X@old",
        target="ext:bundle_b:X@official",
        added_in="1",
    )
    assert legacy.legacy_form_kind == "legacy_slot"
    assert legacy.legacy_value == "ext:bundle_b:X@old"


@pytest.mark.unit
def test_table_rejects_unsupported_schema_version() -> None:
    with pytest.raises(ValidationError):
        MigrationTable(schema_version=MIGRATION_SCHEMA_VERSION + 1, entries=[])


@pytest.mark.unit
def test_table_rejects_duplicate_legacy_value() -> None:
    e1 = MigrationEntry(
        bare_class_name="X",
        target="ext:bundle_a:X@official",
        added_in="1",
    )
    e2 = MigrationEntry(
        bare_class_name="X",
        target="ext:bundle_b:X@official",
        added_in="1",
    )
    with pytest.raises(ValidationError):
        MigrationTable(schema_version=1, entries=[e1, e2])


@pytest.mark.unit
def test_table_lookup_helpers() -> None:
    bare = MigrationEntry(
        bare_class_name="MergeDataComponent",
        target="ext:utilities:MergeDataComponent@official",
        added_in="1.10.0",
    )
    imp = MigrationEntry(
        import_path="langflow.components.utilities.MergeDataComponent",
        target="ext:utilities:MergeDataComponent@official",
        added_in="1.10.0",
    )
    legacy = MigrationEntry(
        legacy_slot="ext:utilities:MergeDataComponent@official-pre-a",
        target="ext:utilities:MergeDataComponent@official",
        added_in="1.10.0",
    )
    table = MigrationTable(schema_version=1, entries=[bare, imp, legacy])
    assert table.lookup_bare("MergeDataComponent") is bare
    assert table.lookup_bare("Unknown") is None
    assert table.lookup_import_path("langflow.components.utilities.MergeDataComponent") is imp
    assert table.lookup_legacy_slot("ext:utilities:MergeDataComponent@official-pre-a") is legacy
    assert sorted(table.all_known_legacy_values()) == sorted(
        [
            "MergeDataComponent",
            "langflow.components.utilities.MergeDataComponent",
            "ext:utilities:MergeDataComponent@official-pre-a",
        ]
    )


@pytest.mark.unit
def test_ambiguous_bare_name_requires_at_least_two_candidates() -> None:
    with pytest.raises(ValidationError):
        AmbiguousBareName(
            name="MergeDataComponent",
            candidates=["ext:processing:MergeDataComponent@official"],
        )


@pytest.mark.unit
def test_ambiguous_bare_name_rejects_non_canonical_candidate() -> None:
    with pytest.raises(ValidationError):
        AmbiguousBareName(
            name="MergeDataComponent",
            candidates=[
                "ext:processing:MergeDataComponent@official",
                "MergeDataComponent",  # not canonical
            ],
        )


@pytest.mark.unit
def test_ambiguous_bare_name_rejects_duplicate_candidates() -> None:
    with pytest.raises(ValidationError):
        AmbiguousBareName(
            name="MergeDataComponent",
            candidates=[
                "ext:processing:MergeDataComponent@official",
                "ext:processing:MergeDataComponent@official",
            ],
        )


@pytest.mark.unit
def test_table_rejects_collision_between_entries_and_ambiguous_bare_names() -> None:
    """A bare name cannot be both auto-rewrite and ambiguous.

    The auto-rewrite would silently win, so the table validator must
    reject the contradiction at load time.
    """
    auto = MigrationEntry(
        bare_class_name="MergeDataComponent",
        target="ext:processing:MergeDataComponent@official",
        added_in="1.10.0",
    )
    ambig = AmbiguousBareName(
        name="MergeDataComponent",
        candidates=[
            "ext:processing:MergeDataComponent@official",
            "ext:deactivated:MergeDataComponent@official",
        ],
        added_in="1.10.0",
    )
    with pytest.raises(ValidationError):
        MigrationTable(
            schema_version=1,
            entries=[auto],
            ambiguous_bare_names=[ambig],
        )


@pytest.mark.unit
def test_table_rejects_duplicate_ambiguous_bare_names() -> None:
    a1 = AmbiguousBareName(
        name="MergeDataComponent",
        candidates=[
            "ext:processing:MergeDataComponent@official",
            "ext:deactivated:MergeDataComponent@official",
        ],
        added_in="1.10.0",
    )
    a2 = AmbiguousBareName(
        name="MergeDataComponent",
        candidates=[
            "ext:processing:MergeDataComponent@official",
            "ext:other:MergeDataComponent@official",
        ],
        added_in="1.10.0",
    )
    with pytest.raises(ValidationError):
        MigrationTable(schema_version=1, entries=[], ambiguous_bare_names=[a1, a2])


@pytest.mark.unit
def test_table_lookup_ambiguous_bare() -> None:
    ambig = AmbiguousBareName(
        name="MergeDataComponent",
        candidates=[
            "ext:processing:MergeDataComponent@official",
            "ext:deactivated:MergeDataComponent@official",
        ],
        added_in="1.10.0",
    )
    table = MigrationTable(schema_version=1, entries=[], ambiguous_bare_names=[ambig])
    assert table.lookup_ambiguous_bare("MergeDataComponent") is ambig
    assert table.lookup_ambiguous_bare("Unknown") is None
