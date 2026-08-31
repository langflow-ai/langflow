from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

sys.path.insert(0, str(Path(__file__).resolve().parent))

from manage_bundle_profiles import (
    DEFAULT_LOCKS,
    DEFAULT_PROFILES,
    REPO_ROOT,
    check_locks,
    compile_profile,
    discover_bundle_catalog,
    read_json,
    validate_contract,
    validate_installed,
)


def load_contract() -> dict:
    return read_json(DEFAULT_PROFILES)


def test_reviewed_profiles_and_locks_are_current() -> None:
    assert check_locks(DEFAULT_PROFILES, DEFAULT_LOCKS) == []


def test_every_supported_downstream_image_family_selects_a_build_time_profile() -> None:
    contract = load_contract()

    assert contract["image_families"] == {
        "enterprise-ubi-hardened": {
            "install_phase": "build",
            "profile": "enterprise-hardened",
        }
    }
    _, errors = validate_contract(contract)
    assert errors == []


def test_profile_compilation_is_deterministic() -> None:
    contract = load_contract()
    catalog = discover_bundle_catalog()

    first = compile_profile(contract, "enterprise-hardened", catalog)
    second = compile_profile(contract, "enterprise-hardened", catalog)

    assert first == second
    assert first["image_families"] == ["enterprise-ubi-hardened"]
    assert first["application"]["requirement"] == "langflow==1.12.0"
    assert first["bundle_api"]["requirement"] == "lfx==1.12.0"
    assert first["bundles"] == sorted(first["bundles"], key=lambda item: item["distribution"])


def test_profile_matches_application_bundle_dependencies_exactly() -> None:
    contract = load_contract()
    profile = contract["profiles"]["enterprise-hardened"]
    declared = {item["distribution"] for item in profile["bundles"]}

    root_project = __import__("tomllib").loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    application = {
        canonicalize_name(Requirement(value).name)
        for value in root_project["dependencies"]
        if canonicalize_name(Requirement(value).name).startswith("lfx-")
    }

    assert declared == application


def test_unknown_bundle_is_rejected() -> None:
    contract = load_contract()
    profile = contract["profiles"]["enterprise-hardened"]
    profile["bundles"].append(
        {
            "distribution": "lfx-unknown",
            "extras": [],
            "version": ">=1,<2",
            "providers": ["unknown"],
        }
    )

    _, errors = validate_contract(contract)

    assert any("unknown bundle distribution 'lfx-unknown'" in error for error in errors)


def test_runtime_profile_selection_is_rejected() -> None:
    contract = load_contract()
    contract["image_families"]["enterprise-ubi-hardened"]["install_phase"] = "runtime"

    _, errors = validate_contract(contract)

    assert any("must install bundles at build time" in error for error in errors)


def test_unbounded_python_range_is_rejected() -> None:
    contract = load_contract()
    contract["profiles"]["enterprise-hardened"]["python"] = ">=3.10"

    _, errors = validate_contract(contract)

    assert any("Python version" in error and "must have lower and upper bounds" in error for error in errors)


def test_unbounded_bundle_range_is_rejected() -> None:
    contract = load_contract()
    contract["profiles"]["enterprise-hardened"]["bundles"][0]["version"] = ">=0.1.0"

    _, errors = validate_contract(contract)

    assert any("must have lower and upper bounds" in error for error in errors)


def test_unknown_extra_is_rejected() -> None:
    contract = load_contract()
    contract["profiles"]["enterprise-hardened"]["bundles"][0]["extras"] = ["unknown"]

    _, errors = validate_contract(contract)

    assert any("has unknown extras ['unknown']" in error for error in errors)


def test_duplicate_provider_is_rejected() -> None:
    contract = load_contract()
    profile = contract["profiles"]["enterprise-hardened"]
    profile["bundles"][1]["providers"] = profile["bundles"][0]["providers"]

    _, errors = validate_contract(contract)

    assert any("provider inventory must be" in error for error in errors)
    assert any("duplicate providers declared" in error for error in errors)


def test_undeclared_application_bundle_is_rejected() -> None:
    contract = load_contract()
    contract["profiles"]["enterprise-hardened"]["bundles"].pop()

    _, errors = validate_contract(contract)

    assert any("application bundle source drift" in error and "undeclared" in error for error in errors)


def test_installed_inventory_rejects_transitive_and_provider_drift() -> None:
    contract = load_contract()
    catalog = discover_bundle_catalog()
    lock = compile_profile(contract, "enterprise-hardened", catalog)
    distributions = {item["distribution"]: item["resolved_version"] for item in lock["bundles"]}
    providers = {provider: [item["distribution"]] for item in lock["bundles"] for provider in item["providers"]}
    distributions["lfx-unknown"] = "1.0.0"
    providers["unknown"] = ["lfx-unknown"]
    first_provider = lock["providers"][0]
    providers[first_provider].append("lfx-unknown")

    errors = validate_installed(lock, distributions, providers)

    assert any("undeclared transitive bundle distributions" in error for error in errors)
    assert any("undeclared providers installed" in error for error in errors)
    assert any("duplicate providers installed" in error for error in errors)


def test_checked_in_lock_requires_an_intentional_profile_diff(tmp_path: Path) -> None:
    contract = load_contract()
    contract["profiles"]["enterprise-hardened"]["description"] += " Changed."
    profiles_path = tmp_path / "profiles.json"
    profiles_path.write_text(json.dumps(contract), encoding="utf-8")

    errors = check_locks(profiles_path, DEFAULT_LOCKS)

    assert any("stale bundle profile lock" in error for error in errors)


def test_contract_validation_does_not_mutate_input() -> None:
    contract = load_contract()
    original = copy.deepcopy(contract)

    validate_contract(contract)

    assert contract == original
