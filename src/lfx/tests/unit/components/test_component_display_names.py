"""Tests that ALL component outputs and inputs use the new display names.

Validates the Data->JSON and DataFrame->Table rename migration is complete
across the entire component library. No component should still use the old
display names "Data", "DataFrame", or "Data or DataFrame".
"""

from __future__ import annotations

import importlib
import inspect
import os
from pathlib import Path

import lfx.components

# --- Named constants ---

DEPRECATED_OUTPUT_DISPLAY_NAME_DATA = "Data"
DEPRECATED_OUTPUT_DISPLAY_NAME_DATAFRAME = "DataFrame"
DEPRECATED_DISPLAY_NAME_DATA_OR_DATAFRAME = "Data or DataFrame"

EXPECTED_DATA_REPLACEMENT = "JSON"
EXPECTED_DATAFRAME_REPLACEMENT = "Table"

MINIMUM_EXPECTED_COMPONENTS = 20


def _discover_all_component_classes() -> list[tuple[str, type]]:
    """Discover all component classes from the lfx.components package.

    Finds all .py files under lfx/components, imports them, and collects
    all classes that inherit from Component.

    Returns:
        List of (fully_qualified_name, class) tuples.
    """
    from lfx.custom.custom_component.component import Component

    discovered: list[tuple[str, type]] = []
    components_pkg_path = Path(lfx.components.__path__[0])
    components_pkg_name = lfx.components.__name__

    # Walk all .py files to discover component modules without relying
    # on pkgutil.walk_packages, which may trigger __init__.py __getattr__
    # and fail on components with missing optional dependencies.
    for root, _dirs, files in os.walk(components_pkg_path):
        for filename in files:
            if not filename.endswith(".py") or filename.startswith("_"):
                continue

            filepath = Path(root) / filename
            # Convert filesystem path to module path
            relative = filepath.relative_to(components_pkg_path)
            parts = list(relative.with_suffix("").parts)
            module_name = f"{components_pkg_name}.{'.'.join(parts)}"

            try:
                module = importlib.import_module(module_name)
            except Exception:  # noqa: S112 - intentionally skip modules with missing optional deps
                continue

            for attr_name, attr_value in inspect.getmembers(module, inspect.isclass):
                if (
                    issubclass(attr_value, Component)
                    and attr_value is not Component
                    and attr_value.__module__ == module_name
                ):
                    qualified_name = f"{module_name}.{attr_name}"
                    discovered.append((qualified_name, attr_value))

    return discovered


def _get_output_display_names(component_class: type) -> list[tuple[str, str]]:
    """Extract (output_name, display_name) pairs from a component class's outputs.

    Returns:
        List of (output_name, display_name) tuples.
    """
    outputs = getattr(component_class, "outputs", None)
    if not outputs:
        return []

    results = []
    for output in outputs:
        display_name = getattr(output, "display_name", None)
        name = getattr(output, "name", "unknown")
        if display_name is not None:
            results.append((name, display_name))
    return results


def _get_input_display_names(component_class: type) -> list[tuple[str, str]]:
    """Extract (input_name, display_name) pairs from a component class's inputs.

    Returns:
        List of (input_name, display_name) tuples.
    """
    inputs = getattr(component_class, "inputs", None)
    if not inputs:
        return []

    results = []
    for inp in inputs:
        display_name = getattr(inp, "display_name", None)
        name = getattr(inp, "name", "unknown")
        if display_name is not None:
            results.append((name, display_name))
    return results


# Discover all components once at module level for reuse across tests
_ALL_COMPONENTS = _discover_all_component_classes()


class TestOutputDisplayNames:
    """Validate that no component output uses deprecated display names."""

    def test_should_not_have_data_as_output_display_name(self):
        """No component output should have display_name='Data'.

        The correct display name after migration is 'JSON'.
        """
        violations: list[str] = []

        for qualified_name, component_class in _ALL_COMPONENTS:
            for output_name, display_name in _get_output_display_names(component_class):
                if display_name == DEPRECATED_OUTPUT_DISPLAY_NAME_DATA:
                    violations.append(
                        f"{qualified_name} output '{output_name}' has "
                        f"display_name='{DEPRECATED_OUTPUT_DISPLAY_NAME_DATA}' "
                        f"(should be '{EXPECTED_DATA_REPLACEMENT}')"
                    )

        assert not violations, (
            f"Found {len(violations)} output(s) still using deprecated "
            f"display_name='{DEPRECATED_OUTPUT_DISPLAY_NAME_DATA}':\n" + "\n".join(f"  - {v}" for v in violations)
        )

    def test_should_not_have_dataframe_as_output_display_name(self):
        """No component output should have display_name='DataFrame'.

        The correct display name after migration is 'Table'.
        """
        violations: list[str] = []

        for qualified_name, component_class in _ALL_COMPONENTS:
            for output_name, display_name in _get_output_display_names(component_class):
                if display_name == DEPRECATED_OUTPUT_DISPLAY_NAME_DATAFRAME:
                    violations.append(
                        f"{qualified_name} output '{output_name}' has "
                        f"display_name='{DEPRECATED_OUTPUT_DISPLAY_NAME_DATAFRAME}' "
                        f"(should be '{EXPECTED_DATAFRAME_REPLACEMENT}')"
                    )

        assert not violations, (
            f"Found {len(violations)} output(s) still using deprecated "
            f"display_name='{DEPRECATED_OUTPUT_DISPLAY_NAME_DATAFRAME}':\n" + "\n".join(f"  - {v}" for v in violations)
        )

    def test_should_not_have_dataframe_as_input_display_name(self):
        """No component input should have display_name='DataFrame'.

        The correct display name after migration is 'Table'.
        """
        violations: list[str] = []

        for qualified_name, component_class in _ALL_COMPONENTS:
            for input_name, display_name in _get_input_display_names(component_class):
                if display_name == DEPRECATED_OUTPUT_DISPLAY_NAME_DATAFRAME:
                    violations.append(
                        f"{qualified_name} input '{input_name}' has "
                        f"display_name='{DEPRECATED_OUTPUT_DISPLAY_NAME_DATAFRAME}' "
                        f"(should be '{EXPECTED_DATAFRAME_REPLACEMENT}')"
                    )

        assert not violations, (
            f"Found {len(violations)} input(s) still using deprecated "
            f"display_name='{DEPRECATED_OUTPUT_DISPLAY_NAME_DATAFRAME}':\n" + "\n".join(f"  - {v}" for v in violations)
        )

    def test_should_not_have_data_or_dataframe_as_display_name(self):
        """No component output or input should have display_name='Data or DataFrame'."""
        violations: list[str] = []

        for qualified_name, component_class in _ALL_COMPONENTS:
            for output_name, display_name in _get_output_display_names(component_class):
                if display_name == DEPRECATED_DISPLAY_NAME_DATA_OR_DATAFRAME:
                    violations.append(
                        f"{qualified_name} output '{output_name}' has "
                        f"display_name='{DEPRECATED_DISPLAY_NAME_DATA_OR_DATAFRAME}'"
                    )

            for input_name, display_name in _get_input_display_names(component_class):
                if display_name == DEPRECATED_DISPLAY_NAME_DATA_OR_DATAFRAME:
                    violations.append(
                        f"{qualified_name} input '{input_name}' has "
                        f"display_name='{DEPRECATED_DISPLAY_NAME_DATA_OR_DATAFRAME}'"
                    )

        assert not violations, (
            f"Found {len(violations)} field(s) still using deprecated "
            f"display_name='{DEPRECATED_DISPLAY_NAME_DATA_OR_DATAFRAME}':\n" + "\n".join(f"  - {v}" for v in violations)
        )


class TestComponentDiscoverySanity:
    """Sanity checks to ensure the test infrastructure itself is working."""

    def test_should_discover_a_minimum_number_of_components(self):
        """Ensure we are actually scanning a meaningful number of components.

        If this fails, it means the discovery mechanism is broken and the
        display name tests above are vacuously passing.
        """
        assert len(_ALL_COMPONENTS) >= MINIMUM_EXPECTED_COMPONENTS, (
            f"Only discovered {len(_ALL_COMPONENTS)} components, expected at least "
            f"{MINIMUM_EXPECTED_COMPONENTS}. Component discovery may be broken."
        )

    def test_should_find_components_with_outputs(self):
        """At least some discovered components should have outputs defined."""
        components_with_outputs = [name for name, cls in _ALL_COMPONENTS if getattr(cls, "outputs", None)]
        assert len(components_with_outputs) > 0, "No components with outputs found. Output inspection may be broken."

    def test_should_find_components_with_inputs(self):
        """At least some discovered components should have inputs defined."""
        components_with_inputs = [name for name, cls in _ALL_COMPONENTS if getattr(cls, "inputs", None)]
        assert len(components_with_inputs) > 0, "No components with inputs found. Input inspection may be broken."
