"""Guard: the generated ``lfx-bundles[all-no-torch]`` aggregate stays torch-free.

``all-no-torch`` is ``all`` minus the torch-pulling providers (``cuga``,
``codeagents``); it backs slim / CPU-only images that must never pull torch.
Torch arrives *transitively* (``cuga`` -> torch, ``codeagents`` -> smolagents ->
torch), so a newly added provider can silently violate the rule without ever
naming torch in its extra. Two layers of defense:

* ``test_all_no_torch_structure`` (offline, fast): the aggregate is exactly
  ``all`` minus the known torch providers and references only real extras.
  Catches generator drift / hand-edits, and trips if the torch-provider set
  changes -- forcing a conscious update here and in the generator.
* ``test_all_no_torch_resolves_without_torch`` (resolves deps): the real guard.
  Resolves the aggregate and asserts no torch-family distribution appears,
  catching a new provider that pulls torch transitively. Skips (never fails red)
  when the resolver / network is unavailable.

Keep ``TORCH_PROVIDERS`` in sync with ``TORCH_EXTRAS`` in
``scripts/migrate/consolidate_bundles.py`` -- they encode the same rule.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - py3.10 fallback
    tomllib = pytest.importorskip("tomli")

_PKG_DIR = Path(__file__).resolve().parent.parent
_PYPROJECT = _PKG_DIR / "pyproject.toml"

# Providers whose SDKs pull torch (transitively). Mirror of
# scripts/migrate/consolidate_bundles.py:TORCH_EXTRAS. Changing this set is a
# deliberate act: update it in BOTH places, together.
TORCH_PROVIDERS = {"cuga", "codeagents"}

# A resolved distribution is "torch-family" if its canonical name matches one of
# these or starts with a prefix below (the torch / CUDA GPU stack). torch,
# sentence-transformers, triton and nvidia-cu* only appear when torch is pulled.
_TORCH_NAMES = {"torch", "torchvision", "torchaudio", "triton", "sentence-transformers"}
_TORCH_PREFIXES = ("nvidia-cu",)


def _extras() -> dict[str, list[str]]:
    data = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    return data["project"]["optional-dependencies"]


def _provider_keys(aggregate: list[str]) -> set[str]:
    # entries look like "lfx-bundles[<key>]"
    return {entry.split("[", 1)[1].rstrip("]") for entry in aggregate}


def _canonical(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def _is_torch_family(name: str) -> bool:
    canonical = _canonical(name)
    return canonical in _TORCH_NAMES or any(canonical.startswith(p) for p in _TORCH_PREFIXES)


def test_all_no_torch_structure() -> None:
    """all-no-torch == all minus the known torch providers, referencing real extras only."""
    extras = _extras()
    assert "all-no-torch" in extras, "lfx-bundles is missing the 'all-no-torch' aggregate"

    all_keys = _provider_keys(extras["all"])
    no_torch_keys = _provider_keys(extras["all-no-torch"])

    assert no_torch_keys <= all_keys, f"all-no-torch references non-'all' keys: {sorted(no_torch_keys - all_keys)}"

    excluded = all_keys - no_torch_keys
    assert excluded == TORCH_PROVIDERS, (
        f"all-no-torch must be 'all' minus {sorted(TORCH_PROVIDERS)}; it actually excludes {sorted(excluded)}. "
        "If the torch-provider set changed, update TORCH_PROVIDERS here AND TORCH_EXTRAS in "
        "scripts/migrate/consolidate_bundles.py, then regenerate the pyproject."
    )

    defined = set(extras) - {"all", "all-no-torch"}
    assert no_torch_keys <= defined, f"all-no-torch references undefined extras: {sorted(no_torch_keys - defined)}"


def test_all_no_torch_resolves_without_torch() -> None:
    """Resolving lfx-bundles[all-no-torch] must not pull any torch-family distribution."""
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv not on PATH; cannot resolve all-no-torch")

    requirement = f"lfx-bundles[all-no-torch] @ file://{_PKG_DIR}"
    # Trusted invocation: uv path from shutil.which, all args static. S603 is a false positive.
    proc = subprocess.run(  # noqa: S603
        [
            uv,
            "pip",
            "compile",
            "--prerelease=allow",
            "--python-platform",
            "linux",
            "--python-version",
            "3.12",
            "-",
        ],
        input=requirement,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    if proc.returncode != 0:
        pytest.skip(f"could not resolve all-no-torch (offline / registry unavailable?):\n{proc.stderr[-800:]}")

    offenders = sorted(
        {
            line.split("==", 1)[0].strip()
            for line in proc.stdout.splitlines()
            if "==" in line and not line.lstrip().startswith("#") and _is_torch_family(line.split("==", 1)[0])
        }
    )
    assert not offenders, (
        f"lfx-bundles[all-no-torch] resolved torch-family packages: {offenders}. "
        "A provider in 'all' pulls torch transitively -- add it to TORCH_EXTRAS in "
        "scripts/migrate/consolidate_bundles.py (and TORCH_PROVIDERS in this test), then regenerate."
    )
