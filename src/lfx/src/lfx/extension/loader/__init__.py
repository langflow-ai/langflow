"""Single-Bundle loader for the Langflow Extension System.

This package turns a directory tree on disk (an Extension or a loose
LANGFLOW_COMPONENTS_PATH entry) into a list of :class:`LoadedComponent`
records keyed by the namespaced ID ``ext:<bundle>:<Class>@<slot>``.

Two entry points exist:

    1. :func:`load_extension` -- given a directory containing a v0 manifest
       (extension.json or [tool.langflow.extension] in pyproject.toml), walk
       the bundle directory it declares, import each module, collect every
       :class:`Component` subclass, and register them at the ``official``
       slot.  Multi-bundle manifests are rejected here a second time (the
       schema rejects them too; the loader re-checks at runtime).

    2. :func:`discover_inline_bundles` -- given a list of LANGFLOW_COMPONENTS_PATH
       directories, treat each immediate subfolder as a Bundle at the
       ``extra`` slot.  Walk order is platform-independent: paths are
       iterated in user-declared order, subfolders within a path are sorted
       lexicographically.  Duplicate-name detection emits
       ``duplicate-inline-bundle`` warnings.

The loader's contract with the rest of the system is:

    - Bundle code is *trusted* (it was installed by pip or placed on the
      filesystem by the operator); we DO import it in-process.  This is the
      load-time analogue of validate's --execute-imports flag.  Sandboxing
      is out of scope for v0; the Extension System threat model is "the
      operator chose to install this".
    - Module discovery is recursive and deterministic.  Files are scanned
      in sorted order so the resulting registry order does not depend on
      the underlying filesystem.
    - Failures are typed.  Every error path produces an
      :class:`~lfx.extension.errors.ExtensionError`; nothing raises across
      the loader's public boundary except programmer errors (``TypeError``
      on a non-Path argument, etc.).

Internal layout (all underscore-prefixed; not part of the public surface):

    - ``_types``       -- ``LoadedComponent``, ``LoadResult``, slot constants.
    - ``_discovery``   -- filesystem walk + ``importlib.util`` orchestration.
    - ``_detection``   -- Component subclass identification (MRO heuristic).
    - ``_orchestrator``-- ``load_extension`` / ``discover_inline_bundles``;
                          path-safety, multi-bundle re-check, identity tuple.
    - ``_plugins``     -- manifest-first precedence over ``langflow.plugins``;
                          installed-distribution discovery primitives.

A future installed-package / seed-dir discovery flow will reuse
``_plugins.installed_extension_roots`` for the read-only @official slot at
server startup, and atomic-swap reload will reuse ``_orchestrator`` plus the
discovery layer.  Splitting the loader into small files now keeps each
follow-on touching one banner-section at a time.
"""

from lfx.extension.loader._discovery import DEFAULT_MODULE_NAMESPACE
from lfx.extension.loader._orchestrator import (
    discover_inline_bundles,
    load_extension,
    load_inline_bundle,
)
from lfx.extension.loader._plugins import (
    filter_component_entry_points,
    filter_plugin_entry_points,
    installed_extension_roots,
    manifest_owning_distributions,
)
from lfx.extension.loader._startup import (
    load_installed_extensions,
    load_seed_extensions,
)
from lfx.extension.loader._types import (
    SLOT_EXTRA,
    SLOT_OFFICIAL,
    SLOT_VALUES,
    LoadedComponent,
    LoadResult,
)

__all__ = [
    "DEFAULT_MODULE_NAMESPACE",
    "SLOT_EXTRA",
    "SLOT_OFFICIAL",
    "SLOT_VALUES",
    "LoadResult",
    "LoadedComponent",
    "discover_inline_bundles",
    "filter_component_entry_points",
    "filter_plugin_entry_points",
    "installed_extension_roots",
    "load_extension",
    "load_inline_bundle",
    "load_installed_extensions",
    "load_seed_extensions",
    "manifest_owning_distributions",
]
