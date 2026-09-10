"""Guard the cryptography security floor across uv and published extras."""

from __future__ import annotations

import sys
from pathlib import Path

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.version import Version

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

REPO_ROOT = Path(__file__).resolve().parents[4]
CRYPTOGRAPHY_FLOOR = Version("50.0.0")
LANGCHAIN_LITELLM_COMPAT_VERSION = Version("0.5.1")

PACKAGE_MANIFESTS = {
    "lfx": REPO_ROOT / "src" / "lfx" / "pyproject.toml",
    "langflow-base": REPO_ROOT / "src" / "backend" / "base" / "pyproject.toml",
}
COMPAT_EXTRAS = {
    REPO_ROOT / "src" / "lfx" / "pyproject.toml": {"opendsstar": "opendsstar"},
    REPO_ROOT / "src" / "backend" / "base" / "pyproject.toml": {
        "opendsstar": "opendsstar",
        "cuga": "cuga",
    },
    REPO_ROOT / "src" / "bundles" / "lfx-bundles" / "pyproject.toml": {
        "codeagents": "opendsstar",
        "cuga": "cuga",
    },
}


def _load_toml(path: Path) -> dict:
    with path.open("rb") as file:
        return tomllib.load(file)


def _requirements(specs: list[str], package_name: str) -> list[Requirement]:
    return [requirement for spec in specs if (requirement := Requirement(spec)).name.lower() == package_name]


def _is_exact_version(requirement: Requirement, version: Version) -> bool:
    return str(requirement.specifier) == f"=={version}"


def _requires_at_least(requirement: Requirement, version: Version) -> bool:
    return requirement.marker is None and any(
        specifier.operator == ">=" and Version(specifier.version) >= version for specifier in requirement.specifier
    )


def _is_active(requirement: Requirement, environment: dict[str, str]) -> bool:
    return requirement.marker is None or requirement.marker.evaluate(environment)


def test_published_core_packages_require_patched_cryptography() -> None:
    """Both independently installable core wheels must carry the fixed floor."""
    for package_name, manifest_path in PACKAGE_MANIFESTS.items():
        dependencies = _load_toml(manifest_path)["project"]["dependencies"]
        cryptography = _requirements(dependencies, "cryptography")

        assert len(cryptography) == 1, f"Expected one cryptography dependency in {package_name}"
        assert _requires_at_least(cryptography[0], CRYPTOGRAPHY_FLOOR)


def test_uv_overrides_enforce_the_security_floor_and_compatibility_valve() -> None:
    """Universal uv resolution must not retain a vulnerable or incompatible fork."""
    overrides = _load_toml(REPO_ROOT / "pyproject.toml")["tool"]["uv"]["override-dependencies"]

    cryptography = _requirements(overrides, "cryptography")
    assert len(cryptography) == 1
    assert _requires_at_least(cryptography[0], CRYPTOGRAPHY_FLOOR)

    langchain_litellm = _requirements(overrides, "langchain-litellm")
    assert len(langchain_litellm) == 1
    assert _is_exact_version(langchain_litellm[0], LANGCHAIN_LITELLM_COMPAT_VERSION)


def test_floor_guard_rejects_excluding_only_one_vulnerable_version() -> None:
    vulnerable_requirement = Requirement("cryptography>=48.0.1,!=49.0.0")
    assert not _requires_at_least(vulnerable_requirement, CRYPTOGRAPHY_FLOOR)


def test_pip_facing_extras_pin_the_highest_cryptography_50_compatible_release() -> None:
    """CUGA/OpenDsStar wheel metadata must expose the uv compatibility choice to pip."""
    environments = []
    for python_version in ("3.10", "3.11", "3.12", "3.13", "3.14"):
        for sys_platform, platform_machine in (
            ("linux", "x86_64"),
            ("win32", "AMD64"),
            ("darwin", "arm64"),
            ("darwin", "x86_64"),
        ):
            environment = default_environment()
            environment.update(
                {
                    "python_full_version": f"{python_version}.0",
                    "python_version": python_version,
                    "sys_platform": sys_platform,
                    "platform_machine": platform_machine,
                }
            )
            environments.append(environment)

    for manifest_path, extras in COMPAT_EXTRAS.items():
        optional_dependencies = _load_toml(manifest_path)["project"]["optional-dependencies"]
        for extra_name, upstream_name in extras.items():
            extra = optional_dependencies[extra_name]
            upstream_requirements = _requirements(extra, upstream_name)
            compat_requirements = _requirements(extra, "langchain-litellm")

            assert upstream_requirements, f"Missing {upstream_name} dependency in {manifest_path}:{extra_name}"
            assert compat_requirements, f"Missing langchain-litellm pin in {manifest_path}:{extra_name}"
            assert all(
                _is_exact_version(requirement, LANGCHAIN_LITELLM_COMPAT_VERSION) for requirement in compat_requirements
            )
            for environment in environments:
                assert any(_is_active(requirement, environment) for requirement in upstream_requirements) == any(
                    _is_active(requirement, environment) for requirement in compat_requirements
                )


def test_lock_contains_only_patched_cryptography_and_explicit_compat_release() -> None:
    packages = _load_toml(REPO_ROOT / "uv.lock")["package"]
    cryptography_versions = {Version(package["version"]) for package in packages if package["name"] == "cryptography"}
    langchain_litellm_versions = {
        Version(package["version"]) for package in packages if package["name"] == "langchain-litellm"
    }

    assert cryptography_versions
    assert min(cryptography_versions) >= CRYPTOGRAPHY_FLOOR
    assert langchain_litellm_versions == {LANGCHAIN_LITELLM_COMPAT_VERSION}
