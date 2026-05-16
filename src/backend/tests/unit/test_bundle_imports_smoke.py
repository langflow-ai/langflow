"""Per-bundle import smoke test.

For every installed ``lfx-<bundle>`` distribution registered under the
``langflow.extensions`` entry-point group, this test:

  1. Imports the bundle's ``lfx_<bundle>.components.<bundle>`` package.
  2. Verifies ``__all__`` is defined and non-empty.
  3. Resolves every name in ``__all__`` via attribute access (the lazy
     ``__getattr__`` shim each bundle ships).

This single parametrized test replaces ~79 hand-written per-bundle
smoke tests.  New bundles get coverage automatically by virtue of
registering the entry-point.  If a bundle ships a class with a broken
import or a typo in ``__all__``, this test fails fast and tells the
operator exactly which bundle / name is wrong.

Bundles that legitimately can't be import-smoke-tested (e.g. those
requiring heavy optional dependencies not present in the test image)
should declare the missing module via an ``ImportError`` raised at
top-level import time; this test then ``pytest.skip``s that bundle
rather than failing.
"""

from __future__ import annotations

import importlib
from importlib.metadata import entry_points

import pytest


def _discover_installed_bundles() -> list[tuple[str, str]]:
    """Return ``[(ep_name, package), ...]`` for every installed lfx bundle.

    ``ep_name`` is the entry-point name (``"lfx-openai"``); ``package`` is
    the importable Python package the entry-point points at
    (``"lfx_openai"``).
    """
    discovered: list[tuple[str, str]] = []
    try:
        eps = entry_points(group="langflow.extensions")
    except Exception:
        return discovered
    for ep in eps:
        if not ep.name.startswith("lfx-"):
            continue
        discovered.append((ep.name, ep.value))
    discovered.sort()
    return discovered


_BUNDLES = _discover_installed_bundles()


@pytest.mark.parametrize(
    ("ep_name", "package"),
    _BUNDLES,
    ids=[name for name, _ in _BUNDLES] or ["NO_BUNDLES_INSTALLED"],
)
def test_bundle_components_importable(ep_name: str, package: str) -> None:
    """Every class in ``lfx_<bundle>.components.<bundle>.__all__`` must resolve."""
    # Bundle name is the snake_case portion of the package
    # (``lfx_openai`` -> ``openai``; ``lfx_google_genai`` -> ``google_genai``).
    bundle_name = package.removeprefix("lfx_")
    component_module = f"{package}.components.{bundle_name}"

    try:
        module = importlib.import_module(component_module)
    except ImportError as exc:
        pytest.skip(f"Bundle {ep_name!r}: components package {component_module!r} not importable in this env: {exc}")

    all_attr = getattr(module, "__all__", None)
    assert all_attr is not None, (
        f"Bundle {ep_name!r}: {component_module!r} is missing ``__all__``.  "
        f"Without it the dynamic walk and the bridge fall back to inspecting "
        f"module globals, which is fragile."
    )
    assert len(all_attr) > 0, (
        f"Bundle {ep_name!r}: ``__all__`` is empty.  A bundle with no exported "
        f"components is almost certainly a configuration error."
    )

    failures: list[str] = []
    optional_dep_skips: list[str] = []
    for name in all_attr:
        try:
            obj = getattr(module, name)
        except AttributeError as exc:
            # An AttributeError unwrapping an underlying ModuleNotFoundError
            # is the bundle's lazy ``__getattr__`` re-raising an ImportError
            # for an OPTIONAL dependency (e.g. ``langchain_ibm`` not
            # installed in the test image).  Skip those rather than fail.
            cause = exc.__cause__ or exc.__context__
            if isinstance(cause, ModuleNotFoundError):
                optional_dep_skips.append(f"{name}: optional dep {cause.name!r} not installed")
                continue
            failures.append(f"{name}: {exc}")
            continue
        except ImportError as exc:
            failures.append(f"{name}: {exc}")
            continue
        if obj is None:
            failures.append(f"{name}: resolved to None")
            continue
        if not callable(obj):
            # Non-callable exports are unusual but legal (constants, dicts).
            # Don't fail, but ensure they have a non-empty repr.
            assert repr(obj), f"{name}: empty repr"

    if optional_dep_skips and not failures and len(optional_dep_skips) == len(all_attr):
        # Entire bundle relies on optional deps that aren't installed in
        # this env -- skip rather than report all-skipped-but-passed.
        pytest.skip(
            f"Bundle {ep_name!r}: all {len(all_attr)} exports require optional "
            f"deps not installed:\n  - " + "\n  - ".join(optional_dep_skips)
        )

    assert not failures, (
        f"Bundle {ep_name!r} ({component_module!r}) failed to resolve "
        f"{len(failures)} entries in ``__all__``:\n  - " + "\n  - ".join(failures)
    )


def test_at_least_one_bundle_installed() -> None:
    """Sanity guard: fail loudly when zero bundles are installed.

    If the install set is empty the parametrized test silently passes
    via parametrize-with-empty-list.  This assertion makes that
    misconfiguration visible in the full backend test env (where this
    test file actually runs).
    """
    assert _BUNDLES, (
        "No lfx-<bundle> entry-points found in this environment.  Either "
        "no bundles are installed or the langflow.extensions entry-point "
        "group is not being scanned."
    )
