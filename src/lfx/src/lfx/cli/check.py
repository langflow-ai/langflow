"""CLI check command for detecting and updating outdated components in flows."""

from __future__ import annotations

import copy
import difflib
import sys
from functools import partial
from typing import Any

import orjson
import typer
from aiofile import async_open
from asyncer import syncify
from rich.console import Console

from lfx.interface.components import get_and_cache_all_types_dict
from lfx.log.logger import logger
from lfx.services.deps import get_settings_service

# Initialize console (default to stdout)
console = Console()


def get_interactive_console(output: str | None = None) -> Console:
    """Get console for interactive prompts.

    When output is stdout ("-"), use stderr for prompts to avoid mixing with JSON output.
    Otherwise, use the default stdout console.
    """
    if output == "-":
        return Console(file=sys.stderr)
    return console


# ORJSON options for pretty formatting
ORJSON_OPTIONS = orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS

# Components to skip during updates
SKIPPED_COMPONENTS = {"LanguageModelComponent"}


async def load_specific_components(component_modules: set[str]) -> dict:
    """Load only the specific components mentioned in the flow metadata.

    Args:
        component_modules: Set of module paths like 'lfx.components.input_output.chat.ChatInput'

    Returns:
        Dictionary mapping component types to their templates
    """
    import importlib

    from lfx.custom.utils import create_component_template

    components_dict = {}

    for module_path in component_modules:
        try:
            # Import the module and get the component class
            module_parts = module_path.split(".")
            module_name = ".".join(module_parts[:-1])
            class_name = module_parts[-1]

            # Security: only allow trusted component namespaces
            allowed_prefixes = ("lfx.components.", "langflow.components.")
            if not module_name.startswith(allowed_prefixes):
                await logger.awarning(
                    f"Skipping untrusted module path '{module_path}'. "
                    "Only 'lfx.components.*' and 'langflow.components.*' modules are allowed for selective loading."
                )
                continue

            if not module_name or not class_name:
                await logger.awarning(f"Invalid component path '{module_path}'")
                continue

            await logger.adebug(f"Loading component {class_name} from {module_name}")

            module = importlib.import_module(module_name)
            component_class = getattr(module, class_name)

            # Create component instance and template
            try:
                component_instance = component_class()
            except TypeError as te:
                await logger.awarning(f"Failed to instantiate component '{class_name}' from '{module_name}': {te}")
                continue
            comp_template, _ = create_component_template(
                component_extractor=component_instance, module_name=module_path
            )

            # Use the class name as the component type
            components_dict[class_name] = comp_template

        except (ImportError, AttributeError, RuntimeError) as e:
            await logger.awarning(f"Failed to load component {module_path}: {e}")
            continue

    await logger.adebug(f"Successfully loaded {len(components_dict)} specific components")
    return components_dict


def find_component_in_types(component_type: str, all_types_dict: dict) -> dict | None:
    """Find a component by searching across all categories in all_types_dict.

    Args:
        component_type: The component type to search for (e.g., 'Agent', 'CalculatorComponent')
        all_types_dict: Dictionary of component categories and their components

    Returns:
        The component dict if found, None otherwise
    """
    # First try direct lookup (for exact matches)
    if component_type in all_types_dict:
        return all_types_dict[component_type]

    # Search across all categories
    for category_components in all_types_dict.values():
        if isinstance(category_components, dict):
            # Look for exact component name match
            if component_type in category_components:
                return category_components[component_type]

            # Look for component by display name or class name
            for comp_name, comp_data in category_components.items():
                if isinstance(comp_data, dict):
                    # Check display name
                    if comp_data.get("display_name") == component_type:
                        return comp_data
                    # Check if the component type matches any known mappings
                    if _matches_component_type(component_type, comp_name, comp_data):
                        return comp_data

    return None


def _matches_component_type(flow_type: str, comp_name: str, comp_data: dict) -> bool:
    """Check if a flow component type matches a loaded component.

    Args:
        flow_type: Component type from the flow (e.g., 'Agent', 'CalculatorComponent')
        comp_name: Component name from loaded components
        comp_data: Component data dictionary

    Returns:
        True if they match, False otherwise
    """
    # Direct name match
    if flow_type == comp_name:
        return True

    # Check display name
    display_name = comp_data.get("display_name", "")
    if flow_type == display_name:
        return True

    # Common mappings for known component types
    mappings = {
        "Agent": ["AgentComponent", "agent"],
        "CalculatorComponent": ["Calculator", "CalculatorTool", "calculator"],
        "ChatInput": ["ChatInputComponent", "chat_input"],
        "ChatOutput": ["ChatOutputComponent", "chat_output"],
        "URLComponent": ["URL", "URLTool", "url"],
    }

    if flow_type in mappings:
        return comp_name in mappings[flow_type] or display_name in mappings[flow_type]

    return False


async def check_flow_components(
    flow_path: str,
    *,
    update: bool = False,
    force: bool = False,
    interactive: bool = False,
    output: str | None = None,
    in_place: bool = False,
    backup: bool = False,
    show_diff: bool = False,
) -> dict:
    """Check a JSON flow for outdated components using code_hash."""
    # Load flow
    try:
        async with async_open(flow_path, "r") as f:
            flow_data = orjson.loads(await f.read())
    except (OSError, orjson.JSONDecodeError) as e:
        return {
            "error": f"Failed to load flow file: {e}",
            "flow_path": flow_path,
        }

    # Check if we can use selective component loading based on metadata
    component_modules = set()
    for node in flow_data.get("data", {}).get("nodes", []) if "data" in flow_data else flow_data.get("nodes", []):
        node_data = node.get("data", {})
        node_type = node_data.get("type")
        if node_type and node_type not in {"note", "genericNode", "noteNode"}:
            node_template = node_data.get("node", {})
            node_metadata = node_template.get("metadata", {})
            module_info = node_metadata.get("module")
            if module_info:
                component_modules.add(module_info)

    # Load components efficiently
    all_types_dict = {}
    if component_modules:
        await logger.adebug(f"Found {len(component_modules)} component modules in flow metadata, loading selectively")
        all_types_dict = await load_specific_components(component_modules)
        if not all_types_dict:
            await logger.adebug(
                "Selective component loading returned empty dict, falling back to full component catalog"
            )

    # Load full catalog if no selective loading was attempted or if it returned empty
    if not all_types_dict:
        await logger.adebug("Loading all component types")
        settings_service = get_settings_service()
        if settings_service is None:
            return {
                "error": "Settings service is not available. Cannot load component types.",
                "flow_path": flow_path,
            }
        try:
            all_types_dict = await get_and_cache_all_types_dict(settings_service)
            # Log available component types for debugging
            if all_types_dict:
                available_types = list(all_types_dict.keys())
                await logger.adebug(f"Loaded {len(available_types)} component types: {available_types[:10]}...")
            else:
                await logger.adebug("No component types loaded")
        except (ImportError, RuntimeError) as e:
            return {
                "error": f"Failed to load component types: {e}",
                "flow_path": flow_path,
            }

    # Check each node
    outdated_components: list[dict[str, Any]] = []
    check_errors: list[dict[str, Any]] = []
    nodes = flow_data.get("data", {}).get("nodes", []) if "data" in flow_data else flow_data.get("nodes", [])

    for node in nodes:
        node_data = node.get("data", {})
        node_type = node_data.get("type")

        if node_type and node_type not in {"note", "genericNode", "noteNode"}:
            # Find the component in the loaded types (search across all categories)
            found_component = find_component_in_types(node_type, all_types_dict)
            if found_component:
                await logger.adebug(f"Checking component type '{node_type}' for updates")
                result = check_component_outdated(node, all_types_dict, found_component, show_diff=show_diff)
                if "error" in result:
                    # Component check failed (e.g., missing code) - treat as error
                    check_errors.append(result)
                    await logger.awarning(f"Failed to check component '{node_type}': {result['error']}")
                elif result["outdated"]:
                    outdated_components.append(result)
                    await logger.adebug(
                        f"Found outdated component: {node_type} "
                        f"({result.get('comparison_method', 'unknown')} comparison)"
                    )
            else:
                # Log when component type is not found in all_types_dict (skip UI-only types)
                await logger.adebug(f"Component type '{node_type}' not found in loaded components")

    # Handle updates if requested
    if update or interactive:
        # auto_update=True means apply updates automatically without prompts
        # auto_update=False means interactive mode (prompt for each component)
        is_auto_mode = update and not interactive
        return await handle_updates(
            flow_path,
            flow_data,
            outdated_components,
            all_types_dict,
            auto_update=is_auto_mode,
            force=force,
            output=output,
            in_place=in_place,
            backup=backup,
        )

    result = {
        "flow_path": flow_path,
        "outdated_components": outdated_components,
        "total_nodes": len(nodes),
        "outdated_count": len(outdated_components),
    }

    # Include check errors if any occurred
    if check_errors:
        result["check_errors"] = check_errors
        result["error_count"] = len(check_errors)

    return result


def check_component_outdated(
    node: dict, all_types_dict: dict, latest_component: dict | None = None, *, show_diff: bool = False
) -> dict:
    """Check if a component is outdated using code_hash comparison."""
    node_data = node.get("data", {})
    node_type = node_data.get("type")
    node_template = node_data.get("node", {})
    node_metadata = node_template.get("metadata", {})

    # Get latest component template (use provided component or search for it)
    if latest_component is None:
        latest_component = all_types_dict.get(node_type, {})
    latest_metadata = latest_component.get("metadata", {})

    # Compare code hashes first, fall back to code comparison
    node_hash = node_metadata.get("code_hash")
    latest_hash = latest_metadata.get("code_hash")

    if node_hash and latest_hash:
        # Use hash comparison when available
        outdated = node_hash != latest_hash and node_type not in SKIPPED_COMPONENTS
    else:
        # Fall back to code string comparison when hashes are not available
        current_template = node_template.get("template", {})
        latest_template = latest_component.get("template", {})

        current_code = current_template.get("code", {}).get("value", "")
        latest_code = latest_template.get("code", {}).get("value", "")

        # If neither has code, this is likely a bug - components should have code
        # Return an error rather than silently treating them as the same
        if not current_code and not latest_code:
            return {
                "outdated": False,
                "error": (
                    f"Component '{node_type}' has no code in both current and latest versions. "
                    "This may indicate a bug in component structure or code extraction."
                ),
                "node_id": node.get("id"),
                "component_type": node_type,
            }
        outdated = current_code != latest_code and node_type not in SKIPPED_COMPONENTS

    if not outdated:
        return {"outdated": False}

    # Check breaking changes
    breaking_change = check_breaking_changes(node_template, latest_component)

    # Analyze specific changes
    changes = analyze_component_changes(node_template, latest_component, show_diff=show_diff)

    # Determine comparison method used
    comparison_method = "hash" if (node_hash and latest_hash) else "code"

    return {
        "outdated": True,
        "breaking_change": breaking_change,
        "node_id": node["id"],
        "component_type": node_type,
        "display_name": node_template.get("display_name", node_type),
        "user_edited": node_template.get("edited", False),
        "node_hash": node_hash,
        "latest_hash": latest_hash,
        "comparison_method": comparison_method,
        "changes": changes,
    }


def check_breaking_changes(current_node: dict, latest_component: dict) -> bool:
    """Check if the update would introduce breaking changes."""
    # Check output changes
    current_outputs = current_node.get("outputs", [])
    latest_outputs = latest_component.get("outputs", [])

    current_output_names = {out.get("name") for out in current_outputs}
    latest_output_names = {out.get("name") for out in latest_outputs}

    # Removed outputs are breaking
    if current_output_names - latest_output_names:
        return True

    # Pre-index latest outputs by name for O(1) lookup
    latest_outputs_by_name = {out.get("name"): out for out in latest_outputs}

    # Check for output type changes
    for current_out in current_outputs:
        output_name = current_out.get("name")
        latest_out = latest_outputs_by_name.get(output_name)
        if latest_out is not None:
            current_types = set(current_out.get("types", []))
            latest_types = set(latest_out.get("types", []))
            # If latest types don't include all current types, it's breaking
            if not current_types.issubset(latest_types):
                return True

    # Check template changes
    current_template = current_node.get("template", {})
    latest_template = latest_component.get("template", {})

    current_inputs = set(current_template.keys()) - {"_type", "code"}
    latest_inputs = set(latest_template.keys()) - {"_type", "code"}

    # Removed inputs are breaking
    if current_inputs - latest_inputs:
        return True

    # Check for required inputs that were added
    for input_name in latest_inputs - current_inputs:
        input_field = latest_template[input_name]
        if input_field.get("required", False):
            return True

    return False


def analyze_component_changes(current_node: dict, latest_component: dict, *, show_diff: bool = False) -> dict[str, Any]:
    """Analyze specific changes between current and latest component versions."""
    changes: dict[str, Any] = {
        "added_inputs": [],
        "removed_inputs": [],
        "added_outputs": [],
        "removed_outputs": [],
        "modified_inputs": [],
        "code_diff": None,
    }

    current_template = current_node.get("template", {})
    latest_template = latest_component.get("template", {})

    # Analyze input changes
    current_inputs = set(current_template.keys()) - {"_type", "code"}
    latest_inputs = set(latest_template.keys()) - {"_type", "code"}

    for input_name in latest_inputs - current_inputs:
        input_field = latest_template[input_name]
        if changes["added_inputs"] is not None:
            changes["added_inputs"].append(
                {
                    "name": input_name,
                    "type": input_field.get("type", "unknown"),
                    "required": input_field.get("required", False),
                    "default": input_field.get("value"),
                    "display_name": input_field.get("display_name", input_name),
                }
            )

    for input_name in current_inputs - latest_inputs:
        input_field = current_template[input_name]
        if changes["removed_inputs"] is not None:
            changes["removed_inputs"].append(
                {
                    "name": input_name,
                    "type": input_field.get("type", "unknown"),
                    "display_name": input_field.get("display_name", input_name),
                }
            )

    # Analyze output changes
    current_outputs = current_node.get("outputs", [])
    latest_outputs = latest_component.get("outputs", [])

    current_output_names = {out.get("name") for out in current_outputs}
    latest_output_names = {out.get("name") for out in latest_outputs}

    for output in latest_outputs:
        if output.get("name") not in current_output_names and changes["added_outputs"] is not None:
            changes["added_outputs"].append(
                {
                    "name": output.get("name"),
                    "types": output.get("types", []),
                    "display_name": output.get("display_name", output.get("name")),
                }
            )

    for output in current_outputs:
        if output.get("name") not in latest_output_names and changes["removed_outputs"] is not None:
            changes["removed_outputs"].append(
                {
                    "name": output.get("name"),
                    "types": output.get("types", []),
                    "display_name": output.get("display_name", output.get("name")),
                }
            )

    # Analyze code changes (only if show_diff is enabled, as it can be expensive)
    if show_diff:
        current_code = current_template.get("code", {}).get("value", "")
        latest_code = latest_template.get("code", {}).get("value", "")

        if current_code != latest_code:
            diff_result = generate_code_diff(current_code, latest_code)
            changes["code_diff"] = diff_result

    return changes


def generate_code_diff(current_code: str, latest_code: str) -> dict[str, Any] | None:
    """Generate a unified diff between current and latest code."""
    if not current_code and not latest_code:
        return None

    current_lines = current_code.splitlines(keepends=True)
    latest_lines = latest_code.splitlines(keepends=True)

    diff_lines = list(
        difflib.unified_diff(
            current_lines,
            latest_lines,
            fromfile="current",
            tofile="latest",
            n=3,  # 3 lines of context
        )
    )

    if not diff_lines:
        return None

    # Parse diff to extract meaningful changes
    added_lines: list[str] = []
    removed_lines: list[str] = []
    context_blocks: list[list[str]] = []

    current_block: list[str] = []
    for line in diff_lines[2:]:  # Skip the '---' and '+++' headers
        if line.startswith("@@"):
            if current_block:
                context_blocks.append(current_block)
                current_block = []
            current_block.append(line.strip())
        elif line.startswith("+") and not line.startswith("+++"):
            added_lines.append(line[1:].rstrip())
            current_block.append(line.rstrip())
        elif line.startswith("-") and not line.startswith("---"):
            removed_lines.append(line[1:].rstrip())
            current_block.append(line.rstrip())
        elif line.startswith(" "):
            current_block.append(line.rstrip())

    if current_block:
        context_blocks.append(current_block)

    return {
        "added_lines": added_lines,
        "removed_lines": removed_lines,
        "context_blocks": context_blocks,
        "full_diff": "".join(diff_lines),
    }


async def handle_updates(
    flow_path: str,
    flow_data: dict,
    outdated_components: list,
    all_types_dict: dict,
    *,
    auto_update: bool,
    force: bool,
    output: str | None = None,
    in_place: bool = False,
    backup: bool = False,
) -> dict:
    """Handle component updates with user interaction."""
    safe_updates = [comp for comp in outdated_components if not comp["breaking_change"]]
    breaking_updates = [comp for comp in outdated_components if comp["breaking_change"]]

    # Check if output/in_place is required before starting interactive prompts
    # Note: output can be "-" for stdout, which is valid
    if not auto_update and (safe_updates or breaking_updates) and output != "-" and output is None and not in_place:
        return {
            "error": "When applying updates, you must specify either --output <file>, --output -, or --in-place",
            "flow_path": flow_path,
            "applied_updates": 0,
        }

    applied_updates = 0
    failed_updates = []

    if auto_update:
        # Apply safe updates automatically
        for component in safe_updates:
            if await apply_component_update(flow_data, component, all_types_dict):
                applied_updates += 1
            else:
                failed_updates.append(component)

        # Apply breaking changes if force is enabled
        if force:
            for component in breaking_updates:
                if await apply_component_update(flow_data, component, all_types_dict):
                    applied_updates += 1
                else:
                    failed_updates.append(component)
    else:
        # Interactive mode - prompt for each component individually
        # Pass output parameter so prompts can use stderr when output is stdout
        for component in safe_updates:
            if prompt_for_component_update(component, "safe", output=output):
                if await apply_component_update(flow_data, component, all_types_dict):
                    applied_updates += 1
                else:
                    failed_updates.append(component)

        for component in breaking_updates:
            if prompt_for_component_update(component, "breaking", output=output):
                if await apply_component_update(flow_data, component, all_types_dict):
                    applied_updates += 1
                else:
                    failed_updates.append(component)

    # Log any failed updates
    if failed_updates:
        await logger.awarning(
            f"Failed to apply {len(failed_updates)} update(s): {', '.join(c['component_type'] for c in failed_updates)}"
        )

    # Save updated flow
    output_path = None
    if applied_updates > 0:
        # Determine output path: --output takes precedence, then --in-place, otherwise error
        if output is not None:
            if output == "-":
                # Write to stdout
                output_path = "-"
                try:
                    # Write JSON to stdout
                    sys.stdout.write(orjson.dumps(flow_data, option=ORJSON_OPTIONS).decode())
                    sys.stdout.write("\n")
                    sys.stdout.flush()
                except OSError as e:
                    return {
                        "error": f"Failed to write to stdout: {e}",
                        "flow_path": flow_path,
                        "applied_updates": applied_updates,
                    }
            else:
                output_path = output
                try:
                    async with async_open(output_path, "w") as f:
                        await f.write(orjson.dumps(flow_data, option=ORJSON_OPTIONS).decode())
                except OSError as e:
                    return {
                        "error": f"Failed to save updated flow: {e}",
                        "flow_path": flow_path,
                        "applied_updates": applied_updates,
                    }
        elif in_place:
            output_path = flow_path
            backup_path = None
            try:
                # Create backup if requested
                if backup:
                    backup_path = f"{flow_path}.bak"
                    # Read original file content for backup
                    async with async_open(flow_path, "r") as original_file:
                        original_content = await original_file.read()
                    # Write backup
                    async with async_open(backup_path, "w") as backup_file:
                        await backup_file.write(original_content)
                    await logger.adebug(f"Created backup file: {backup_path}")

                # Write updated flow
                async with async_open(output_path, "w") as f:
                    await f.write(orjson.dumps(flow_data, option=ORJSON_OPTIONS).decode())
            except OSError as e:
                return {
                    "error": f"Failed to save updated flow: {e}",
                    "flow_path": flow_path,
                    "applied_updates": applied_updates,
                }
        else:
            return {
                "error": "When applying updates, you must specify either --output <file>, --output -, or --in-place",
                "flow_path": flow_path,
                "applied_updates": applied_updates,
            }

    result = {
        "flow_path": flow_path,
        "total_nodes": len(
            flow_data.get("data", {}).get("nodes", []) if "data" in flow_data else flow_data.get("nodes", [])
        ),
        "outdated_count": len(outdated_components),
        "applied_updates": applied_updates,
        "safe_updates": len(safe_updates),
        "breaking_updates": len(breaking_updates),
        "updated": applied_updates > 0,
    }
    if output_path is not None:
        result["output_path"] = output_path
    if backup and in_place and applied_updates > 0:
        result["backup_path"] = f"{flow_path}.bak"
    return result


def prompt_for_component_update(component: dict, update_type: str, output: str | None = None) -> bool:
    """Prompt user for individual component update.

    Args:
        component: Component data to update
        update_type: Type of update ("safe" or "breaking")
        output: Output destination (None, file path, or "-" for stdout)
    """
    display_name = component.get("display_name", component.get("component_type"))
    node_id = component.get("node_id")
    changes = component.get("changes", {})

    # Use stderr console when output is stdout to avoid mixing with JSON
    interactive_console = get_interactive_console(output)

    interactive_console.print(f"\n📦 {display_name} ({node_id})")

    # Show changes
    if changes.get("added_inputs"):
        interactive_console.print("  New inputs:")
        for inp in changes["added_inputs"]:
            required = "required" if inp["required"] else "optional"
            default = f", default: {inp['default']}" if inp.get("default") else ""
            interactive_console.print(f"    • {inp['display_name']} ({inp['type']}, {required}{default})")

    if changes.get("removed_inputs"):
        interactive_console.print("  Removed inputs:")
        for inp in changes["removed_inputs"]:
            interactive_console.print(f"    • {inp['display_name']} ({inp['type']})")

    if changes.get("added_outputs"):
        interactive_console.print("  New outputs:")
        for out in changes["added_outputs"]:
            types_str = ", ".join(out["types"])
            interactive_console.print(f"    • {out['display_name']} ({types_str})")

    if changes.get("removed_outputs"):
        interactive_console.print("  Removed outputs:")
        for out in changes["removed_outputs"]:
            types_str = ", ".join(out["types"])
            interactive_console.print(f"    • {out['display_name']} ({types_str})")

    # Show code diff for non-breaking changes
    if changes.get("code_diff") and update_type == "safe":
        interactive_console.print("  Code changes:")
        diff_data = changes["code_diff"]

        # Show a summary of changes
        if diff_data["added_lines"] or diff_data["removed_lines"]:
            interactive_console.print(
                f"    📝 {len(diff_data['added_lines'])} additions, {len(diff_data['removed_lines'])} deletions"
            )

        # Show all diff blocks in interactive mode
        for i, block in enumerate(diff_data["context_blocks"]):
            interactive_console.print(f"    ┌─ Change {i + 1}:")
            for line in block:
                if line.startswith("+"):
                    interactive_console.print(f"    │ [green]{line}[/green]")
                elif line.startswith("-"):
                    interactive_console.print(f"    │ [red]{line}[/red]")
                elif line.startswith("@@"):
                    interactive_console.print(f"    │ [cyan]{line}[/cyan]")
                else:
                    interactive_console.print(f"    │ {line}")
            interactive_console.print("    └─")

    if update_type == "breaking":
        interactive_console.print("  ⚠️  This is a breaking change that may affect connected components")

    # Use the interactive console for prompt text (stderr when output is stdout)
    # Then use Python's built-in input() which reads from stdin (correct for user input)
    while True:
        interactive_console.print("? Update this component? [y/n] (n): ", end="")
        try:
            response = input().strip().lower()
        except (EOFError, KeyboardInterrupt):
            # Handle stdin closed or user interrupt - default to not updating
            interactive_console.print()  # Print newline for clean output
            return False
        if not response:  # Empty input means default
            response = "n"
        if response in ["y", "yes", "n", "no"]:
            break
        interactive_console.print("[yellow]Please enter 'y' or 'n'[/yellow]")

    return response in ["y", "yes"]


async def apply_component_update(flow_data: dict, component: dict, all_types_dict: dict) -> bool:
    """Apply a component update to the flow data.

    Returns:
        True if update was applied successfully, False otherwise.
    """
    component_type = component["component_type"]
    node_id = component["node_id"]

    # Find the node in the flow data
    nodes = flow_data.get("data", {}).get("nodes", []) if "data" in flow_data else flow_data.get("nodes", [])

    for node in nodes:
        if node["id"] == node_id:
            # Find the latest component using our mapping function
            found_component = find_component_in_types(component_type, all_types_dict)
            if not found_component:
                await logger.awarning(f"Could not find latest component for {component_type}")
                return False

            # Store current user values before updating
            current_node_data = node["data"].get("node", {})
            current_template = current_node_data.get("template", {})
            user_values = {}

            # Extract user-set values
            for field_name, field_data in current_template.items():
                if isinstance(field_data, dict) and "value" in field_data:
                    user_values[field_name] = field_data["value"]

            # Update the node with the latest component data
            node["data"]["node"] = copy.deepcopy(found_component)

            # Restore user values where possible
            updated_template = node["data"]["node"].get("template", {})
            for field_name, user_value in user_values.items():
                if field_name in updated_template and isinstance(updated_template[field_name], dict):
                    updated_template[field_name]["value"] = user_value

            return True

    # Node not found
    await logger.awarning(f"Could not find node {node_id} in flow data")
    return False


@partial(syncify, raise_sync_error=False)
async def check_command(
    flow_path: str = typer.Argument(..., help="Path to the JSON flow file"),
    *,
    update: bool = typer.Option(False, "--update", help="Apply safe updates automatically"),  # noqa: FBT003
    force: bool = typer.Option(False, "--force", help="Apply all updates including breaking changes"),  # noqa: FBT003
    interactive: bool = typer.Option(
        False,  # noqa: FBT003
        "--interactive",
        "-i",
        help="Prompt for each component update individually",
    ),
    output: str | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path, or '-' for stdout (requires --update or --interactive)",
    ),
    in_place: bool = typer.Option(
        False,  # noqa: FBT003
        "--in-place",
        help="Update the input file in place (requires --update or --interactive)",
    ),
    backup: bool = typer.Option(
        True,  # noqa: FBT003
        "--backup/--no-backup",
        help="Create a backup file (.bak) before in-place modification (default: True, requires --in-place)",
    ),
    show_diff: bool = typer.Option(
        False,  # noqa: FBT003
        "--show-diff",
        help="Calculate and show code differences (can be expensive for large components)",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show verbose output"),  # noqa: FBT003
) -> None:
    """Check a flow for outdated components and optionally update them."""
    # Configure logging for debugging
    if verbose:
        from lfx.log.logger import configure

        configure(log_level="DEBUG", disable=False)
        await logger.ainfo("Starting component check...")

    try:
        result = await check_flow_components(
            flow_path,
            update=update,
            force=force,
            interactive=interactive,
            output=output,
            in_place=in_place,
            backup=backup,
            show_diff=show_diff,
        )
    except (OSError, RuntimeError, ImportError) as e:
        console.print(f"[red]Error checking flow: {e}[/red]")
        raise typer.Exit(1) from e

    if "error" in result:
        console.print(f"[red]Error: {result['error']}[/red]")
        raise typer.Exit(1)

    # Display results
    flow_path_str = result["flow_path"]
    total_nodes = result.get("total_nodes", 0)
    outdated_count = result.get("outdated_count", 0)
    applied_updates = result.get("applied_updates", 0)

    console.print(f"\nChecking flow: [bold]{flow_path_str}[/bold]")
    console.print(f"Total nodes: {total_nodes}")
    console.print(f"Outdated components: {outdated_count}")

    # Display check errors if any occurred
    check_errors = result.get("check_errors", [])
    if check_errors:
        error_count = result.get("error_count", len(check_errors))
        console.print(f"[red]⚠️  {error_count} component check error(s) occurred:[/red]")
        for error_info in check_errors:
            component_type = error_info.get("component_type", "unknown")
            node_id = error_info.get("node_id", "unknown")
            error_msg = error_info.get("error", "Unknown error")
            console.print(f"  • {component_type} ({node_id}): [red]{error_msg}[/red]")

    if outdated_count == 0:
        console.print("[green]✅ All components are up to date![/green]")
        return

    if not update and not applied_updates:
        # Just showing status
        console.print(f"\n[yellow]⚠️  Found {outdated_count} outdated component(s)[/yellow]")
        console.print("Run with --update --output <file> or --update --in-place to apply safe updates")
        console.print("Run with --update --force --output <file> or --update --force --in-place for all updates")

        # Show component details
        for comp in result.get("outdated_components", []):
            display_name = comp.get("display_name", comp.get("component_type"))
            node_id = comp.get("node_id")
            breaking = " (breaking)" if comp.get("breaking_change") else ""
            console.print(f"  • {display_name} ({node_id}){breaking}")

    elif applied_updates > 0:
        safe_updates = result.get("safe_updates", 0)
        breaking_updates = result.get("breaking_updates", 0)

        console.print(f"\n[green]✅ Applied {applied_updates} update(s)[/green]")
        if safe_updates > 0:
            console.print(f"  • {safe_updates} safe update(s)")
        if breaking_updates > 0:
            console.print(f"  • {breaking_updates} breaking update(s)")
            console.print("[yellow]⚠️  Please test your flow thoroughly due to breaking changes[/yellow]")

        output_path = result.get("output_path")
        backup_path = result.get("backup_path")
        if output_path:
            if output_path == "-":
                console.print("Updated flow written to stdout")
            else:
                console.print(f"Updated flow saved to: [bold]{output_path}[/bold]")
                if backup_path:
                    console.print(f"Backup created: [bold]{backup_path}[/bold]")

    elif update and outdated_count > 0:
        # Updates were requested but none applied
        safe_updates = result.get("safe_updates", 0)
        breaking_updates = result.get("breaking_updates", 0)
        skipped = outdated_count - applied_updates

        if safe_updates > 0:
            console.print(f"[green]✅ Applied {safe_updates} safe update(s)[/green]")

        if breaking_updates > 0:
            console.print(
                f"[yellow]⚠️  {breaking_updates} component(s) with breaking changes skipped "
                f"(use --force to include)[/yellow]"
            )

        if skipped > 0 and not breaking_updates:
            console.print(f"[yellow]⚠️  {skipped} component(s) skipped[/yellow]")
