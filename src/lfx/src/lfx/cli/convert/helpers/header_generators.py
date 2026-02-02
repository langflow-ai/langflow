"""Generate header sections of the output file (imports, custom components, prompts)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ..constants import COMPONENT_IMPORTS
from .import_extraction import categorize_imports, extract_imports_from_code, strip_custom_code_imports

if TYPE_CHECKING:
    from ..types import FlowInfo, NodeInfo

_SINGLE_ITEM = 1


def generate_header(lines: list[str], flow_info: FlowInfo) -> None:
    """Generate the module docstring header."""
    lines.append(f'"""Flow: {flow_info.name}')
    if flow_info.description:
        lines.append(f"\n{flow_info.description}")
    lines.append("\nAuto-generated from JSON using `lfx convert`.")
    lines.append("Review and adjust as needed before committing.")
    lines.append('"""')
    lines.append("")
    lines.append("from __future__ import annotations")
    lines.append("")


def generate_imports(lines: list[str], flow_info: FlowInfo) -> None:
    """Generate import statements for components."""
    imports_by_module: dict[str, set[str]] = {}

    for node in flow_info.nodes:
        if node.has_custom_code:
            continue
        import_path = COMPONENT_IMPORTS.get(node.node_type)
        if import_path:
            module, class_name = import_path.rsplit(".", 1)
            if module not in imports_by_module:
                imports_by_module[module] = set()
            imports_by_module[module].add(class_name)

    lines.append("from lfx.graph import Graph")
    for module in sorted(imports_by_module.keys()):
        classes = sorted(imports_by_module[module])
        if len(classes) == _SINGLE_ITEM:
            lines.append(f"from {module} import {classes[0]}")
        else:
            lines.append(f"from {module} import (")
            lines.extend(f"    {cls}," for cls in classes)
            lines.append(")")
    lines.append("")


def generate_unknown_components_warning(lines: list[str], flow_info: FlowInfo) -> None:
    """Generate warning section for components not found in COMPONENT_IMPORTS."""
    if not flow_info.unknown_components:
        return

    lines.extend(
        [
            "",
            "# " + "=" * 70,
            "# WARNING: Unknown Components",
            "# " + "=" * 70,
            "# The following components are not in the default lfx imports.",
            "# You need to manually import them or convert them to custom components.",
            "#",
        ]
    )
    lines.extend(f"# TODO: Import or define '{c}'" for c in sorted(flow_info.unknown_components))
    lines.extend(
        [
            "#",
            "# Options:",
            "#   1. Add the import manually if the component exists elsewhere",
            "#   2. Convert the node to a custom component in the Langflow UI",
            "#   3. Add the component mapping to lfx.cli.convert.constants.COMPONENT_IMPORTS",
            "",
        ]
    )


def generate_global_variables_section(lines: list[str], flow_info: FlowInfo) -> None:
    """Generate documentation section for global variables used in the flow."""
    if not flow_info.global_variables:
        return

    sorted_vars = sorted(flow_info.global_variables)
    lines.extend(
        [
            "",
            "# " + "=" * 70,
            "# Global Variables",
            "# " + "=" * 70,
            "# This flow uses the following global variables (referenced as {var_name}).",
            "# These must be provided at runtime via the global_variables parameter.",
            "#",
        ]
    )
    lines.extend(f"# - {var_name}" for var_name in sorted_vars)
    lines.extend(
        [
            "#",
            "# Example usage:",
            "#   graph = get_graph()",
            "#   result = await graph.run(",
            "#       input_value='Hello',",
            "#       global_variables={",
        ]
    )
    lines.extend(f"#           '{var_name}': 'your_value_here'," for var_name in sorted_vars)
    lines.extend(
        [
            "#       },",
            "#   )",
            "",
        ]
    )


def generate_custom_components(lines: list[str], flow_info: FlowInfo) -> None:
    """Generate custom component class definitions."""
    custom_components = [n for n in flow_info.nodes if n.has_custom_code]
    if not custom_components:
        return

    unique_components = _deduplicate_custom_components(custom_components)
    if not unique_components:
        return

    lines.append("")
    lines.append("# " + "=" * 70)
    lines.append("# Custom Components")
    lines.append("# " + "=" * 70)
    lines.append("# NOTE: Review and move to a separate file if needed.")
    lines.append("")

    _generate_consolidated_imports(lines, unique_components)

    for display_name, code in unique_components:
        lines.append(f"# Custom component: {display_name}")
        clean_code = strip_custom_code_imports(code)
        lines.append(clean_code.rstrip())
        lines.append("")


def _deduplicate_custom_components(custom_components: list[NodeInfo]) -> list[tuple[str, str]]:
    """Deduplicate custom components by class name."""
    seen_classes: dict[str, str] = {}
    unique_components: list[tuple[str, str]] = []

    for node in custom_components:
        if not node.custom_code:
            continue
        component_match = re.search(
            r"class\s+(\w+)\s*\(\s*(?:\w+\.)*(?:Component|CustomComponent)",
            node.custom_code,
        )
        if component_match:
            class_name = component_match.group(1)
        else:
            class_match = re.search(r"class\s+(\w+)", node.custom_code)
            class_name = class_match.group(1) if class_match else None
        if class_name and class_name not in seen_classes:
            seen_classes[class_name] = node.custom_code
            unique_components.append((node.display_name, node.custom_code))

    return unique_components


def _generate_consolidated_imports(lines: list[str], unique_components: list[tuple[str, str]]) -> None:
    """Generate consolidated imports from all custom components."""
    all_langflow_imports: set[str] = set()
    all_lfx_imports: set[str] = set()
    all_other_imports: list[str] = []
    seen_other_imports: set[str] = set()

    for _, code in unique_components:
        imports, _ = extract_imports_from_code(code)
        langflow_imps, lfx_imps, other_imps = categorize_imports(imports)
        all_langflow_imports.update(langflow_imps)
        all_lfx_imports.update(lfx_imps)
        for imp in other_imps:
            if imp not in seen_other_imports:
                seen_other_imports.add(imp)
                all_other_imports.append(imp)

    lines.extend(sorted(all_other_imports))
    if all_other_imports:
        lines.append("")

    lines.extend(sorted(all_lfx_imports))

    langflow_only = [
        imp
        for imp in sorted(all_langflow_imports)
        if not any(lfx_imp.replace("lfx", "langflow") == imp for lfx_imp in all_lfx_imports)
    ]
    lines.extend(langflow_only)

    if all_lfx_imports or all_langflow_imports:
        lines.append("")


def generate_prompts(lines: list[str], flow_info: FlowInfo) -> None:
    """Generate prompt constant definitions."""
    if not flow_info.prompts:
        return

    lines.append("")
    lines.append("# " + "=" * 70)
    lines.append("# Prompts and System Instructions")
    lines.append("# " + "=" * 70)
    lines.append("# NOTE: Consider moving to a separate prompts.py file.")
    lines.append("")
    for name, value in flow_info.prompts.items():
        escaped = value.replace('"""', r"\"\"\"")
        lines.append(f'{name} = """')
        lines.append(escaped.rstrip())
        lines.append('"""')
        lines.append("")
