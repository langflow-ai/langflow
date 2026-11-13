"""Release contracts must detect breaks regardless of implementation code changes."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

import pytest
from component_compatibility import (
    CompatibilityGateError,
    compare_registries,
    review_acknowledgments,
    validate_snapshot,
)
from component_release_plan import previous_release


def component():
    return {
        "template": {
            "code": {"value": "unchanged implementation"},
            "hidden_input": {"type": "str", "input_types": ["Message"], "value": "", "show": False},
        },
        "outputs": [{"name": "result", "types": ["Message"], "selected": "Message"}],
    }


def snapshot(entries=None, *, version="0.3.0", package="lfx-example"):
    entries = {"Example": component()} if entries is None else entries
    return {
        "format_version": 1,
        "complete": True,
        "distributions": {package: version},
        "all_types": {"test": entries},
        "component_packages": dict.fromkeys(entries, package),
    }


@pytest.mark.parametrize("change", ["field", "output", "type", "connection", "retired", "component"])
@pytest.mark.component_runtime
def test_equal_code_still_detects_every_breaking_contract(change):
    previous = snapshot()
    current = copy.deepcopy(previous)
    entry = current["all_types"]["test"]["Example"]
    if change == "field":
        del entry["template"]["hidden_input"]
    elif change == "output":
        entry["outputs"] = []
    elif change == "type":
        entry["template"]["hidden_input"]["type"] = "int"
    elif change == "connection":
        entry["template"]["hidden_input"]["input_types"] = []
    elif change == "retired":
        entry["retired_in"] = "1.14.0"
    else:
        current = snapshot({"Other": component()})
    [result] = compare_registries(previous, current, "lfx-example")
    assert result.component == "Example"
    assert result.reasons
    assert previous == snapshot()


@pytest.mark.component_runtime
def test_new_optional_fields_are_compatible():
    previous = snapshot()
    current = copy.deepcopy(previous)
    current["all_types"]["test"]["Example"]["template"]["optional"] = {"type": "str", "value": ""}
    assert compare_registries(previous, current, "lfx-example") == []


@pytest.mark.component_runtime
def test_new_required_field_without_default_is_breaking():
    previous = snapshot()
    current = copy.deepcopy(previous)
    current["all_types"]["test"]["Example"]["template"]["required"] = {"required": True, "value": ""}
    [result] = compare_registries(previous, current, "lfx-example")
    assert result.reasons[0]["code"] == "required_input_missing"


@pytest.mark.component_runtime
def test_renamed_component_can_resolve_through_shared_aliases():
    previous = snapshot()
    current = snapshot({"ext:test:Example@official": {**component(), "name": "Example"}})
    assert compare_registries(previous, current, "lfx-example") == []


@pytest.mark.parametrize("mutation", ["incomplete", "empty", "provenance", "template"])
def test_incomplete_snapshots_fail_closed(mutation):
    current = snapshot()
    if mutation == "incomplete":
        current["complete"] = False
    elif mutation == "empty":
        current["all_types"] = {}
    elif mutation == "provenance":
        current["component_packages"] = {}
    else:
        current["all_types"]["test"]["Example"]["template"] = {}
    with pytest.raises(CompatibilityGateError):
        validate_snapshot(current)


@pytest.mark.parametrize(
    ("declared", "versions", "expected"),
    [
        ("0.3.0", ("0.2.0", "0.3.0", "0.4.0"), "0.3.0"),
        ("1.13.2", ("1.12.6", "1.13.1", "1.13.2", "1.14.0"), "1.13.2"),
        ("1.14.0rc1", ("1.13.9", "1.14.0rc1", "1.14.0"), "1.13.9"),
        ("1.14.0", ("1.13.9", "1.14.0rc1", "1.14.0.dev1", "1.14.0+local"), "1.13.9"),
        ("0.1.0", (), None),
    ],
)
def test_previous_release_policy(declared, versions, expected):
    assert previous_release(declared, versions) == expected


def breaking_change():
    current = snapshot()
    current["all_types"]["test"]["Example"]["outputs"] = []
    return compare_registries(snapshot(), current, "lfx-example")


def acknowledgment(changes, root: Path):
    note = root / "docs/release_notes/compatibility/example.md"
    note.parent.mkdir(parents=True)
    note.write_text(f"Example lost its result output.\n\nBreak identity {changes[0].id}\n")
    return {
        "format_version": 1,
        "breaks": [
            {"id": changes[0].id, "reason": "Removed obsolete output", "release_note": str(note.relative_to(root))}
        ],
    }


@pytest.mark.component_runtime
def test_acknowledged_changes_are_rendered_into_release_notes(tmp_path):
    changes = breaking_change()
    document = acknowledgment(changes, tmp_path)
    notes = review_acknowledgments(changes, document, tmp_path)
    assert "Example lost its result output" in notes
    assert changes[0].id in notes


@pytest.mark.parametrize("format_version", [1, 2])
@pytest.mark.parametrize("invalid", ["missing", "stale", "duplicate", "unpublished", "escape", "wrong_note"])
@pytest.mark.component_runtime
def test_invalid_acknowledgments_cannot_allow_a_break(invalid, format_version, tmp_path):
    changes = breaking_change()
    document = acknowledgment(changes, tmp_path)
    entry = document["breaks"][0]
    [change] = changes
    comparisons = {(change.distribution, change.source_version, change.target_version)}
    if format_version == 2:
        document["format_version"] = 2
        entry.update(
            distribution=change.distribution, source_version=change.source_version, target_version=change.target_version
        )
    if invalid == "missing":
        document["breaks"] = []
    elif invalid == "stale":
        entry["id"] = "0" * 64
        (tmp_path / entry["release_note"]).write_text(f"Example migration guidance for {entry['id']}")
    elif invalid == "duplicate":
        document["breaks"].append(entry)
    elif invalid == "unpublished":
        entry["release_note"] = "docs/release_notes/compatibility/missing.md"
    elif invalid == "escape":
        entry["release_note"] = "../outside.md"
    else:
        (tmp_path / entry["release_note"]).write_text("No migration guidance")
    with pytest.raises(CompatibilityGateError):
        review_acknowledgments(changes, document, tmp_path, comparisons=comparisons)


@pytest.mark.component_runtime
def test_provider_identity_and_saved_field_removal_use_the_shared_rule():
    key = "provider:Example:LanguageModelComponent"
    previous = snapshot({key: component()})
    current = snapshot({key: component()})
    del current["all_types"]["test"][key]["template"]["hidden_input"]
    [change] = compare_registries(previous, current, "lfx-example")
    assert change.reasons[0]["code"] == "field_removed"
    current = snapshot({"Other": component()})
    [change] = compare_registries(previous, current, "lfx-example")
    assert change.reasons[0]["code"] == "component_removed"
