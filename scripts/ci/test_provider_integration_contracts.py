"""Later-provider drift, ownership, and historical gate isolation contracts."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from check_capability_manifests import compare, validate_all
from provider_integration_contracts import validate_contracts


@pytest.fixture
def provider_contract(tmp_path):
    bundle = tmp_path / "bundles" / "acme" / "src" / "lfx_acme"
    bundle.mkdir(parents=True)
    extension_path = bundle / "extension.json"
    extension = {
        "id": "lfx-acme",
        "bundles": [{"name": "acme", "path": "components/acme"}],
        "integrations": [{"provider_id": "acme", "bundle": "acme", "path": "capabilities.v1.json"}],
    }
    extension_path.write_text(json.dumps(extension))
    manifest_path = bundle / "components" / "acme" / "capabilities.v1.json"
    manifest_path.parent.mkdir(parents=True)
    manifest = {
        "schema_version": 1,
        "provider_id": "acme",
        "display_name": "Acme",
        "auth_profiles": [{"id": "user", "identity": "user_delegated", "supports_refresh": True}],
        "capabilities": [
            {
                "id": "acme.records.read",
                "auth_profile_id": "user",
                "required_scopes": ["read"],
                "deployment_contexts": ["self_managed"],
                "risk": "read",
                "maturity": "preview",
                "component_ref": "AcmeReadComponent",
                "policy_keys": ["integrations.acme.records.read"],
            }
        ],
    }
    manifest_path.write_text(json.dumps(manifest))
    contract_root = tmp_path / "contracts"
    contract_root.mkdir()
    contract_path = contract_root / "acme.v1.json"
    contract = {
        "schema_version": 1,
        "provider_id": "acme",
        "distribution": "lfx-acme",
        "manifest": manifest,
        "sources": [{"url": "https://developer.example.com/api", "title": "Official API", "verified_on": "2026-01-01"}],
        "transport_limitations": ["Polling observes only the latest state."],
        "evidence_paths": [str(manifest_path.relative_to(tmp_path))],
        "owner_acceptance": {"status": "pending", "note": "Owner and live-tenant acceptance remain pending."},
    }
    contract_path.write_text(json.dumps(contract))
    index = {"schema_version": 1, "providers": [{"provider_id": "acme", "contract": "acme.v1.json"}]}
    (contract_root / "index.json").write_text(json.dumps(index))
    return tmp_path, contract_root, contract_path, contract, manifest_path, [("acme", extension_path, manifest_path)]


def test_complete_later_contract_passes_without_a_wave_one_matrix(provider_contract):
    root, contracts, _path, _contract, _manifest, manifests = provider_contract
    assert validate_contracts(manifests, contract_root=contracts, repo_root=root) == []
    # validate_all intentionally uses the repository for evidence resolution.
    # Point the fixture's evidence to one real source so only matrix dispatch is under test.
    contract = json.loads(_path.read_text())
    contract["evidence_paths"] = ["scripts/ci/test_provider_integration_contracts.py"]
    _path.write_text(json.dumps(contract))
    assert validate_all(bundles_root=root / "bundles", design_root=root / "no-wave-one", contract_root=contracts) == []


@pytest.mark.parametrize("field", ["auth_profiles", "capabilities", "display_name"])
def test_any_manifest_projection_drift_is_rejected(provider_contract, field):
    root, contracts, _path, contract, manifest_path, manifests = provider_contract
    manifest = copy.deepcopy(contract["manifest"])
    manifest[field] = [] if field != "display_name" else "Different"
    manifest_path.write_text(json.dumps(manifest))
    errors = validate_contracts(manifests, contract_root=contracts, repo_root=root)
    assert any("manifest differs" in error for error in errors)


def test_an_extra_capability_is_rejected(provider_contract):
    root, contracts, _path, contract, manifest_path, manifests = provider_contract
    manifest = copy.deepcopy(contract["manifest"])
    manifest["capabilities"].append({"id": "acme.records.delete", "risk": "destructive"})
    manifest_path.write_text(json.dumps(manifest))
    assert any(
        "manifest differs" in error for error in validate_contracts(manifests, contract_root=contracts, repo_root=root)
    )


@pytest.mark.parametrize(
    ("field", "value", "fragment"),
    [
        ("provider_id", "other", "provider ownership"),
        ("distribution", "lfx-other", "distribution"),
        ("sources", [], "sources"),
        ("sources", [{"url": 42, "title": "Bad", "verified_on": "2026-01-01"}], "source metadata"),
        ("transport_limitations", [], "transport limitations"),
        ("evidence_paths", ["../outside"], "evidence path"),
        ("owner_acceptance", {"status": "accepted", "note": "Claimed without an owner."}, "named owner"),
    ],
)
def test_invalid_evidence_and_unowned_acceptance_fail(provider_contract, field, value, fragment):
    root, contracts, path, contract, _manifest, manifests = provider_contract
    contract[field] = value
    path.write_text(json.dumps(contract))
    assert any(fragment in error for error in validate_contracts(manifests, contract_root=contracts, repo_root=root))


@pytest.mark.parametrize(
    ("entries", "fragment"),
    [
        ([], "no indexed"),
        ([{"provider_id": "acme", "contract": "missing.json"}], "cannot read"),
        ([{"provider_id": "acme", "contract": "acme.v1.json"}] * 2, "duplicates"),
        ([{"provider_id": "other", "contract": "acme.v1.json"}], "stale entry"),
        ([{"provider_id": "acme", "contract": "../outside.json"}], "invalid provider or contract path"),
        ([{"provider_id": "slack", "contract": "acme.v1.json"}], "invalid provider or contract path"),
    ],
)
def test_missing_duplicate_stale_and_escaping_index_entries_fail(provider_contract, entries, fragment):
    root, contracts, _path, _contract, _manifest, manifests = provider_contract
    (contracts / "index.json").write_text(json.dumps({"schema_version": 1, "providers": entries}))
    assert any(fragment in error for error in validate_contracts(manifests, contract_root=contracts, repo_root=root))


def test_duplicate_shipped_provider_ownership_fails(provider_contract):
    root, contracts, _path, _contract, _manifest, manifests = provider_contract
    assert any(
        "multiple shipped" in error
        for error in validate_contracts(manifests * 2, contract_root=contracts, repo_root=root)
    )


def test_missing_historical_matrix_still_fails(tmp_path):
    from check_capability_manifests import DEFAULT_BUNDLES_ROOT

    manifest = DEFAULT_BUNDLES_ROOT / "slack/src/lfx_slack/components/slack/capabilities.v1.json"
    assert any("no capability matrix" in error for error in compare("slack", manifest, tmp_path / "absent.json"))
