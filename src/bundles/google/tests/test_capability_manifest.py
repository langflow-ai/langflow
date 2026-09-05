"""The Google capability manifest is the contract, so it is tested as one.

Three properties matter and none of them are checked by ``lfx extension validate``
alone:

1. The manifest agrees with ``design/dedicated-integrations/matrices/google.json``
   exactly — the same five actions, the same scopes, the same class names. This is
   the ticket's "requested scopes match the approved matrix" requirement.
2. Every ``ConnectionRefInput`` on a shipped component declares the same scope its
   capability declares. Nothing enforces the manifest at runtime yet (INT-7 is the
   future consumer), so scope enforcement today comes entirely from the component
   field; a drift between the two would silently request the wrong grant.
3. The JSON is inside the built wheel. It is data the loader reads from the
   installed package, and the hatch include list defaults to ``*.py``.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from lfx.extension import load_extension, validate_extension
from lfx_google.components import google as google_components

BUNDLE_ROOT = Path(__file__).resolve().parents[1]
EXTENSION_ROOT = BUNDLE_ROOT / "src" / "lfx_google"
MANIFEST_PATH = EXTENSION_ROOT / "components" / "google" / "capabilities.v1.json"
REPO_ROOT = BUNDLE_ROOT.parents[2]
MATRIX_PATH = REPO_ROOT / "design" / "dedicated-integrations" / "matrices" / "google.json"


def _manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _included_matrix_actions() -> dict[str, dict]:
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    return {action["action_id"]: action for action in matrix["actions"] if action["decision"] == "include"}


def test_extension_validate_accepts_the_manifest() -> None:
    report = validate_extension(EXTENSION_ROOT)

    assert report.ok, [error.code for error in report.errors.errors]


def test_loader_exposes_the_google_provider() -> None:
    result = load_extension(EXTENSION_ROOT, distribution="lfx-google")

    assert result.ok, result.errors
    assert len(result.integrations) == 1
    integration = result.integrations[0]
    assert integration.provider_id == "google"
    assert integration.bundle == "google"
    assert integration.capability_manifest.schema_version == 1


def test_manifest_actions_match_the_capability_matrix() -> None:
    expected = _included_matrix_actions()
    capabilities = {capability["id"]: capability for capability in _manifest()["capabilities"]}

    assert set(capabilities) == set(expected), "manifest and matrix disagree on the included action set"
    for action_id, action in expected.items():
        capability = capabilities[action_id]
        matrix_scopes = [entry["scope"] for entry in action["scopes"] if entry["role"] == "required"]
        assert capability["required_scopes"] == matrix_scopes, action_id
        assert capability["display_name"] == action["display_name"], action_id
        assert capability["component_ref"] == action["component_class"], action_id
        assert capability["substrate"] == action["substrate"], action_id
        assert capability["identity"] == action["identity"], action_id


def test_gmail_search_is_not_shipped() -> None:
    # decisions/google-restricted-scopes.md Option B: gmail.readonly is restricted
    # and the wave-1 hosted app requests no restricted scope.
    capability_ids = {capability["id"] for capability in _manifest()["capabilities"]}

    assert "google.gmail.search" not in capability_ids
    assert not hasattr(google_components, "GmailSearchComponent")


def test_no_capability_requests_a_restricted_scope() -> None:
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    avoided = {entry["scope"] for entry in matrix["restricted_scope_decisions"] if entry["decision"] == "avoid"}
    declared = {scope for capability in _manifest()["capabilities"] for scope in capability["required_scopes"]}

    assert declared.isdisjoint(avoided)


def test_policy_keys_are_namespaced_per_capability() -> None:
    for capability in _manifest()["capabilities"]:
        assert capability["policy_keys"], capability["id"]
        for key in capability["policy_keys"]:
            assert key.startswith("integrations.google."), key


def test_every_component_ref_resolves_to_an_exported_class() -> None:
    for capability in _manifest()["capabilities"]:
        component_ref = capability["component_ref"]
        assert component_ref in google_components.__all__, component_ref
        assert getattr(google_components, component_ref, None) is not None, component_ref


def test_component_connection_scopes_match_the_manifest() -> None:
    """The component field, not the manifest, is what the resolver enforces today."""
    for capability in _manifest()["capabilities"]:
        component_class = getattr(google_components, capability["component_ref"])
        connection_fields = [field for field in component_class.inputs if field.name == "connection"]
        assert len(connection_fields) == 1, capability["component_ref"]
        connection = connection_fields[0]
        assert connection.provider == "google"
        assert connection.auth_profile_id == capability["auth_profile_id"]
        assert connection.required_scopes == list(capability["required_scopes"]), capability["id"]
        assert connection.capabilities == [capability["id"]]
        assert connection.required is True


def test_scopes_are_declared_as_full_google_urls() -> None:
    # The broker stores the scope strings Google returns and the DB resolver
    # compares them as raw strings, so a short suffix never matches.
    for capability in _manifest()["capabilities"]:
        for scope in capability["required_scopes"]:
            assert scope.startswith("https://www.googleapis.com/auth/"), scope


@pytest.mark.skipif(shutil.which("uv") is None, reason="uv is required to build the wheel")
def test_capability_manifest_ships_inside_the_wheel(tmp_path: Path) -> None:
    """Contract data has to be packaged, not just present in the source tree."""
    subprocess.run(  # noqa: S603 - fixed argv, no shell
        [shutil.which("uv"), "build", "--wheel", "--out-dir", str(tmp_path), str(BUNDLE_ROOT)],
        check=True,
        capture_output=True,
    )
    wheels = list(tmp_path.glob("lfx_google-*.whl"))
    assert wheels, "no wheel was produced"
    with zipfile.ZipFile(wheels[0]) as archive:
        names = set(archive.namelist())
    assert "lfx_google/components/google/capabilities.v1.json" in names


@pytest.mark.skipif(shutil.which("uv") is None, reason="uv is required to build the wheel")
def test_manifest_is_readable_from_an_installed_wheel(tmp_path: Path) -> None:
    """Import the manifest the way a pip install would see it, in a clean process."""
    subprocess.run(  # noqa: S603 - fixed argv, no shell
        [shutil.which("uv"), "build", "--wheel", "--out-dir", str(tmp_path), str(BUNDLE_ROOT)],
        check=True,
        capture_output=True,
    )
    wheel = next(iter(tmp_path.glob("lfx_google-*.whl")))
    unpacked = tmp_path / "unpacked"
    with zipfile.ZipFile(wheel) as archive:
        archive.extractall(unpacked)  # our own freshly built wheel

    script = (
        "import json,sys,pathlib;"
        "p=pathlib.Path(sys.argv[1])/'lfx_google'/'components'/'google'/'capabilities.v1.json';"
        "d=json.loads(p.read_text());"
        "print(len(d['capabilities']))"
    )
    completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [sys.executable, "-c", script, str(unpacked)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout.strip() == "5"
