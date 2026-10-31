"""Extras-drift guard for the ``lfx-bundles`` metapackage.

``src/bundles/lfx-bundles/pyproject.toml`` carries one optional-dependency
extra per provider plus the *generated* ``all`` and ``all-no-torch`` aggregates
for explicit opt-in installs such as ``lfx[bundles]``. These invariants are
maintained by ``scripts/migrate/consolidate_bundles.py`` and must never drift
by hand-edit:

    1. every provider directory has exactly one extra (PEP 685-normalized key),
       apart from explicit compatibility aliases for graduated providers,
    2. ``all`` is exactly the set of per-provider self-refs -- a provider
       missing from ``all`` silently drops its deps from explicit all-bundle
       installs,
    3. ``all-no-torch`` is exactly ``all`` minus the torch-pulling providers
       (``TORCH_EXTRAS``), giving a torch-free full-provider install,
    4. normalized extra keys are collision-free,
    5. the metapackage provider set stays disjoint from the graduated
       partner distributions (no double-ship; manifest would shadow),
    6. retired ALTK extras cannot reinstall the removed toolkit dependency.
"""

from __future__ import annotations

import re
from pathlib import Path

from packaging.requirements import Requirement

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10: tomllib is stdlib only on 3.11+
    import tomli as tomllib  # pytest guarantees tomli on <3.11

REPO_ROOT = Path(__file__).resolve().parents[4]
METAPACKAGE_DIR = REPO_ROOT / "src" / "bundles" / "lfx-bundles"
PROVIDERS_DIR = METAPACKAGE_DIR / "src" / "lfx_bundles"
BUNDLES_DIR = REPO_ROOT / "src" / "bundles"

# Generated aggregate extras (not per-provider) -- kept in sync with
# scripts/migrate/consolidate_bundles.py. ``all`` pulls every provider;
# ``all-no-torch`` is ``all`` minus the torch-pulling providers (TORCH_EXTRAS).
AGGREGATE_EXTRAS = frozenset({"all", "all-no-torch"})
RETIRED_EXTRAS = frozenset({"chroma"})
COMPATIBILITY_EXTRAS = {
    "azure": ["lfx-azure>=0.1.0,<1.0.0"],
    "google": ["lfx-google>=0.2.5,<1.0.0"],
    "ollama": ["lfx-ollama>=0.1.0,<1.0.0"],
}
TORCH_EXTRAS = frozenset({"cuga", "codeagents"})


def _normalize(name: str) -> str:
    """PEP 685 extra-name normalization (matches consolidate_bundles.py)."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _load_extras() -> dict[str, list[str]]:
    with (METAPACKAGE_DIR / "pyproject.toml").open("rb") as fh:
        return tomllib.load(fh)["project"]["optional-dependencies"]


def _provider_dirs() -> list[str]:
    return sorted(
        child.name for child in PROVIDERS_DIR.iterdir() if child.is_dir() and (child / "__init__.py").is_file()
    )


def test_every_provider_has_an_extra_and_vice_versa() -> None:
    extras = _load_extras()
    extra_keys = set(extras) - AGGREGATE_EXTRAS - COMPATIBILITY_EXTRAS.keys()
    provider_keys = {_normalize(p) for p in _provider_dirs()}
    assert extra_keys == provider_keys, (
        f"extras and provider dirs drifted: extras-only={sorted(extra_keys - provider_keys)}, "
        f"providers-only={sorted(provider_keys - extra_keys)}"
    )


def test_all_extra_is_exactly_the_per_provider_self_refs() -> None:
    extras = _load_extras()
    expected = {
        f"lfx-bundles[{key}]"
        for key in extras
        if key not in AGGREGATE_EXTRAS and key not in COMPATIBILITY_EXTRAS and key not in RETIRED_EXTRAS
    }
    actual = set(extras["all"])
    assert actual == expected, (
        f"generated `all` drifted: missing={sorted(expected - actual)}, stray={sorted(actual - expected)}"
    )


def test_all_no_torch_extra_is_all_minus_torch_providers() -> None:
    extras = _load_extras()
    expected = {
        f"lfx-bundles[{key}]"
        for key in extras
        if key not in AGGREGATE_EXTRAS
        and key not in TORCH_EXTRAS
        and key not in COMPATIBILITY_EXTRAS
        and key not in RETIRED_EXTRAS
    }
    actual = set(extras["all-no-torch"])
    assert actual == expected, (
        f"generated `all-no-torch` drifted: missing={sorted(expected - actual)}, stray={sorted(actual - expected)}"
    )


def test_graduated_compatibility_extras_are_explicit_and_not_aggregated() -> None:
    extras = _load_extras()
    assert {key: extras[key] for key in COMPATIBILITY_EXTRAS} == COMPATIBILITY_EXTRAS
    aggregate_requirements = {*extras["all"], *extras["all-no-torch"]}
    assert not {f"lfx-bundles[{key}]" for key in COMPATIBILITY_EXTRAS} & aggregate_requirements


def test_normalized_extra_keys_are_collision_free() -> None:
    providers = _provider_dirs()
    normalized = [_normalize(p) for p in providers]
    dupes = {key for key in normalized if normalized.count(key) > 1}
    assert not dupes, f"provider names collide after PEP 685 normalization: {sorted(dupes)}"


def test_metapackage_providers_disjoint_from_graduated_partners() -> None:
    """A provider must ship from exactly one distribution.

    Graduated ``lfx-<provider>`` packages are the manifest-shipping
    ``src/bundles/<provider>/`` workspace members (manifest shadows
    manifest-less, but double-shipping is still a packaging bug).
    """
    partners = {
        child.name
        for child in BUNDLES_DIR.iterdir()
        if child.is_dir() and child.name != "lfx-bundles" and (child / "pyproject.toml").is_file()
    }
    overlap = {_normalize(p) for p in _provider_dirs()} & {_normalize(p) for p in partners}
    assert not overlap, f"providers shipped from both lfx-bundles and a graduated package: {sorted(overlap)}"


def test_retired_altk_extra_cannot_reinstall_toolkit() -> None:
    assert _load_extras()["altk"] == []
    with (REPO_ROOT / "src" / "backend" / "base" / "pyproject.toml").open("rb") as file:
        project = tomllib.load(file)["project"]
    assert project["optional-dependencies"]["altk"] == []
    manifests = [_load_extras(), project["optional-dependencies"]]
    for extras in manifests:
        for dependencies in extras.values():
            assert not any(Requirement(dependency).name == "agent-lifecycle-toolkit" for dependency in dependencies)


def test_huggingface_dependency_does_not_request_removed_inference_extra() -> None:
    requirements = (Requirement(dependency) for dependency in _load_extras()["huggingface"])
    huggingface_hub = next(requirement for requirement in requirements if requirement.name == "huggingface-hub")

    assert not huggingface_hub.extras
