"""CLI check command for detecting and updating outdated components in flows."""

from __future__ import annotations

import copy
import difflib
from typing import Any

import orjson
import typer
from aiofile import async_open
from rich.console import Console
from rich.prompt import Prompt

from lfx.interface.components import get_and_cache_all_types_dict
from lfx.log.logger import logger
from lfx.services.deps import get_settings_service
from lfx.utils.async_helpers import run_until_complete

# Initialize console
console = Console()

# ORJSON options for pretty formatting
ORJSON_OPTIONS = orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS

# Components to skip during updates
SKIPPED_COMPONENTS = {"LanguageModelComponent"}

# Maximum context blocks to show in diff
MAX_CONTEXT_BLOCKS = 2


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
    flow_path: str, *, update: bool = False, force: bool = False, interactive: bool = False, output: str | None = None
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
    if component_modules:
        await logger.adebug(f"Found {len(component_modules)} component modules in flow metadata, loading selectively")
        all_types_dict = await load_specific_components(component_modules)
    else:
        await logger.adebug("No module metadata found, loading all component types")
        settings_service = get_settings_service()
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
    nodes = flow_data.get("data", {}).get("nodes", []) if "data" in flow_data else flow_data.get("nodes", [])

    for node in nodes:
        node_data = node.get("data", {})
        node_type = node_data.get("type")

        if node_type and node_type not in {"note", "genericNode", "noteNode"}:
            # Find the component in the loaded types (search across all categories)
            found_component = find_component_in_types(node_type, all_types_dict)
            if found_component:
                await logger.adebug(f"Checking component type '{node_type}' for updates")
                result = check_component_outdated(node, all_types_dict, found_component)
                if result["outdated"]:
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
        )

    return {
        "flow_path": flow_path,
        "outdated_components": outdated_components,
        "total_nodes": len(nodes),
        "outdated_count": len(outdated_components),
    }


def check_component_outdated(node: dict, all_types_dict: dict, latest_component: dict | None = None) -> dict:
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

        # If neither has code, consider them the same
        if not current_code and not latest_code:
            outdated = False
        else:
            outdated = current_code != latest_code and node_type not in SKIPPED_COMPONENTS

    if not outdated:
        return {"outdated": False}

    # Check breaking changes
    breaking_change = check_breaking_changes(node_template, latest_component)

    # Analyze specific changes
    changes = analyze_component_changes(node_template, latest_component)

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

    # Check for output type changes
    for current_out in current_outputs:
        for latest_out in latest_outputs:
            if current_out.get("name") == latest_out.get("name"):
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


def analyze_component_changes(current_node: dict, latest_component: dict) -> dict[str, Any]:
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

    # Analyze code changes
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
) -> dict:
    """Handle component updates with user interaction."""
    safe_updates = [comp for comp in outdated_components if not comp["breaking_change"]]
    breaking_updates = [comp for comp in outdated_components if comp["breaking_change"]]

    applied_updates = 0

    if auto_update:
        # Apply safe updates automatically
        for component in safe_updates:
            await apply_component_update(flow_data, component, all_types_dict)
            applied_updates += 1

        # Apply breaking changes if force is enabled
        if force:
            for component in breaking_updates:
                await apply_component_update(flow_data, component, all_types_dict)
                applied_updates += 1
    else:
        # Interactive mode - prompt for each component individually
        for component in safe_updates:
            if prompt_for_component_update(component, "safe"):
                await apply_component_update(flow_data, component, all_types_dict)
                applied_updates += 1

        for component in breaking_updates:
            if prompt_for_component_update(component, "breaking"):
                await apply_component_update(flow_data, component, all_types_dict)
                applied_updates += 1

    # Save updated flow
    if applied_updates > 0:
        output_path = output or flow_path
        try:
            async with async_open(output_path, "w") as f:
                await f.write(orjson.dumps(flow_data, option=ORJSON_OPTIONS).decode())
        except OSError as e:
            return {
                "error": f"Failed to save updated flow: {e}",
                "flow_path": flow_path,
                "applied_updates": applied_updates,
            }

    return {
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


def prompt_for_component_update(component: dict, update_type: str) -> bool:
    """Prompt user for individual component update."""
    display_name = component.get("display_name", component.get("component_type"))
    node_id = component.get("node_id")
    changes = component.get("changes", {})

    console.print(f"\n📦 {display_name} ({node_id})")

    # Show changes
    if changes.get("added_inputs"):
        console.print("  New inputs:")
        for inp in changes["added_inputs"]:
            required = "required" if inp["required"] else "optional"
            default = f", default: {inp['default']}" if inp.get("default") else ""
            console.print(f"    • {inp['display_name']} ({inp['type']}, {required}{default})")

    if changes.get("removed_inputs"):
        console.print("  Removed inputs:")
        for inp in changes["removed_inputs"]:
            console.print(f"    • {inp['display_name']} ({inp['type']})")

    if changes.get("added_outputs"):
        console.print("  New outputs:")
        for out in changes["added_outputs"]:
            types_str = ", ".join(out["types"])
            console.print(f"    • {out['display_name']} ({types_str})")

    if changes.get("removed_outputs"):
        console.print("  Removed outputs:")
        for out in changes["removed_outputs"]:
            types_str = ", ".join(out["types"])
            console.print(f"    • {out['display_name']} ({types_str})")

    # Show code diff for non-breaking changes
    if changes.get("code_diff") and update_type == "safe":
        console.print("  Code changes:")
        diff_data = changes["code_diff"]

        # Show a summary of changes
        if diff_data["added_lines"] or diff_data["removed_lines"]:
            console.print(
                f"    📝 {len(diff_data['added_lines'])} additions, {len(diff_data['removed_lines'])} deletions"
            )

        # Show key diff blocks (limit to avoid overwhelming output)
        for i, block in enumerate(diff_data["context_blocks"][:MAX_CONTEXT_BLOCKS]):  # Show max blocks
            console.print(f"    ┌─ Change {i + 1}:")
            for line in block[:10]:  # Show max 10 lines per block
                if line.startswith("+"):
                    console.print(f"    │ [green]{line}[/green]")
                elif line.startswith("-"):
                    console.print(f"    │ [red]{line}[/red]")
                elif line.startswith("@@"):
                    console.print(f"    │ [cyan]{line}[/cyan]")
                else:
                    console.print(f"    │ {line}")

        if len(diff_data["context_blocks"]) > MAX_CONTEXT_BLOCKS:
            console.print(f"    └─ ... and {len(diff_data['context_blocks']) - MAX_CONTEXT_BLOCKS} more changes")

    if update_type == "breaking":
        console.print("  ⚠️  This is a breaking change that may affect connected components")

    response = Prompt.ask("? Update this component?", choices=["y", "n"], default="n")
    return response.lower() in ["y", "yes"]


async def apply_component_update(flow_data: dict, component: dict, all_types_dict: dict) -> None:
    """Apply a component update to the flow data."""
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
                continue

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

            break


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
    output: str | None = typer.Option(None, "--output", "-o", help="Output file path (defaults to input file)"),
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
            flow_path, update=update, force=force, interactive=interactive, output=output
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

    if outdated_count == 0:
        console.print("[green]✅ All components are up to date![/green]")
        return

    if not update and not applied_updates:
        # Just showing status
        console.print(f"\n[yellow]⚠️  Found {outdated_count} outdated component(s)[/yellow]")
        console.print("Run with --update to apply safe updates automatically")
        console.print("Run with --update --force to apply all updates including breaking changes")

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

        output_path = output or flow_path
        console.print(f"Updated flow saved to: [bold]{output_path}[/bold]")

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


# Sync wrapper for the CLI
def check_command_sync(
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
    output: str | None = typer.Option(None, "--output", "-o", help="Output file path (defaults to input file)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show verbose output"),  # noqa: FBT003
) -> None:
    """Check a flow for outdated components and optionally update them."""
    run_until_complete(
        check_command(flow_path, update=update, force=force, interactive=interactive, output=output, verbose=verbose)
    )
