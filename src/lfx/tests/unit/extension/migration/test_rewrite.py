"""Tests for the flow-deserializer rewrite hook."""

from __future__ import annotations

import pytest
from lfx.extension.migration.rewrite import migrate_flow_payload
from lfx.extension.migration.schema import MigrationEntry, MigrationTable


def _node(node_id: str, type_value: str) -> dict:
    """Build a minimal saved-flow node skeleton for testing."""
    return {
        "id": node_id,
        "type": "genericNode",
        "data": {
            "id": node_id,
            "type": type_value,
            "node": {"template": {}},
        },
    }


def _payload(*nodes: dict) -> dict:
    return {"data": {"nodes": list(nodes), "edges": []}}


@pytest.fixture
def table() -> MigrationTable:
    return MigrationTable(
        schema_version=1,
        entries=[
            MigrationEntry(
                bare_class_name="OpenAIEmbeddings",
                target="ext:openai:OpenAIEmbeddings@official",
                added_in="1.10.0",
            ),
            MigrationEntry(
                import_path="langflow.components.openai.OpenAIEmbeddings",
                target="ext:openai:OpenAIEmbeddings@official",
                added_in="1.10.0",
            ),
            MigrationEntry(
                legacy_slot="ext:openai:OpenAIEmbeddings@official-pre-a",
                target="ext:openai:OpenAIEmbeddings@official",
                added_in="1.10.0",
            ),
            MigrationEntry(
                bare_class_name="MergeDataComponent",
                target="ext:utilities:MergeDataComponent@official",
                added_in="1.10.0",
            ),
        ],
    )


@pytest.mark.unit
def test_rewrites_bare_class_name(table: MigrationTable) -> None:
    payload = _payload(_node("OpenAIEmbeddings-1", "OpenAIEmbeddings"))
    report = migrate_flow_payload(payload, table=table)
    assert report.rewritten_count == 1
    assert payload["data"]["nodes"][0]["data"]["type"] == "ext:openai:OpenAIEmbeddings@official"
    [record] = report.records
    assert record.outcome == "rewritten"
    assert record.legacy_form_kind == "bare_class_name"
    assert record.new_value == "ext:openai:OpenAIEmbeddings@official"


@pytest.mark.unit
def test_rewrites_import_path(table: MigrationTable) -> None:
    payload = _payload(_node("X-1", "langflow.components.openai.OpenAIEmbeddings"))
    report = migrate_flow_payload(payload, table=table)
    assert report.rewritten_count == 1
    assert payload["data"]["nodes"][0]["data"]["type"] == "ext:openai:OpenAIEmbeddings@official"
    assert report.records[0].legacy_form_kind == "import_path"


@pytest.mark.unit
def test_rewrites_pre_phase_a_slot(table: MigrationTable) -> None:
    payload = _payload(_node("X-1", "ext:openai:OpenAIEmbeddings@official-pre-a"))
    report = migrate_flow_payload(payload, table=table)
    assert report.rewritten_count == 1
    assert payload["data"]["nodes"][0]["data"]["type"] == "ext:openai:OpenAIEmbeddings@official"
    assert report.records[0].legacy_form_kind == "legacy_slot"


@pytest.mark.unit
def test_rewrites_every_known_reference_in_one_pass(table: MigrationTable) -> None:
    payload = _payload(
        _node("a", "OpenAIEmbeddings"),
        _node("b", "langflow.components.openai.OpenAIEmbeddings"),
        _node("c", "ext:openai:OpenAIEmbeddings@official-pre-a"),
        _node("d", "MergeDataComponent"),
    )
    report = migrate_flow_payload(payload, table=table)
    assert report.rewritten_count == 4
    new_types = [n["data"]["type"] for n in payload["data"]["nodes"]]
    assert new_types == [
        "ext:openai:OpenAIEmbeddings@official",
        "ext:openai:OpenAIEmbeddings@official",
        "ext:openai:OpenAIEmbeddings@official",
        "ext:utilities:MergeDataComponent@official",
    ]


@pytest.mark.unit
def test_already_canonical_left_alone(table: MigrationTable) -> None:
    payload = _payload(_node("x", "ext:openai:OpenAIEmbeddings@official"))
    report = migrate_flow_payload(payload, table=table)
    assert report.rewritten_count == 0
    assert report.records[0].outcome == "already_canonical"
    assert payload["data"]["nodes"][0]["data"]["type"] == "ext:openai:OpenAIEmbeddings@official"


@pytest.mark.unit
def test_unmapped_reference_emits_typed_error_with_suggestion(table: MigrationTable) -> None:
    # A near-miss on an existing entry: should produce a close-match hint.
    payload = _payload(_node("x", "OpenAIEmbedding"))  # missing trailing 's'
    report = migrate_flow_payload(payload, table=table)
    assert report.rewritten_count == 0
    [record] = report.records
    assert record.outcome == "unmapped"
    assert record.error is not None
    assert record.error.code == "component-not-found-with-hint"
    assert "OpenAIEmbeddings" in record.error.hint
    # Flow load should NOT crash; node retains its original type.
    assert payload["data"]["nodes"][0]["data"]["type"] == "OpenAIEmbedding"


@pytest.mark.unit
def test_unmapped_with_no_close_match_falls_back_to_generic_hint(table: MigrationTable) -> None:
    payload = _payload(_node("x", "TotallyUnrelatedSymbol"))
    report = migrate_flow_payload(payload, table=table)
    [record] = report.records
    assert record.outcome == "unmapped"
    assert record.error is not None
    assert "No close match" in record.error.hint or "Did you mean" in record.error.hint


@pytest.mark.unit
def test_cross_bucket_ambiguity_emits_component_name_ambiguous() -> None:
    """Two buckets matching the same string -> ``component-name-ambiguous``."""
    # Build two entries that share a literal string across buckets.  We use
    # ``model_construct`` to bypass the table-level uniqueness check; the
    # entries themselves are individually valid.
    e_bare = MigrationEntry(
        bare_class_name="ConflictedName",
        target="ext:bundle_a:ConflictedName@official",
        added_in="1.10.0",
    )
    # Build the import_path entry such that its import_path equals the bare
    # name above.  The per-entry validator requires at least one dot in the
    # import path, so we cheat by mutating the frozen instance's slot after
    # construction; the table-level uniqueness check is bypassed via
    # ``model_construct``.
    e_imp = MigrationEntry(
        import_path="x.ConflictedName",
        target="ext:bundle_b:ConflictedName@official",
        added_in="1.10.0",
    )
    object.__setattr__(e_imp, "import_path", "ConflictedName")

    table = MigrationTable.model_construct(schema_version=1, entries=[e_bare, e_imp])
    payload = _payload(_node("z", "ConflictedName"))
    report = migrate_flow_payload(payload, table=table)
    [record] = report.records
    assert record.outcome == "ambiguous"
    assert record.error is not None
    assert record.error.code == "component-name-ambiguous"
    # Original node value is left intact -- we never silently load into
    # the wrong bundle.
    assert payload["data"]["nodes"][0]["data"]["type"] == "ConflictedName"


@pytest.mark.unit
def test_payload_without_data_wrapper(table: MigrationTable) -> None:
    """``Graph.from_payload`` accepts both shapes; the rewriter must too."""
    payload = {"nodes": [_node("x", "OpenAIEmbeddings")], "edges": []}
    report = migrate_flow_payload(payload, table=table)
    assert report.rewritten_count == 1
    assert payload["nodes"][0]["data"]["type"] == "ext:openai:OpenAIEmbeddings@official"


@pytest.mark.unit
def test_malformed_node_skipped_silently(table: MigrationTable) -> None:
    """Note nodes / non-component shapes have no ``data.type`` -- skip them."""
    payload = {
        "data": {
            "nodes": [
                "not a dict",
                {"id": "x", "type": "noteNode"},  # no data
                {"id": "y", "data": "not a dict"},
                {"id": "z", "data": {"id": "z"}},  # no type
                _node("ok", "OpenAIEmbeddings"),
            ],
            "edges": [],
        }
    }
    report = migrate_flow_payload(payload, table=table)
    # Only the 'ok' node was visited.
    assert len(report.records) == 1
    assert report.records[0].outcome == "rewritten"


@pytest.mark.unit
def test_non_dict_payload_raises_type_error(table: MigrationTable) -> None:
    with pytest.raises(TypeError):
        migrate_flow_payload([], table=table)  # type: ignore[arg-type]


@pytest.mark.unit
def test_idempotent_when_run_twice(table: MigrationTable) -> None:
    payload = _payload(_node("x", "OpenAIEmbeddings"))
    first = migrate_flow_payload(payload, table=table)
    second = migrate_flow_payload(payload, table=table)
    assert first.rewritten_count == 1
    assert second.rewritten_count == 0
    assert second.records[0].outcome == "already_canonical"
