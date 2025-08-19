"""Project export utilities.

This module provides utilities for exporting Langflow projects as ZIP archives
with extracted component code and environment variable templates.
"""

import re

# Constants
FILENAME_SANITIZE_PATTERN = r"[^a-zA-Z0-9_-]"
MIN_ENV_VAR_LENGTH = 3


def is_valid_node(node: dict) -> bool:
    """Check if a node is valid and has the required structure."""
    return isinstance(node, dict) and "data" in node and "node" in node["data"] and "template" in node["data"]["node"]


def extract_code_from_node(node: dict) -> str | None:
    """Extract code content from a node's template."""
    template = node["data"]["node"]["template"]
    if "code" not in template:
        return None

    code_field = template["code"]
    if not isinstance(code_field, dict) or "value" not in code_field:
        return None

    code_content = code_field["value"]
    if not code_content or not isinstance(code_content, str):
        return None

    return code_content


def generate_code_filename(node: dict) -> str:
    """Generate a sanitized filename for the component code."""
    node_data = node["data"]
    component_type = node_data.get("type", "component")
    component_id = node.get("id", "unknown")

    # Sanitize filename components
    safe_component_type = re.sub(r"\W", "_", component_type)
    safe_component_id = re.sub(FILENAME_SANITIZE_PATTERN, "_", component_id)

    return f"{safe_component_type}_{safe_component_id}.py"


def create_code_file_content(node: dict, flow_name: str, code_content: str) -> str:
    """Create the complete code file content with docstring."""
    node_data = node["data"]
    component_type = node_data.get("type", "component")
    component_id = node.get("id", "unknown")

    docstring = f'"""Component: {component_type}\nID: {component_id}\nFlow: {flow_name}\n"""\n\n'
    return docstring + code_content


def extract_component_code_from_flow(flow_data: dict, flow_name: str) -> dict[str, str]:
    """Extract code from components in a flow and return a mapping of filenames to code content."""
    code_files = {}

    if "data" not in flow_data or "nodes" not in flow_data["data"]:
        return code_files

    nodes = flow_data["data"]["nodes"]

    for node in nodes:
        if not is_valid_node(node):
            continue

        code_content = extract_code_from_node(node)
        if code_content:
            filename = generate_code_filename(node)
            file_content = create_code_file_content(node, flow_name, code_content)
            code_files[filename] = file_content

    return code_files


def is_valid_env_var_name(name: str) -> bool:
    """Check if a string is a valid environment variable name.

    Valid env var names should:
    - Contain only uppercase letters, digits, and underscores
    - Not start with a digit
    - Be reasonably formatted as an environment variable
    """
    # Check if it matches the pattern for env vars
    if not re.match(r"^[A-Z_][A-Z0-9_]*$", name):
        return False

    # Additional heuristics - should look like an env var
    # Examples: API_KEY, OPENAI_API_KEY, DATABASE_URL
    if len(name) < MIN_ENV_VAR_LENGTH:
        return False

    # Should contain at least one underscore or be all caps
    return "_" in name or name.isupper()


def extract_env_variables_from_flow(flow_data: dict) -> dict[str, dict]:
    """Extract environment variables from a flow's components.

    Args:
        flow_data: Flow data containing nodes with templates

    Returns:
        Dict mapping variable names to their metadata:
        {
            "OPENAI_API_KEY": {
                "valid": True,
                "components": ["OpenAI", "ChatOpenAI"],
                "description": "OpenAI API key for authentication"
            },
            "My API Key": {
                "valid": False,
                "components": ["SomeComponent"],
                "description": "Invalid env var name - contains spaces and mixed case"
            }
        }
    """
    env_vars = {}

    if "data" not in flow_data or "nodes" not in flow_data["data"]:
        return env_vars

    nodes = flow_data["data"]["nodes"]

    for node in nodes:
        if not is_valid_node(node):
            continue

        node_data = node["data"]
        component_type = node_data.get("type", "Unknown")
        template = node_data["node"]["template"]

        # Look for fields with load_from_db=True
        for field_name, field_data in template.items():
            if not isinstance(field_data, dict):
                continue

            load_from_db = field_data.get("load_from_db", False)
            if not load_from_db:
                continue

            # Get the value which should be the variable name
            var_name = field_data.get("value", "")
            if not var_name or not isinstance(var_name, str):
                continue

            # Initialize or update the env var entry
            if var_name not in env_vars:
                env_vars[var_name] = {
                    "valid": is_valid_env_var_name(var_name),
                    "components": [],
                    "field_name": field_name,
                }

            if component_type not in env_vars[var_name]["components"]:
                env_vars[var_name]["components"].append(component_type)

    return env_vars


def generate_env_example_content(all_env_vars: dict[str, dict]) -> str:
    """Generate .env.example file content.

    Args:
        all_env_vars: Dictionary of environment variables from all flows

    Returns:
        String content for .env.example file
    """
    if not all_env_vars:
        return """# .env.example - Environment Variables Template
# Copy this file to .env and fill in your actual values

# No environment variables detected in this project
"""

    lines = [
        "# .env.example - Environment Variables Template",
        "# Copy this file to .env and fill in your actual values",
        "# Generated from Langflow project export",
        "",
    ]

    # Separate valid and invalid env vars
    valid_vars = {k: v for k, v in all_env_vars.items() if v["valid"]}
    invalid_vars = {k: v for k, v in all_env_vars.items() if not v["valid"]}

    # Add valid environment variables
    if valid_vars:
        lines.append("# Environment Variables")
        lines.append("# Set these values according to your deployment needs")
        lines.append("")

        for var_name, var_info in sorted(valid_vars.items()):
            components = ", ".join(var_info["components"])
            field_name = var_info.get("field_name", "unknown")

            lines.append(f"# Used by: {components} (field: {field_name})")
            lines.append(f"{var_name}=your_value_here")
            lines.append("")

    # Add invalid environment variables as comments
    if invalid_vars:
        lines.append("# Invalid Environment Variable Names")
        lines.append("# These variables have invalid names and need to be renamed in your components")
        lines.append("# Valid env var names should use UPPERCASE_WITH_UNDERSCORES format")
        lines.append("")

        for var_name, var_info in sorted(invalid_vars.items()):
            components = ", ".join(var_info["components"])
            field_name = var_info.get("field_name", "unknown")

            lines.append(f"# INVALID: '{var_name}' - Used by: {components} (field: {field_name})")
            lines.append("# Suggested fix: Rename to a valid format like: MY_API_KEY")
            lines.append(f"# {var_name.upper().replace(' ', '_').replace('-', '_')}=your_value_here")
            lines.append("")

    return "\n".join(lines)


def generate_export_readme(
    project_name: str,
    version: str,
    langflow_version: str,
    export_timestamp: str,
    flows_count: int,
    code_files_count: int,
) -> str:
    """Generate README content for project export.

    Args:
        project_name: Name of the project
        version: Export format version (e.g., "1.0")
        langflow_version: Version of Langflow used
        export_timestamp: ISO timestamp of export
        flows_count: Number of flows in the export
        code_files_count: Number of code files extracted

    Returns:
        str: README content as markdown
    """
    return f"""# {project_name}

This export contains the complete project structure with extracted component code.

## Structure

- `project.json` - Project metadata and complete flow definitions
- `components/` - Extracted Python code from custom components, organized by flow
- `.env.example` - Template for environment variables used by components

## Export Info

- Export format version: {version}
- Langflow version: {langflow_version}
- Exported at: {export_timestamp}
- Total flows: {flows_count}
- Code files extracted: {code_files_count}

## Usage

The extracted Python files in the `components/` directory can be used for:
- Static analysis with tools like mypy, ruff, pylint
- Code review and auditing
- Understanding component logic outside of Langflow

Each component file includes metadata in its docstring indicating the original component type, ID, and parent flow.
"""
