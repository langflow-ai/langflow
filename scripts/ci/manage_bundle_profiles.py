"""Validate, resolve, and verify declarative downstream bundle profiles."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from contextlib import suppress
from importlib import metadata
from pathlib import Path
from typing import Any

import tomllib
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import Version

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROFILES = REPO_ROOT / "scripts" / "ci" / "bundle_profiles.json"
DEFAULT_LOCKS = REPO_ROOT / "scripts" / "ci" / "bundle_profile_locks"
AGGREGATE_EXTRAS = {"all", "all-no-torch"}
BUNDLE_INIT_PATH_PARTS = 3


class ProfileError(ValueError):
    """Raised when a bundle profile violates the release contract."""


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_project(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))["project"]


def canonical_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def profile_digest(profile: dict[str, Any]) -> str:
    encoded = json.dumps(profile, separators=(",", ":"), sort_keys=True).encode()
    return f"sha256:{hashlib.sha256(encoded).hexdigest()[:16]}"


def is_bounded(specifier: str) -> bool:
    specs = list(SpecifierSet(specifier))
    lower = any(item.operator in {">", ">=", "~=", "==", "==="} for item in specs)
    upper = any(item.operator in {"<", "<=", "~=", "==", "==="} for item in specs)
    return lower and upper


def discover_bundle_catalog(repo_root: Path = REPO_ROOT) -> dict[str, dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {}
    for pyproject_path in sorted((repo_root / "src" / "bundles").glob("*/pyproject.toml")):
        project = read_project(pyproject_path)
        distribution = canonicalize_name(project["name"])
        entry_points = project.get("entry-points", {})
        providers = sorted(entry_points.get("langflow.extensions", {}))
        optional = project.get("optional-dependencies", {})
        extras = sorted(optional)
        if distribution == "lfx-bundles":
            providers = sorted(name for name in optional if name not in AGGREGATE_EXTRAS)

        lfx_requirements = [
            Requirement(value)
            for value in project.get("dependencies", [])
            if canonicalize_name(Requirement(value).name) == "lfx"
        ]
        if len(lfx_requirements) != 1:
            message = f"{distribution} must declare exactly one lfx compatibility requirement"
            raise ProfileError(message)

        catalog[distribution] = {
            "distribution": distribution,
            "version": project["version"],
            "providers": providers,
            "extras": extras,
            "optional_dependencies": optional,
            "lfx_specifier": str(lfx_requirements[0].specifier),
            "path": str(pyproject_path.relative_to(repo_root)),
        }
    return catalog


def selected_providers(catalog_item: dict[str, Any]) -> list[str]:
    # lfx-bundles ships every provider's component code even when an extra is
    # omitted; extras select SDK dependencies, not the component inventory.
    return catalog_item["providers"]


def application_bundle_requirements(repo_root: Path, source: str) -> dict[str, Requirement]:
    project = read_project(repo_root / source)
    requirements = {}
    for value in project.get("dependencies", []):
        requirement = Requirement(value)
        name = canonicalize_name(requirement.name)
        if name.startswith("lfx-"):
            requirements[name] = requirement
    return requirements


def validate_profile(
    name: str,
    profile: dict[str, Any],
    catalog: dict[str, dict[str, Any]],
    repo_root: Path = REPO_ROOT,
) -> list[str]:
    required_fields = (
        "description",
        "owners",
        "update_cadence",
        "indexes",
        "python",
        "application",
        "bundle_api",
        "bundles",
    )
    errors = [f"{name}: missing required field {field!r}" for field in required_fields if field not in profile]
    errors.extend(
        f"{name}: field {field!r} must not be empty"
        for field in required_fields
        if field != "bundles" and field in profile and not profile[field]
    )

    python_specifier = profile.get("python", "")
    try:
        if not is_bounded(python_specifier):
            errors.append(f"{name}: Python version {python_specifier!r} must have lower and upper bounds")
    except ValueError as exc:
        errors.append(f"{name}: invalid Python version {python_specifier!r}: {exc}")

    application = profile.get("application", {})
    bundle_api = profile.get("bundle_api", {})
    for label, selection in (("application", application), ("bundle_api", bundle_api)):
        specifier = selection.get("version", "")
        try:
            if not is_bounded(specifier):
                errors.append(f"{name}: {label} version {specifier!r} must have lower and upper bounds")
        except ValueError as exc:
            errors.append(f"{name}: invalid {label} version {specifier!r}: {exc}")

    lfx_project = read_project(repo_root / "src" / "lfx" / "pyproject.toml")
    lfx_version = Version(lfx_project["version"])
    if bundle_api.get("distribution") != "lfx":
        errors.append(f"{name}: bundle_api distribution must be 'lfx'")
    else:
        try:
            if lfx_version not in SpecifierSet(bundle_api.get("version", "")):
                errors.append(f"{name}: current lfx {lfx_version} is outside the bundle_api range")
        except ValueError:
            pass

    root_project = read_project(repo_root / "pyproject.toml")
    if canonicalize_name(application.get("distribution", "")) != canonicalize_name(root_project["name"]):
        errors.append(f"{name}: application distribution must match {root_project['name']!r}")
    else:
        try:
            if Version(root_project["version"]) not in SpecifierSet(application.get("version", "")):
                errors.append(f"{name}: current application {root_project['version']} is outside its profile range")
        except ValueError:
            pass

    distributions: set[str] = set()
    provider_owners: dict[str, list[str]] = {}
    for item in profile.get("bundles", []):
        distribution = canonicalize_name(item.get("distribution", ""))
        if distribution in distributions:
            errors.append(f"{name}: duplicate bundle distribution {distribution!r}")
            continue
        distributions.add(distribution)

        catalog_item = catalog.get(distribution)
        if catalog_item is None:
            errors.append(f"{name}: unknown bundle distribution {distribution!r}")
            continue

        extras = item.get("extras")
        if not isinstance(extras, list):
            errors.append(f"{name}: {distribution} must declare extras as a list")
            continue
        if extras != sorted(set(extras)):
            errors.append(f"{name}: {distribution} extras must be unique and sorted")
        unknown_extras = sorted(set(extras) - set(catalog_item["extras"]))
        if unknown_extras:
            errors.append(f"{name}: {distribution} has unknown extras {unknown_extras}")

        specifier = item.get("version", "")
        try:
            if not is_bounded(specifier):
                errors.append(f"{name}: {distribution} version {specifier!r} must have lower and upper bounds")
            elif Version(catalog_item["version"]) not in SpecifierSet(specifier):
                errors.append(
                    f"{name}: source version {catalog_item['version']} for {distribution} is outside {specifier}"
                )
        except ValueError as exc:
            errors.append(f"{name}: invalid version range for {distribution}: {exc}")

        if lfx_version not in SpecifierSet(catalog_item["lfx_specifier"]):
            errors.append(
                f"{name}: {distribution} requires lfx{catalog_item['lfx_specifier']}, incompatible with {lfx_version}"
            )

        expected_providers = selected_providers(catalog_item) if not unknown_extras else []
        declared_providers = item.get("providers", [])
        if declared_providers != sorted(set(declared_providers)):
            errors.append(f"{name}: {distribution} providers must be unique and sorted")
        if declared_providers != expected_providers:
            errors.append(
                f"{name}: {distribution} provider inventory must be {expected_providers}, got {declared_providers}"
            )
        for provider in declared_providers:
            provider_owners.setdefault(provider, []).append(distribution)

    duplicates = {provider: owners for provider, owners in provider_owners.items() if len(owners) > 1}
    if duplicates:
        errors.append(f"{name}: duplicate providers declared by multiple distributions: {duplicates}")

    source = application.get("bundle_source")
    if source:
        try:
            application_requirements = application_bundle_requirements(repo_root, source)
        except (FileNotFoundError, KeyError, tomllib.TOMLDecodeError) as exc:
            errors.append(f"{name}: cannot read application bundle source {source!r}: {exc}")
        else:
            actual = set(application_requirements)
            if actual != distributions:
                errors.append(
                    f"{name}: application bundle source drift; undeclared={sorted(actual - distributions)}, "
                    f"not-installed-by-application={sorted(distributions - actual)}"
                )
            for distribution in sorted(actual & distributions):
                declared = next(
                    item for item in profile["bundles"] if canonicalize_name(item["distribution"]) == distribution
                )
                if str(application_requirements[distribution].specifier) != str(SpecifierSet(declared["version"])):
                    errors.append(
                        f"{name}: {distribution} range differs from {source}: "
                        f"{declared['version']} != {application_requirements[distribution].specifier}"
                    )
    return errors


def validate_contract(
    contract: dict[str, Any], repo_root: Path = REPO_ROOT
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    errors: list[str] = []
    if contract.get("schema_version") != 1:
        errors.append("bundle profile schema_version must be 1")
    profiles = contract.get("profiles", {})
    if not profiles:
        errors.append("bundle profile contract must contain profiles")
    image_families = contract.get("image_families", {})
    if not image_families:
        errors.append("bundle profile contract must map every supported downstream image family")
    referenced_profiles: set[str] = set()
    for family, selection in image_families.items():
        profile_name = selection.get("profile")
        if profile_name not in profiles:
            errors.append(f"downstream image family {family!r} selects unknown profile {profile_name!r}")
        else:
            referenced_profiles.add(profile_name)
        if selection.get("install_phase") != "build":
            errors.append(f"downstream image family {family!r} must install bundles at build time")
    if unreferenced := sorted(set(profiles) - referenced_profiles):
        errors.append(f"bundle profiles are not selected by a supported downstream image family: {unreferenced}")

    try:
        catalog = discover_bundle_catalog(repo_root)
    except ProfileError as exc:
        return {}, [str(exc)]
    for name, profile in profiles.items():
        errors.extend(validate_profile(name, profile, catalog, repo_root))
    return catalog, errors


def exact_requirement(distribution: str, extras: list[str], version: str) -> str:
    suffix = f"[{','.join(extras)}]" if extras else ""
    return f"{distribution}{suffix}=={version}"


def compile_profile(
    contract: dict[str, Any],
    profile_name: str,
    catalog: dict[str, dict[str, Any]],
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    profile = contract["profiles"][profile_name]
    root_project = read_project(repo_root / "pyproject.toml")
    lfx_project = read_project(repo_root / "src" / "lfx" / "pyproject.toml")
    bundles = []
    for item in sorted(profile["bundles"], key=lambda value: canonicalize_name(value["distribution"])):
        distribution = canonicalize_name(item["distribution"])
        resolved_version = catalog[distribution]["version"]
        bundles.append(
            {
                "distribution": distribution,
                "extras": item["extras"],
                "providers": item["providers"],
                "requested": item["version"],
                "resolved_version": resolved_version,
                "requirement": exact_requirement(distribution, item["extras"], resolved_version),
            }
        )
    return {
        "schema_version": contract["schema_version"],
        "profile": profile_name,
        "image_families": sorted(
            family for family, selection in contract["image_families"].items() if selection["profile"] == profile_name
        ),
        "profile_digest": profile_digest(profile),
        "indexes": profile["indexes"],
        "python": profile["python"],
        "application": {
            "distribution": canonicalize_name(profile["application"]["distribution"]),
            "requested": profile["application"]["version"],
            "resolved_version": root_project["version"],
            "requirement": exact_requirement(root_project["name"], [], root_project["version"]),
        },
        "bundle_api": {
            "distribution": "lfx",
            "requested": profile["bundle_api"]["version"],
            "resolved_version": lfx_project["version"],
            "requirement": exact_requirement("lfx", [], lfx_project["version"]),
        },
        "bundles": bundles,
        "providers": sorted(provider for item in bundles for provider in item["providers"]),
    }


def compile_all(contract_path: Path, output_dir: Path, repo_root: Path = REPO_ROOT) -> list[Path]:
    contract = read_json(contract_path)
    catalog, errors = validate_contract(contract, repo_root)
    if errors:
        raise ProfileError("\n".join(errors))
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for profile_name in sorted(contract["profiles"]):
        path = output_dir / f"{profile_name}.lock.json"
        path.write_text(canonical_json(compile_profile(contract, profile_name, catalog, repo_root)), encoding="utf-8")
        paths.append(path)
    return paths


def check_locks(contract_path: Path, locks_dir: Path, repo_root: Path = REPO_ROOT) -> list[str]:
    contract = read_json(contract_path)
    catalog, errors = validate_contract(contract, repo_root)
    if errors:
        return errors
    expected_names = {f"{name}.lock.json" for name in contract.get("profiles", {})}
    actual_names = {path.name for path in locks_dir.glob("*.lock.json")} if locks_dir.is_dir() else set()
    for missing in sorted(expected_names - actual_names):
        errors.append(f"missing bundle profile lock {missing}")
    for unexpected in sorted(actual_names - expected_names):
        errors.append(f"unexpected bundle profile lock {unexpected}")
    for profile_name in sorted(contract.get("profiles", {})):
        path = locks_dir / f"{profile_name}.lock.json"
        if path.is_file():
            expected = canonical_json(compile_profile(contract, profile_name, catalog, repo_root))
            if path.read_text(encoding="utf-8") != expected:
                errors.append(f"stale bundle profile lock {path.name}; regenerate it intentionally")
    return errors


def installed_inventory() -> tuple[dict[str, str], dict[str, list[str]]]:
    distributions: dict[str, str] = {}
    provider_owners: dict[str, list[str]] = {}
    for distribution in metadata.distributions():
        raw_name = distribution.metadata.get("Name")
        if not raw_name:
            continue
        name = canonicalize_name(raw_name)
        entry_points = list(distribution.entry_points)
        if not any(point.group in {"langflow.extensions", "lfx.bundles"} for point in entry_points):
            continue
        distributions[name] = distribution.version
        for point in entry_points:
            if point.group == "langflow.extensions":
                provider_owners.setdefault(point.name, []).append(name)

        if name == "lfx-bundles":
            for file_name in distribution.files or []:
                parts = Path(file_name).parts
                if (
                    len(parts) == BUNDLE_INIT_PATH_PARTS
                    and parts[0] == "lfx_bundles"
                    and parts[2] == "__init__.py"
                    and not parts[1].startswith("_")
                ):
                    provider_owners.setdefault(parts[1], []).append(name)
    return dict(sorted(distributions.items())), {key: sorted(value) for key, value in sorted(provider_owners.items())}


def validate_installed(
    lock: dict[str, Any],
    actual_distributions: dict[str, str],
    provider_owners: dict[str, list[str]],
    contract_versions: dict[str, str] | None = None,
) -> list[str]:
    errors: list[str] = []
    if contract_versions is not None:
        for contract_key in ("application", "bundle_api"):
            selection = lock[contract_key]
            distribution = selection["distribution"]
            actual = contract_versions.get(distribution)
            if actual is None:
                errors.append(f"missing {contract_key} distribution {distribution!r}")
            elif actual != selection["resolved_version"]:
                errors.append(f"{distribution} version drift: expected {selection['resolved_version']}, got {actual}")
    expected_distributions = {item["distribution"]: item["resolved_version"] for item in lock["bundles"]}
    missing = sorted(set(expected_distributions) - set(actual_distributions))
    unexpected = sorted(set(actual_distributions) - set(expected_distributions))
    if missing:
        errors.append(f"missing declared bundle distributions: {missing}")
    if unexpected:
        errors.append(f"undeclared transitive bundle distributions installed: {unexpected}")
    for distribution in sorted(set(expected_distributions) & set(actual_distributions)):
        expected = expected_distributions[distribution]
        actual = actual_distributions[distribution]
        if actual != expected:
            errors.append(f"{distribution} version drift: expected {expected}, got {actual}")

    actual_providers = set(provider_owners)
    expected_providers = set(lock["providers"])
    if missing_providers := sorted(expected_providers - actual_providers):
        errors.append(f"missing declared providers: {missing_providers}")
    if unexpected_providers := sorted(actual_providers - expected_providers):
        errors.append(f"undeclared providers installed: {unexpected_providers}")
    duplicates = {provider: owners for provider, owners in provider_owners.items() if len(set(owners)) > 1}
    if duplicates:
        errors.append(f"duplicate providers installed: {duplicates}")
    return errors


def print_errors(errors: list[str]) -> int:
    for error in errors:
        print(f"- {error}", file=sys.stderr)
    return 1 if errors else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles", type=Path, default=DEFAULT_PROFILES)
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check", help="validate profiles and checked-in locks")
    check.add_argument("--locks-dir", type=Path, default=DEFAULT_LOCKS)

    compile_parser = subparsers.add_parser("compile", help="resolve every profile into a deterministic lock")
    compile_parser.add_argument("--output-dir", type=Path, required=True)

    requirements = subparsers.add_parser("requirements", help="render exact build requirements from a lock")
    requirements.add_argument("--lock", type=Path, required=True)
    requirements.add_argument(
        "--bundles-only",
        action="store_true",
        help="omit the application requirement when the downstream build installs Langflow from pinned source",
    )

    verify = subparsers.add_parser("verify-installed", help="verify an installed image against a profile lock")
    verify.add_argument("--lock", type=Path, required=True)
    verify.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "check":
            errors = check_locks(args.profiles, args.locks_dir)
            if errors:
                return print_errors(errors)
            print(f"Bundle profiles and locks passed: {args.profiles}")
        elif args.command == "compile":
            paths = compile_all(args.profiles, args.output_dir)
            for path in paths:
                print(path)
        elif args.command == "requirements":
            lock = read_json(args.lock)
            if not args.bundles_only:
                print(lock["application"]["requirement"])
            for item in lock["bundles"]:
                print(item["requirement"])
        elif args.command == "verify-installed":
            lock = read_json(args.lock)
            distributions, providers = installed_inventory()
            contract_versions = {}
            for contract_key in ("application", "bundle_api"):
                distribution = lock[contract_key]["distribution"]
                with suppress(metadata.PackageNotFoundError):
                    contract_versions[distribution] = metadata.version(distribution)
            errors = validate_installed(lock, distributions, providers, contract_versions)
            report = {
                "schema_version": lock["schema_version"],
                "profile": lock["profile"],
                "profile_digest": lock["profile_digest"],
                "passed": not errors,
                "contract_versions": contract_versions,
                "distributions": distributions,
                "providers": providers,
                "errors": errors,
            }
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(canonical_json(report), encoding="utf-8")
            if errors:
                return print_errors(errors)
            print(f"Installed bundle profile passed; inventory: {args.output}")
    except (KeyError, OSError, ProfileError, ValueError) as exc:
        return print_errors([str(exc)])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
