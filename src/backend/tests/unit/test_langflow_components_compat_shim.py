"""Tests for the dynamic ``langflow.components.*`` -> ``lfx.components.*`` bridge.

Saved flows in the wild import their components via the legacy
``langflow.components.<sub>.<leaf>`` paths (the integration test
``test_dynamic_import_integration.py`` documents this contract).  The
lfx extraction moved every component module into ``lfx.components.*``;
``langflow/__init__.py`` installs a meta path finder that bridges the
two namespaces dynamically so saved flows keep loading without
modification.

This suite locks the contract:

    1. Generic prefix bridge: ``langflow.components.<rest>`` resolves to
       ``lfx.components.<rest>`` for arbitrary subpackages and submodules,
       including new bundles extracted in the future.
    2. Renamed-package override: ``langflow.components.knowledge_bases``
       (and any submodule under it) resolves to
       ``lfx.components.files_and_knowledge`` because the package was
       renamed during the move while the langflow-side path stays for
       saved-flow compat.
    3. Class identity is preserved: a class loaded via the langflow path
       is the same object as the one loaded via the lfx path, so
       ``isinstance`` checks across the bridge keep working.
"""

from __future__ import annotations

import importlib
import sys

import langflow  # noqa: F401  -- triggers the meta finder install


def test_dotted_submodule_import_resolves() -> None:
    """``from langflow.components.processing.converter import X`` works.

    Regression: the deletion of the physical ``langflow/components/processing/converter.py``
    shim broke this import path before the dynamic bridge landed.
    """
    from langflow.components.processing.converter import convert_to_dataframe

    # The bridge is a name alias, not a copy; ``__module__`` reflects the
    # underlying lfx location so debuggers / stack traces point at the
    # canonical source file.
    assert convert_to_dataframe.__module__ == "lfx.components.processing.converter"


def test_helpers_subpackage_imports() -> None:
    """``from langflow.components.helpers import X`` works for any helper class."""
    from langflow.components.helpers import CalculatorComponent

    assert CalculatorComponent.__module__.startswith("lfx.components.")


def test_knowledge_bases_override_resolves_to_files_and_knowledge() -> None:
    """``langflow.components.knowledge_bases[.<rest>]`` -> ``lfx.components.files_and_knowledge[.<rest>]``.

    The lfx package was renamed during the move; the langflow-side path
    stays as ``knowledge_bases`` so saved flows that imported via that
    name continue to resolve.
    """
    from langflow.components.knowledge_bases.retrieval import KnowledgeBaseComponent

    assert KnowledgeBaseComponent.__module__ == "lfx.components.files_and_knowledge.retrieval"


def test_class_identity_preserved_across_bridge() -> None:
    """Same class is returned via ``langflow.components.X`` and ``lfx.components.X``.

    Critical for ``isinstance`` checks against types resolved through
    either path -- e.g. a saved flow imports the legacy langflow path
    while runtime code imports the lfx path; both must compare equal.
    """
    import langflow.components.processing.converter as langflow_module
    import lfx.components.processing.converter as lfx_module

    assert langflow_module is lfx_module
    assert langflow_module.convert_to_dataframe is lfx_module.convert_to_dataframe


def test_top_level_components_is_aliased_to_lfx_components() -> None:
    """``import langflow.components`` resolves to the lfx package.

    Catches the case where the meta finder isn't installed yet when
    ``langflow.components`` is first imported -- happens on cold imports
    in test runs that don't go through ``langflow.__init__`` first.
    """
    import langflow.components
    import lfx.components

    assert langflow.components is lfx.components


def test_arbitrary_extracted_bundle_resolves_via_dynamic_bridge() -> None:
    """A bundle that exists in lfx but had no physical ``langflow/components`` shim resolves.

    Regression-future: the previous shim layout required a parallel
    physical file per subpackage; forgetting to add one silently broke
    pre-existing flows.  The dynamic bridge means a new lfx component
    module is reachable via the legacy langflow path immediately.
    """
    # Pick any subpackage under lfx.components that didn't have a
    # physical shim under langflow/components/ before the deletion.
    target = "lfx.components.helpers.calculator_core"
    importlib.import_module(target)
    bridge = importlib.import_module("langflow.components.helpers.calculator_core")
    assert bridge is sys.modules[target]
