"""Compare complete release registries with Langflow's shared compatibility rule."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

from packaging.utils import InvalidName, canonicalize_name
from packaging.version import InvalidVersion, Version

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping
    from pathlib import Path


class CompatibilityGateError(ValueError):
    """Release evidence is missing, incomplete, or inconsistent."""


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate_snapshot(snapshot: dict[str, Any]) -> None:
    if snapshot.get("format_version") != 1 or snapshot.get("complete") is not True:
        msg = "a complete format1 registry snapshot is required"
        raise CompatibilityGateError(msg)
    if not isinstance(snapshot.get("distributions"), dict) or not snapshot["distributions"]:
        msg = "the snapshot must identify its installed distributions"
        raise CompatibilityGateError(msg)
    if not isinstance(snapshot.get("all_types"), dict) or not snapshot["all_types"]:
        msg = "the snapshot registry is empty"
        raise CompatibilityGateError(msg)
    if not isinstance(snapshot.get("component_packages"), dict):
        msg = "the snapshot must identify each component's distribution"
        raise CompatibilityGateError(msg)
    for components in snapshot["all_types"].values():
        if not isinstance(components, dict):
            msg = "component categories must be mappings"
            raise CompatibilityGateError(msg)
        for key, entry in components.items():
            if not isinstance(entry, dict) or not isinstance(entry.get("template"), dict) or not entry["template"]:
                msg = f"{key} has no component template"
                raise CompatibilityGateError(msg)
            if not isinstance(entry.get("outputs"), list) or key not in snapshot["component_packages"]:
                msg = f"{key} has no output contract or distribution provenance"
                raise CompatibilityGateError(msg)


@dataclass(frozen=True)
class ContractChange:
    distribution: str
    component: str
    source_version: str
    target_version: str
    before_sha256: str
    after_sha256: str | None
    reasons: tuple[dict[str, str | None], ...]

    @property
    def id(self) -> str:
        return digest(asdict(self))

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, **asdict(self)}


def contract(entry: Mapping[str, Any]) -> dict[str, Any]:
    """Bind acknowledgments to compatibility inputs rather than implementation code."""
    template = copy.deepcopy(entry.get("template", {}))
    template.pop("code", None)
    return {
        "template": template,
        "outputs": entry.get("outputs", []),
        "custom_fields": entry.get("custom_fields"),
        "retired_in": entry.get("retired_in"),
        "replacement": entry.get("replacement"),
    }


def compare_registries(
    previous: dict[str, Any], current: dict[str, Any], distribution: str, *, whole_registry: bool = False
) -> list[ContractChange]:
    """Check every prior contract even when its implementation code is unchanged."""
    from lfx.upgrade.checker import breaking_reasons, build_registry_lookup

    validate_snapshot(previous)
    validate_snapshot(current)
    source_version = previous["distributions"].get(distribution)
    target_version = current["distributions"].get(distribution)
    if not source_version or not target_version:
        msg = f"{distribution} is missing from snapshot distribution versions"
        raise CompatibilityGateError(msg)
    lookup = build_registry_lookup(current["all_types"])
    changes: list[ContractChange] = []
    seen: set[str] = set()
    for components in previous["all_types"].values():
        for key, before in sorted(components.items()):
            if key in seen or (not whole_registry and previous["component_packages"][key] != distribution):
                continue
            seen.add(key)
            after = lookup.get(key)
            if after is None:
                reasons = [{"code": "component_removed", "field": None, "message": "the component is unavailable"}]
            elif after.get("retired_in") and not before.get("retired_in"):
                reasons = [{"code": "component_retired", "field": None, "message": "the component is now retired"}]
            else:
                saved = copy.deepcopy(before)
                # Any old input may contain a saved value and a connection.
                for name, field in saved["template"].items():
                    if name != "code" and isinstance(field, dict) and field.get("value") in (None, "", [], {}):
                        field["value"] = "compatibility-saved-value"
                reasons = [asdict(reason) for reason in breaking_reasons(after, saved, connected_fields=None)]
            if reasons:
                changes.append(
                    ContractChange(
                        distribution,
                        key,
                        source_version,
                        target_version,
                        digest(contract(before)),
                        digest(contract(after)) if after is not None else None,
                        tuple(reasons),
                    )
                )
    if not seen:
        msg = f"{distribution} exported no prior component contracts"
        raise CompatibilityGateError(msg)
    return changes


SCOPED_ACKNOWLEDGMENT_FORMAT = 2
ComparisonScope = tuple[str, str, str]


def _acknowledgment_scope(entry: dict[str, Any]) -> ComparisonScope:
    distribution = entry["distribution"]
    source_version = entry["source_version"]
    target_version = entry["target_version"]
    msg = "a break acknowledgment needs a canonical distribution name and valid comparison versions"
    try:
        if (
            isinstance(distribution, str)
            and canonicalize_name(distribution, validate=True) == distribution
            and isinstance(source_version, str)
            and isinstance(target_version, str)
        ):
            Version(source_version)
            Version(target_version)
            return distribution, source_version, target_version
    except (InvalidName, InvalidVersion) as exc:
        raise CompatibilityGateError(msg) from exc
    raise CompatibilityGateError(msg)


def review_acknowledgments(
    changes: list[ContractChange],
    document: dict[str, Any],
    root: Path,
    *,
    comparisons: Collection[ComparisonScope] | None = None,
) -> str:
    """Validate acknowledgments and render the notes for the selected comparisons."""
    format_version = document.get("format_version")
    if format_version not in (1, SCOPED_ACKNOWLEDGMENT_FORMAT) or not isinstance(document.get("breaks"), list):
        msg = "compatibility acknowledgments require format_version 1 or 2 and a breaks list"
        raise CompatibilityGateError(msg)
    scoped = format_version == SCOPED_ACKNOWLEDGMENT_FORMAT
    required_fields = {"id", "reason", "release_note"}
    if scoped:
        if comparisons is None:
            msg = "versioned acknowledgments require the selected comparisons"
            raise CompatibilityGateError(msg)
        required_fields.update(("distribution", "source_version", "target_version"))
    actual = {change.id: change for change in changes}
    seen: set[str] = set()
    acknowledged: set[str] = set()
    notes = ["# Component compatibility changes", ""]
    notes_root = (root / "docs" / "release_notes" / "compatibility").resolve()
    for entry in document["breaks"]:
        if not isinstance(entry, dict) or set(entry) != required_fields:
            msg = f"each acknowledgment requires exactly these fields: {', '.join(sorted(required_fields))}"
            raise CompatibilityGateError(msg)
        identity = entry["id"]
        if not isinstance(identity, str) or re.fullmatch(r"[a-f0-9]{64}", identity) is None:
            msg = "a break acknowledgment needs a SHA-256 break identity"
            raise CompatibilityGateError(msg)
        if identity in seen:
            msg = f"duplicate break acknowledgment {identity}"
            raise CompatibilityGateError(msg)
        seen.add(identity)
        if not isinstance(entry["reason"], str) or not entry["reason"].strip():
            msg = "a break acknowledgment needs a reason"
            raise CompatibilityGateError(msg)
        if not isinstance(entry["release_note"], str):
            msg = "a break acknowledgment needs a release-note path"
            raise CompatibilityGateError(msg)
        path = (root / entry["release_note"]).resolve()
        if not path.is_relative_to(notes_root) or not path.is_file() or path.suffix != ".md":
            msg = "release notes must be existing Markdown files under docs/release_notes/compatibility"
            raise CompatibilityGateError(msg)
        text = path.read_text(encoding="utf-8").strip()
        if identity not in text:
            msg = "release notes must name the exact break identity"
            raise CompatibilityGateError(msg)
        scope = _acknowledgment_scope(entry) if scoped else None
        if scope is not None and comparisons is not None and scope not in comparisons:
            continue
        change = actual.get(identity)
        if change is None:
            msg = f"unknown or stale break acknowledgment {identity}"
            raise CompatibilityGateError(msg)
        if scope is not None and scope != (change.distribution, change.source_version, change.target_version):
            msg = f"break acknowledgment {identity} belongs to a different comparison"
            raise CompatibilityGateError(msg)
        if change.component not in text:
            msg = "release notes must name the component"
            raise CompatibilityGateError(msg)
        acknowledged.add(identity)
        notes.extend([text, ""])
    missing = sorted(set(actual) - acknowledged)
    if missing:
        msg = "unacknowledged component breaks " + ", ".join(missing)
        raise CompatibilityGateError(msg)
    if not changes:
        notes.append("No acknowledged component contract breaks were found.")
    return "\n".join(notes) + "\n"
