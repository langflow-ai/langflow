"""Manifest/matrix drift checker tests, plus the live lfx-slack manifest."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from check_capability_manifests import (
    DEFAULT_BUNDLES_ROOT,
    DEFAULT_DESIGN_ROOT,
    DELIBERATE_DEVIATIONS,
    compare,
    discover_manifests,
    validate_all,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SLACK_MANIFEST = REPO_ROOT / "src/bundles/slack/src/lfx_slack/components/slack/capabilities.v1.json"
MICROSOFT_MANIFEST = REPO_ROOT / "src/bundles/microsoft/src/lfx_microsoft/components/microsoft/capabilities.v1.json"
MICROSOFT_MATRIX = DEFAULT_DESIGN_ROOT / "matrices" / "microsoft.json"


def test_every_shipped_manifest_agrees_with_its_matrix() -> None:
    assert validate_all() == []


def test_the_slack_bundle_is_discovered() -> None:
    discovered = {provider for provider, _extension, _manifest in discover_manifests(DEFAULT_BUNDLES_ROOT)}

    assert "slack" in discovered


def test_the_microsoft_bundle_is_discovered() -> None:
    """INT-11 and INT-12 ship side by side; one checker covers both."""
    discovered = {provider for provider, _extension, _manifest in discover_manifests(DEFAULT_BUNDLES_ROOT)}

    assert "microsoft" in discovered


def test_slack_declares_no_deviations() -> None:
    assert "slack" not in DELIBERATE_DEVIATIONS


def test_the_microsoft_deviations_are_exactly_the_two_recorded_ones() -> None:
    """Amending them must be a deliberate edit here, not a silent manifest change."""
    assert DELIBERATE_DEVIATIONS["microsoft"] == {
        "display_name": "Microsoft 365",
        "registration_only_scopes": ["offline_access"],
    }


def test_the_microsoft_deviations_are_still_real() -> None:
    matrix = json.loads(MICROSOFT_MATRIX.read_text(encoding="utf-8"))
    manifest = json.loads(MICROSOFT_MANIFEST.read_text(encoding="utf-8"))

    assert matrix["display_name"] != manifest["display_name"]
    required = {
        scope["scope"] for action in matrix["actions"] if action["decision"] == "include" for scope in action["scopes"]
    }
    assert "offline_access" in required
    assert all("offline_access" not in c["required_scopes"] for c in manifest["capabilities"])


def test_a_deviation_that_has_converged_is_reported_as_stale(tmp_path: Path) -> None:
    matrix = json.loads(MICROSOFT_MATRIX.read_text(encoding="utf-8"))
    matrix["display_name"] = DELIBERATE_DEVIATIONS["microsoft"]["display_name"]
    matrix_path = tmp_path / "microsoft.json"
    matrix_path.write_text(json.dumps(matrix), encoding="utf-8")

    errors = compare("microsoft", MICROSOFT_MANIFEST, matrix_path)

    assert any("now equals the matrix" in error for error in errors), errors


def test_a_registration_only_scope_the_matrix_dropped_is_reported_as_stale(tmp_path: Path) -> None:
    matrix = json.loads(MICROSOFT_MATRIX.read_text(encoding="utf-8"))
    for action in matrix["actions"]:
        action["scopes"] = [scope for scope in action["scopes"] if scope["scope"] != "offline_access"]
    matrix_path = tmp_path / "microsoft.json"
    matrix_path.write_text(json.dumps(matrix), encoding="utf-8")

    errors = compare("microsoft", MICROSOFT_MANIFEST, matrix_path)

    assert any("no longer required by any matrix row" in error for error in errors), errors


def test_microsoft_drift_outside_the_deviations_still_fails(tmp_path: Path) -> None:
    """The allowlist is scope-specific: any other scope drift is still a failure."""
    manifest = json.loads(MICROSOFT_MANIFEST.read_text(encoding="utf-8"))
    manifest["capabilities"][0]["required_scopes"] = ["offline_access"]
    path = tmp_path / "capabilities.v1.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    errors = compare("microsoft", path, MICROSOFT_MATRIX)

    assert any("required_scopes" in error for error in errors), errors


def _write_variant(tmp_path: Path, mutate) -> Path:
    manifest = json.loads(SLACK_MANIFEST.read_text(encoding="utf-8"))
    mutate(manifest)
    path = tmp_path / "capabilities.v1.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def _capability(manifest: dict, capability_id: str) -> dict:
    return next(capability for capability in manifest["capabilities"] if capability["id"] == capability_id)


@pytest.mark.parametrize(
    ("mutate", "fragment"),
    [
        (
            lambda m: _capability(m, "slack.user.search")["required_scopes"].append("channels:history"),
            "required_scopes",
        ),
        (
            lambda m: _capability(m, "slack.bot.post")["deployment_contexts"].append("desktop"),
            "deployment_contexts",
        ),
        (
            lambda m: m["capabilities"].remove(_capability(m, "slack.user.canvas")),
            "has no capability",
        ),
        (
            lambda m: _capability(m, "slack.user.send").__setitem__("component_ref", "SlackSomethingElseComponent"),
            "component_ref",
        ),
        (
            lambda m: _capability(m, "slack.user.search").__setitem__("identity", "bot"),
            "identity",
        ),
        (
            lambda m: _capability(m, "slack.bot.add_reaction").__setitem__("policy_keys", ["integrations.google.x"]),
            "outside integrations.slack.",
        ),
        (
            lambda m: _capability(m, "slack.user.search").__setitem__("auth_profile_id", "slack-app-token"),
            "unknown auth profile",
        ),
        (
            lambda m: _capability(m, "slack.bot.list_channel_members")["conditional_scopes"].clear(),
            "conditional_scopes",
        ),
    ],
)
def test_drift_is_reported(tmp_path: Path, mutate, fragment: str) -> None:
    path = _write_variant(tmp_path, mutate)

    errors = compare("slack", path, DEFAULT_DESIGN_ROOT / "matrices" / "slack.json")

    assert errors, "expected the checker to reject this manifest"
    assert any(fragment in error for error in errors), errors


def test_extra_capabilities_and_profiles_are_allowed(tmp_path: Path) -> None:
    """TRG-5 adds an app-token profile and trigger capabilities the action matrix does not describe."""

    def mutate(manifest: dict) -> None:
        manifest["auth_profiles"].append(
            {
                "id": "slack-app-token",
                "kind": "api_key",
                "identity": "bot",
                "scope_separator": ",",
            }
        )
        manifest["capabilities"].append(
            {
                "id": "slack.trigger.events",
                "display_name": "Slack: On Event",
                "auth_profile_id": "slack-app-token",
                "identity": "bot",
                "required_scopes": [],
                "conditional_scopes": [],
                "policy_keys": ["integrations.slack.trigger.events"],
                "substrate": "rest",
                "maturity": "ga",
                "deployment_contexts": ["hosted"],
                "risk": "read",
                "component_ref": "SlackEventTriggerComponent",
            }
        )

    path = _write_variant(tmp_path, mutate)

    assert compare("slack", path, DEFAULT_DESIGN_ROOT / "matrices" / "slack.json") == []


def test_a_missing_matrix_is_an_error(tmp_path: Path) -> None:
    errors = compare("slack", SLACK_MANIFEST, tmp_path / "nope.json")

    assert len(errors) == 1
    assert "no capability matrix" in errors[0]
