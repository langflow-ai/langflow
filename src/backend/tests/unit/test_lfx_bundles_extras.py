"""Extras-drift guard for the ``lfx-bundles`` metapackage.

``src/bundles/lfx-bundles/pyproject.toml`` carries one optional-dependency
extra per provider plus the *generated* ``all`` and ``all-no-torch`` aggregates
(``langflow`` depends on the metapackage via ``lfx-bundles[all]``). These
invariants are maintained by ``scripts/migrate/consolidate_bundles.py`` and must
never drift by hand-edit:

    1. every provider directory has exactly one extra (PEP 685-normalized key),
    2. ``all`` is exactly the set of per-provider self-refs -- a provider
       missing from ``all`` silently drops its deps from ``pip install
       langflow`` (the epic's headline dep-parity risk),
    3. ``all-no-torch`` is exactly ``all`` minus the torch-pulling providers
       (``TORCH_EXTRAS``), giving a torch-free full-provider install,
    4. normalized extra keys are collision-free,
    5. the metapackage provider set stays disjoint from the graduated
       partner distributions (no double-ship; manifest would shadow).
"""

from __future__ import annotations

import re
from pathlib import Path

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
    extra_keys = set(extras) - AGGREGATE_EXTRAS
    provider_keys = {_normalize(p) for p in _provider_dirs()}
    assert extra_keys == provider_keys, (
        f"extras and provider dirs drifted: extras-only={sorted(extra_keys - provider_keys)}, "
        f"providers-only={sorted(provider_keys - extra_keys)}"
    )


def test_all_extra_is_exactly_the_per_provider_self_refs() -> None:
    extras = _load_extras()
    expected = {f"lfx-bundles[{key}]" for key in extras if key not in AGGREGATE_EXTRAS}
    actual = set(extras["all"])
    assert actual == expected, (
        f"generated `all` drifted: missing={sorted(expected - actual)}, stray={sorted(actual - expected)}"
    )


def test_all_no_torch_extra_is_all_minus_torch_providers() -> None:
    extras = _load_extras()
    expected = {f"lfx-bundles[{key}]" for key in extras if key not in AGGREGATE_EXTRAS and key not in TORCH_EXTRAS}
    actual = set(extras["all-no-torch"])
    assert actual == expected, (
        f"generated `all-no-torch` drifted: missing={sorted(expected - actual)}, stray={sorted(actual - expected)}"
    )


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
