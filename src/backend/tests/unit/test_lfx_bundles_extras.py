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
    5. metapackage bundle categories stay disjoint from categories declared
       by partner manifests, preventing one distribution from shadowing another,
    6. retired ALTK extras cannot reinstall the removed toolkit dependency.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
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


def _partner_bundle_names(bundles_dir: Path) -> set[str]:
    """Read registry categories from shipped manifests rather than workspace labels."""
    names = set()
    for child in sorted(bundles_dir.iterdir()):
        project_path = child / "pyproject.toml"
        if not child.is_dir() or child.name == "lfx-bundles" or not project_path.is_file():
            continue
        with project_path.open("rb") as file:
            project = tomllib.load(file)
        manifests = [
            json.loads(path.read_text(encoding="utf-8")) for path in sorted(child.glob("src/*/extension.json"))
        ]
        embedded = project.get("tool", {}).get("langflow", {}).get("extension")
        if embedded is not None:
            manifests.append(embedded)
        assert manifests, f"partner distribution {child.name} has no extension manifest"
        for manifest in manifests:
            names.update(bundle["name"] for bundle in manifest.get("bundles", []))
    return names


def test_metapackage_providers_disjoint_from_graduated_partners() -> None:
    """A registry category must ship from exactly one distribution.

    Distribution and workspace names can differ from declared bundle names.
    The loader shadows only identical categories in the official slot.
    """
    overlap = set(_provider_dirs()) & _partner_bundle_names(BUNDLES_DIR)
    assert not overlap, f"bundle categories shipped from both lfx-bundles and a partner package: {sorted(overlap)}"


def test_confluence_integration_category_preserves_the_legacy_provider() -> None:
    manifest_path = BUNDLES_DIR / "confluence" / "src" / "lfx_confluence" / "extension.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert {bundle["name"] for bundle in manifest["bundles"]} == {"confluence_integrations"}
    assert manifest["integrations"][0]["provider_id"] == "confluence"
    assert manifest["integrations"][0]["bundle"] == "confluence_integrations"
    assert "confluence" in _provider_dirs()
    assert "confluence" not in _partner_bundle_names(BUNDLES_DIR)


@pytest.mark.parametrize("manifest_kind", ["json", "toml"])
def test_manifest_category_detects_double_shipping_despite_a_different_workspace_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, manifest_kind: str
) -> None:
    partner = tmp_path / "renamed-distribution"
    package = partner / "src" / "lfx_renamed"
    package.mkdir(parents=True)
    project = '[project]\nname = "lfx-renamed"\nversion = "0.1.0"\n'
    if manifest_kind == "json":
        manifest = {
            "id": "lfx-renamed",
            "version": "0.1.0",
            "lfx": {"compat": ["1"]},
            "bundles": [{"name": "confluence", "path": "components/confluence"}],
        }
        (package / "extension.json").write_text(json.dumps(manifest), encoding="utf-8")
    else:
        project += (
            '\n[tool.langflow.extension]\nid = "lfx-renamed"\nversion = "0.1.0"\n'
            '[tool.langflow.extension.lfx]\ncompat = ["1"]\n'
            '[[tool.langflow.extension.bundles]]\nname = "confluence"\npath = "components/confluence"\n'
        )
    (partner / "pyproject.toml").write_text(project, encoding="utf-8")
    monkeypatch.setitem(globals(), "BUNDLES_DIR", tmp_path)
    with pytest.raises(AssertionError, match=r"both.*confluence"):
        test_metapackage_providers_disjoint_from_graduated_partners()


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
