"""lfx validate -- structural and semantic validation of Langflow flow JSON.

Validation levels (each level implies all levels below it):

    Level 1 - structural
        The file parses as valid JSON and contains the expected top-level keys
        (``id``, ``name``, ``data``, ``data.nodes``, ``data.edges``).
        Also checks for orphaned nodes (no edges at all) and unused nodes
        (not reachable from any output node), and warns about version mismatches
        (nodes built with a different Langflow version than the one installed).

    Level 2 - components
        Every node's ``data.type`` references a component type that exists in
        the lfx component registry.

    Level 3 - edge types
        Connected ports carry compatible types (source output type must be
        assignable to target input type).

    Level 4 - required inputs
        Every required input field on every component has a value or an
        incoming edge connected to it.  Also checks that password/secret fields
        have a value or a matching environment variable set.

Use ``--level`` to select how deep to go, or ``--skip-*`` flags to opt out of
individual checks while still running the others.

Pass ``--strict`` to treat warnings as errors (exit code 1).

This module is a thin wrapper that re-exports symbols from the
``lfx.cli.validation`` subpackage so that all existing imports continue
to work unchanged.
"""

from __future__ import annotations

# Re-export everything from the validation subpackage.
# This keeps ``from lfx.cli.validate import ...`` working for all consumers
# (the CLI entry point in __main__.py, tests, etc.).
from lfx.cli.validation import (  # noqa: F401
    ValidationIssue,
    ValidationResult,
    _check_missing_credentials,
    _check_orphaned_nodes,
    _check_unused_nodes,
    _check_version_mismatch,
    _expand_paths,
    _get_lf_version,
    _node_display_name,
    validate_command,
    validate_flow_file,
)

# Level constants (re-exported for backwards compatibility)
from lfx.cli.validation.core import (  # noqa: F401
    _LEVEL_COMPONENTS,
    _LEVEL_EDGE_TYPES,
    _LEVEL_REQUIRED_INPUTS,
    _LEVEL_STRUCTURAL,
)
