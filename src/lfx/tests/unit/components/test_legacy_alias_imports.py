"""Regression tests for the legacy component alias modules.

``lfx.components.helpers`` and ``lfx.components.logic`` are backwards-compatibility
shims: the components they advertise now live in ``utilities``, ``flow_controls`` and
``llm_operations``.  Forwarding used to be written as ``from lfx.components import
utilities``, which looks harmless but is not -- none of those three target modules is
registered in ``lfx.components._dynamic_imports``, so the ``from ... import`` form falls
through to ``lfx.components.__getattr__``, which brute-force imports *every* registered
bundle module hunting for a name it can never find.

That turned a two-module forward into an eager import of the entire integration tail
during app startup (``langflow.api.v1.knowledge_bases`` reaches here via
``memory_base.preprocessing`` -> ``models_and_agents.agent``).  Any third-party package
with an import-time side effect then owns process startup -- see #14227, where mem0's
``os.makedirs($HOME/.mem0)`` aborted boot on a read-only Kubernetes filesystem.

Locked here:
  1. The aliases still resolve to the same classes (no behavioural change).
  2. Resolving them does not trigger the package-wide discovery scan.
  3. Discovery itself swallows *any* import failure, not just ``ImportError``.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

# Bundle modules that a legacy alias lookup has no business importing. These sit early in
# the discovery table, so a reintroduced brute-force scan pulls them in first.
CANARY_BUNDLES = (
    "lfx.components.mem0",
    "lfx.components.openai",
    "lfx.components.anthropic",
    "lfx.components.chroma",
)


def _run_probe(script: str) -> dict:
    """Execute ``script`` in a clean interpreter and return its JSON stdout.

    A subprocess is required: discovery state (``_discovered_modules``,
    ``_dynamic_imports``, ``sys.modules``) is process-global, so any earlier test that
    touched ``lfx.components`` would mask a regression here.
    """
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


class TestLegacyAliasesResolve:
    """The forwards must keep pointing at the modules the components actually live in."""

    def test_helpers_forwards_to_utilities(self):
        from lfx.components.helpers import CalculatorComponent, CurrentDateComponent, IDGeneratorComponent

        assert CalculatorComponent.__module__ == "lfx.components.utilities.calculator_core"
        assert CurrentDateComponent.__module__ == "lfx.components.utilities.current_date"
        assert IDGeneratorComponent.__module__ == "lfx.components.utilities.id_generator"

    def test_logic_forwards_to_flow_controls(self):
        from lfx.components.logic import ConditionalRouterComponent, LoopComponent

        assert ConditionalRouterComponent.__module__ == "lfx.components.flow_controls.conditional_router"
        assert LoopComponent.__module__ == "lfx.components.flow_controls.loop"

    def test_logic_forwards_smart_router_to_llm_operations(self):
        from lfx.components.logic import SmartRouterComponent

        assert SmartRouterComponent.__module__.startswith("lfx.components.llm_operations.")


class TestLegacyAliasesDoNotScanBundles:
    """Resolving a legacy alias must not drag in the integration tail."""

    @pytest.mark.parametrize(
        ("module", "attr"),
        [
            ("lfx.components.helpers", "CalculatorComponent"),
            ("lfx.components.helpers", "CurrentDateComponent"),
            ("lfx.components.logic", "ConditionalRouterComponent"),
            ("lfx.components.logic", "SmartRouterComponent"),
        ],
    )
    def test_alias_lookup_skips_package_wide_discovery(self, module: str, attr: str):
        probe = _run_probe(
            "import importlib, json, sys\n"
            "import lfx.components as pkg\n"
            f"getattr(importlib.import_module({module!r}), {attr!r})\n"
            "print(json.dumps({\n"
            '    "discovered": sorted(pkg._discovered_modules),\n'
            '    "submodules": sorted(\n'
            '        m for m in sys.modules if m.startswith("lfx.components.") and m.count(".") == 2\n'
            "    ),\n"
            "}))\n"
        )

        # An empty discovery set is the real assertion: a single entry means __getattr__
        # started walking the table.
        assert probe["discovered"] == [], (
            f"resolving {module}.{attr} triggered package-wide discovery of "
            f"{len(probe['discovered'])} module(s): {probe['discovered'][:10]}"
        )
        leaked = sorted(set(CANARY_BUNDLES) & set(probe["submodules"]))
        assert not leaked, f"resolving {module}.{attr} imported unrelated bundles: {leaked}"


class TestDiscoveryIsBestEffort:
    """A misbehaving integration must not be able to abort the caller's import."""

    @pytest.mark.parametrize("error", [OSError(30, "Read-only file system"), RuntimeError("boom"), ValueError("bad")])
    def test_non_import_errors_are_swallowed(self, monkeypatch: pytest.MonkeyPatch, error: Exception):
        import lfx.components as pkg

        module_name = "_synthetic_failing_module"

        def explode(*_args, **_kwargs):
            raise error

        monkeypatch.setattr(pkg, "import_mod", explode)
        monkeypatch.setattr(pkg, "_discovered_modules", set(pkg._discovered_modules))

        pkg._discover_components_from_module(module_name)

        # Marked discovered so the failure is not retried on every subsequent lookup.
        assert module_name in pkg._discovered_modules
