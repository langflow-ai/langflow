"""Template management and variable substitution for Genesis CLI."""

import os
import re
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
import json


class TemplateManager:
    """Manages Genesis specification templates with variable substitution."""

    def __init__(self, templates_base_path: Optional[Path] = None):
        if templates_base_path:
            self.templates_path = templates_base_path
        else:
            # Default to built-in templates
            self.templates_path = Path(__file__).parent.parent.parent.parent / "templates" / "genesis"

    def list_templates(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """List available templates with metadata."""
        templates = []

        if not self.templates_path.exists():
            return templates

        # Load metadata if available
        metadata_file = self.templates_path / "metadata.yaml"
        metadata = {}
        if metadata_file.exists():
            with open(metadata_file, 'r') as f:
                metadata = yaml.safe_load(f) or {}

        # Find all YAML template files
        for yaml_file in self.templates_path.rglob("*.yaml"):
            if yaml_file.name == "metadata.yaml":
                continue

            try:
                with open(yaml_file, 'r') as f:
                    template_dict = yaml.safe_load(f)

                if not template_dict or 'name' not in template_dict:
                    continue

                # Get relative path from templates base
                relative_path = yaml_file.relative_to(self.templates_path)
                template_category = str(relative_path.parent).replace(os.sep, '/')

                # Filter by category if specified
                if category and category.lower() not in template_category.lower():
                    continue

                template_info = {
                    'file_path': str(relative_path),
                    'full_path': str(yaml_file),
                    'name': template_dict.get('name', ''),
                    'description': template_dict.get('description', ''),
                    'kind': template_dict.get('kind', ''),
                    'category': template_category,
                    'domain': template_dict.get('domain', ''),
                    'version': template_dict.get('version', ''),
                    'agent_goal': template_dict.get('agentGoal', ''),
                    'components_count': len(template_dict.get('components', []))
                }

                templates.append(template_info)

            except Exception as e:
                # Skip invalid template files
                continue

        return sorted(templates, key=lambda t: t['file_path'])

    def load_template(self, template_path: str) -> str:
        """Load template content from file path."""
        # Try relative to templates base first
        full_path = self.templates_path / template_path
        if not full_path.exists():
            # Try as absolute path
            full_path = Path(template_path)

        if not full_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")

        with open(full_path, 'r') as f:
            return f.read()

    def apply_variable_substitution(self, template_content: str,
                                  variables: Optional[Dict[str, Any]] = None,
                                  tweaks: Optional[Dict[str, Any]] = None) -> str:
        """Apply variable substitution to template content."""
        if not variables and not tweaks:
            return template_content

        result = template_content

        # Apply variable substitution
        if variables:
            result = self._substitute_variables(result, variables)

        # Apply component tweaks
        if tweaks:
            result = self._apply_tweaks(result, tweaks)

        return result

    def _substitute_variables(self, content: str, variables: Dict[str, Any]) -> str:
        """Substitute variables in the format {variable_name} and ${ENV_VAR}."""
        result = content

        # Substitute {variable_name} format
        for var_name, var_value in variables.items():
            # Convert value to string representation
            if isinstance(var_value, (dict, list)):
                var_str = json.dumps(var_value)
            elif isinstance(var_value, bool):
                var_str = str(var_value).lower()
            else:
                var_str = str(var_value)

            # Replace {variable_name}
            result = result.replace(f"{{{var_name}}}", var_str)

        # Substitute ${ENV_VAR} format from environment
        env_pattern = re.compile(r'\$\{([^}]+)\}')
        matches = env_pattern.findall(result)

        for env_var in matches:
            env_value = os.getenv(env_var, '')
            result = result.replace(f"${{{env_var}}}", env_value)

        return result

    def _apply_tweaks(self, content: str, tweaks: Dict[str, Any]) -> str:
        """Apply component configuration tweaks."""
        try:
            # Parse YAML content
            spec_dict = yaml.safe_load(content)

            if not spec_dict or 'components' not in spec_dict:
                return content

            # Apply tweaks to components
            for component in spec_dict['components']:
                component_id = component.get('id', '')

                for tweak_key, tweak_value in tweaks.items():
                    if '.' not in tweak_key:
                        continue

                    # Parse tweak key (component_id.field or component_id.config.field)
                    parts = tweak_key.split('.')
                    if parts[0] != component_id:
                        continue

                    # Apply the tweak
                    target = component
                    for part in parts[1:-1]:
                        if part not in target:
                            target[part] = {}
                        target = target[part]

                    # Set the final value
                    final_key = parts[-1]
                    target[final_key] = tweak_value

            # Convert back to YAML
            return yaml.dump(spec_dict, default_flow_style=False, sort_keys=False)

        except Exception as e:
            # If tweaks fail, return original content
            return content

    def validate_template(self, template_content: str) -> Dict[str, Any]:
        """Validate template content structure."""
        try:
            spec_dict = yaml.safe_load(template_content)

            if not spec_dict:
                return {"valid": False, "errors": ["Empty template"]}

            errors = []
            warnings = []

            # Check required fields
            required_fields = ['name', 'description', 'components']
            for field in required_fields:
                if field not in spec_dict:
                    errors.append(f"Missing required field: {field}")

            # Check components structure
            components = spec_dict.get('components', [])
            if not isinstance(components, list):
                errors.append("Components must be a list")
            elif len(components) == 0:
                warnings.append("No components defined")

            # Validate each component
            for i, component in enumerate(components):
                if not isinstance(component, dict):
                    errors.append(f"Component {i} must be a dictionary")
                    continue

                if 'id' not in component:
                    errors.append(f"Component {i} missing required 'id' field")

                if 'type' not in component:
                    errors.append(f"Component {i} missing required 'type' field")

            return {
                "valid": len(errors) == 0,
                "errors": errors,
                "warnings": warnings
            }

        except yaml.YAMLError as e:
            return {"valid": False, "errors": [f"Invalid YAML: {e}"]}
        except Exception as e:
            return {"valid": False, "errors": [f"Validation error: {e}"]}

    def create_template_from_spec(self, spec_content: str, template_path: str,
                                metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Create a new template from specification content."""
        try:
            # Ensure template directory exists
            full_path = self.templates_path / template_path
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Add metadata as comments if provided
            if metadata:
                # Add metadata header
                header_lines = [
                    "# Genesis Agent Template",
                    f"# Generated: {metadata.get('created_at', '')}",
                    f"# Category: {metadata.get('category', '')}",
                    f"# Author: {metadata.get('author', '')}",
                    ""
                ]
                spec_content = "\n".join(header_lines) + spec_content

            # Write template file
            with open(full_path, 'w') as f:
                f.write(spec_content)

            return True

        except Exception as e:
            return False

    def get_template_variables(self, template_content: str) -> List[str]:
        """Extract variable placeholders from template content."""
        variables = set()

        # Find {variable_name} patterns
        brace_pattern = re.compile(r'\{([^}]+)\}')
        variables.update(brace_pattern.findall(template_content))

        # Find ${ENV_VAR} patterns
        env_pattern = re.compile(r'\$\{([^}]+)\}')
        variables.update(env_pattern.findall(template_content))

        return sorted(list(variables))

    def find_template_by_name(self, name: str) -> Optional[str]:
        """Find template file path by name."""
        templates = self.list_templates()

        for template in templates:
            if template['name'].lower() == name.lower():
                return template['file_path']

        # Try fuzzy matching
        name_lower = name.lower()
        for template in templates:
            if name_lower in template['name'].lower():
                return template['file_path']

        return None