# Workflow CLI for AI Studio

This directory contains the Workflow CLI integration for AI Studio, providing unified `ai-studio workflow` commands for managing agent specifications, templates, and workflows. This replaces the previous Genesis CLI with enhanced functionality.

## Overview

The Workflow CLI enables developers to:
- Create flows from YAML specifications
- Validate specifications with detailed feedback
- **Export existing flows to Genesis specifications** *(NEW)*
- List and manage flows, templates, and components
- Configure AI Studio connections
- Browse and use healthcare agent templates

## Migration Notice

**⚠️ IMPORTANT**: The CLI commands have been updated:
- `ai-studio genesis` → `ai-studio workflow` *(recommended)*
- Genesis commands still work with deprecation warnings for backward compatibility

## Installation

The Genesis CLI is automatically available when AI Studio is installed. No additional installation required.

## Quick Start

```bash
# Show available commands
ai-studio workflow --help

# Create a flow from template
ai-studio workflow create -t healthcare/medication-extractor

# Validate a specification
ai-studio workflow validate my-spec.yaml

# Export existing flow to specification (NEW)
ai-studio workflow export flow.json -o my-spec.yaml

# List available templates
ai-studio workflow templates

# Configure AI Studio connection
ai-studio workflow config show
```

### Legacy Commands (Deprecated)
```bash
# Still supported with deprecation warnings
ai-studio genesis create -t template.yaml    # Use 'workflow create' instead
ai-studio genesis validate spec.yaml        # Use 'workflow validate' instead
ai-studio genesis export flow.json          # Use 'workflow export' instead
```

## Command Reference

### `ai-studio workflow create`

Create flows from YAML specifications.

```bash
# Create from local file
ai-studio workflow create -t template.yaml

# Create from library template
ai-studio workflow create -t healthcare/eligibility-checker

# Use variables and tweaks
ai-studio workflow create -t template.yaml \
  --var api_key=test \
  --var temperature=0.7 \
  --tweak agent.model=gpt-4

# Validate only
ai-studio workflow create -t template.yaml --validate-only

# Save to file instead of creating in AI Studio
ai-studio workflow create -t template.yaml -o flow.json
```

**Options:**
- `-t, --template`: Path to YAML specification or library template name
- `-n, --name`: Flow name (defaults to template name)
- `-p, --project`: Project name to create flow in
- `-f, --folder`: Folder ID to create flow in
- `-o, --output`: Save flow to file instead of creating in AI Studio
- `-v, --validate-only`: Only validate without creating
- `--var`: Set runtime variables (format: key=value)
- `--var-file`: Load variables from JSON/YAML file
- `--tweak`: Apply component tweaks (format: component.field=value)

### `ai-studio workflow export` *(NEW)*

Export existing AI Studio flows to Genesis specifications.

```bash
# Export single flow from file
ai-studio workflow export flow.json -o specification.yaml

# Export with custom metadata
ai-studio workflow export flow.json \
  --name "Custom Agent" \
  --domain healthcare \
  --output-file custom-spec.yaml

# Export preserving variables from original flow
ai-studio workflow export flow.json \
  --preserve-vars \
  --include-metadata \
  --output-file enhanced-spec.yaml

# Export multiple flows (batch)
ai-studio workflow export *.json --output-dir ./exported-specs/

# Validate before export
ai-studio workflow export flow.json --validate-only
```

**Options:**
- `-o, --output-file`: Output specification file path
- `--output-dir`: Output directory for batch export
- `--name`: Override specification name
- `--domain`: Override specification domain
- `--preserve-vars`: Preserve variables from flow
- `--include-metadata`: Include extended metadata
- `--validate-only`: Validate export readiness without exporting
- `--format`: Output format (yaml, json)

### `ai-studio workflow validate`

Validate YAML specifications with comprehensive feedback.

```bash
# Basic validation
ai-studio workflow validate template.yaml

# Detailed validation with semantic analysis
ai-studio workflow validate template.yaml --detailed

# Quick validation for real-time feedback
ai-studio workflow validate template.yaml --quick

# JSON output for integration
ai-studio workflow validate template.yaml --format json
```

**Options:**
- `-d, --detailed`: Perform detailed semantic validation
- `-q, --quick`: Quick validation optimized for speed
- `-f, --format`: Output format (table, report, json)

### `ai-studio workflow list`

List workflow resources.

```bash
# List flows
ai-studio workflow list flows

# List templates with category filter
ai-studio workflow list templates --category healthcare

# List components with search
ai-studio workflow list components --search agent

# List folders
ai-studio workflow list folders
```

**Options:**
- `--filter`: Filter results by name or pattern
- `--project`: Filter flows by project name
- `--category`: Filter templates by category
- `--format`: Output format (table, json, simple)
- `--limit`: Maximum number of results

### `ai-studio workflow config`

Manage CLI configuration.

```bash
# Show current configuration
ai-studio workflow config show

# Set configuration values
ai-studio workflow config set ai_studio_url http://localhost:7860
ai-studio workflow config set ai_studio_api_key your-api-key

# Test connection
ai-studio workflow config test

# Import from genesis-agent-cli
ai-studio workflow config import

# Reset to defaults
ai-studio workflow config reset
```

**Configuration Keys:**
- `ai_studio_url`: AI Studio URL
- `ai_studio_api_key`: API key for authentication
- `default_project`: Default project for flows
- `default_folder`: Default folder for flows
- `templates_path`: Custom templates directory
- `verbose`: Enable verbose output

### `ai-studio workflow components`

Discover and explore workflow components.

```bash
# List all components
ai-studio workflow components

# Search for specific components
ai-studio workflow components --search healthcare

# Show only tool components
ai-studio workflow components --tools-only

# Get detailed component info
ai-studio workflow components --info genesis:agent

# Filter by category
ai-studio workflow components --category healthcare
```

### `ai-studio workflow templates`

Browse and manage specification templates.

```bash
# List all templates
ai-studio workflow templates

# Filter by category
ai-studio workflow templates --category healthcare

# Search templates
ai-studio workflow templates --search medication

# Show template details
ai-studio workflow templates --show healthcare/medication-extractor

# List local custom templates
ai-studio workflow templates --local
```

## Configuration

Workflow CLI configuration is stored in `~/.ai-studio/workflow-config.yaml` (replaces `genesis-config.yaml`):

```yaml
ai_studio:
  url: http://localhost:7860
  api_key: your-api-key
default_project: Healthcare Agents
default_folder: genesis-flows
templates_path: /path/to/custom/templates
verbose: false
```

### Environment Variables

Configuration can be overridden with environment variables:

- `AI_STUDIO_URL` / `LANGFLOW_URL`: AI Studio URL
- `AI_STUDIO_API_KEY` / `LANGFLOW_API_KEY`: API key
- `WORKFLOW_DEFAULT_PROJECT`: Default project (was GENESIS_DEFAULT_PROJECT)
- `WORKFLOW_DEFAULT_FOLDER`: Default folder (was GENESIS_DEFAULT_FOLDER)
- `WORKFLOW_TEMPLATES_PATH`: Custom templates path (was GENESIS_TEMPLATES_PATH)
- `WORKFLOW_VERBOSE`: Enable verbose output (was GENESIS_VERBOSE)

## Template System

### Variable Substitution

Templates support variable substitution using two formats:

1. **Runtime variables**: `{variable_name}`
2. **Environment variables**: `${ENV_VAR}`

Example template:
```yaml
name: {agent_name}
config:
  api_key: ${API_KEY}
  temperature: {temperature}
```

Usage:
```bash
ai-studio workflow create -t template.yaml \
  --var agent_name="My Agent" \
  --var temperature=0.7
```

### Component Tweaks

Modify component configurations at runtime:

```bash
ai-studio workflow create -t template.yaml \
  --tweak agent.config.temperature=0.8 \
  --tweak agent.config.model=gpt-4
```

### Template Directory Structure

Built-in templates are organized by category:

```
templates/workflow/
├── healthcare/
│   ├── single-agents/
│   │   ├── medication-extractor.yaml
│   │   ├── eligibility-checker.yaml
│   │   └── clinical-processing-agent.yaml
│   ├── multi-agent/
│   │   └── benefit-check-flow.yaml
│   └── specialized/
│       └── accumulator-check-agent.yaml
├── examples/
│   └── simple-chat-agent.yaml
└── metadata.yaml
```

## Healthcare Templates

The Workflow CLI includes a comprehensive library of healthcare agent templates:

### Single Agent Templates
- **Medication Extractor**: Extract medications with RxNorm codes
- **Eligibility Checker**: Verify insurance eligibility
- **Clinical Processing Agent**: Process clinical documentation
- **Extraction Agent**: General purpose clinical data extraction

### Specialized Healthcare Agents
- **Accumulator Check Agent**: Check benefit accumulators
- **Prior Authorization Agent**: Automate PA workflows
- **EOC Validator**: End of care validation

### Multi-Agent Workflows
- **Benefit Check Flow**: Comprehensive benefit verification
- **Prior Authorization Workflow**: Multi-step PA coordination

## Integration with AI Studio

The Workflow CLI is tightly integrated with AI Studio backend:

- **SpecService**: Leverages existing spec validation and conversion
- **FlowConverter**: Uses enhanced spec-to-flow conversion
- **FlowToSpecConverter**: *(NEW)* Enables reverse conversion from flows to specs
- **ComponentMapper**: Accesses bidirectional type mappings
- **API Endpoints**: Communicates through `/api/v1/spec/` endpoints (including new export endpoints)
- **Database Integration**: Flows are saved to AI Studio database

## Migration from genesis-agent-cli

### Automatic Configuration Import

```bash
ai-studio workflow config import
```

This will automatically detect and import configuration from:
- `~/.genesis-agent.yaml`
- `./.genesis-agent.yaml`
- `~/.ai-studio/genesis-config.yaml` *(legacy)*
- `./.env` files

### Template Compatibility

All existing genesis-agent-cli templates work without modification:
- Same YAML specification format
- Same variable substitution syntax
- Same component tweaks system
- Backward compatible with all features

### Command Mapping

| genesis-agent-cli | ai-studio workflow | ai-studio genesis *(deprecated)* |
|------------------|-------------------|----------------------------------|
| `genesis-agent create` | `ai-studio workflow create` | `ai-studio genesis create` |
| `genesis-agent validate` | `ai-studio workflow validate` | `ai-studio genesis validate` |
| `genesis-agent list` | `ai-studio workflow list` | `ai-studio genesis list` |
| `genesis-agent config` | `ai-studio workflow config` | `ai-studio genesis config` |
| `genesis-agent components` | `ai-studio workflow components` | `ai-studio genesis components` |
| *(NEW)* | `ai-studio workflow export` | `ai-studio genesis export` |

## Error Handling

The Workflow CLI provides comprehensive error handling:

- **Connection errors**: Clear messages when AI Studio is unreachable
- **Validation errors**: Detailed feedback with suggestions
- **Template errors**: Variable and syntax validation
- **Configuration errors**: Helpful configuration guidance

## Debugging

Enable verbose output for debugging:

```bash
# Via command line (workflow commands)
ai-studio workflow create -t template.yaml --debug

# Via configuration
ai-studio workflow config set verbose true

# Via environment variable
export WORKFLOW_VERBOSE=true

# Legacy commands still work with deprecation warnings
ai-studio genesis create -t template.yaml --debug  # DEPRECATED
export GENESIS_VERBOSE=true  # DEPRECATED
```

## Development

### Running Tests

```bash
# Run all Workflow CLI tests
pytest src/backend/base/langflow/cli/workflow/tests/

# Run specific test file
pytest src/backend/base/langflow/cli/workflow/tests/test_workflow_export.py

# Run with coverage
pytest --cov=langflow.cli.workflow src/backend/base/langflow/cli/workflow/tests/

# Legacy Genesis CLI tests (still available)
pytest src/backend/base/langflow/cli/genesis/tests/
```

### Adding New Commands

1. Create command module in `commands/`
2. Import and register in `main.py`
3. Add tests in `tests/`
4. Update documentation

### Adding New Templates

1. Create YAML template in appropriate category
2. Update `metadata.yaml`
3. Test template validation
4. Add to documentation

## Troubleshooting

### Common Issues

**"Workflow CLI not available"**
- Ensure AI Studio is properly installed
- Check Python environment and dependencies
- Legacy: Genesis CLI commands still work with deprecation warnings

**"Cannot connect to AI Studio"**
- Verify AI Studio is running
- Check URL configuration: `ai-studio workflow config show`
- Test connection: `ai-studio workflow config test`
- Legacy: `ai-studio genesis config show` still works

**"Template not found"**
- Check template path: `ai-studio workflow templates`
- Verify custom templates path if using local templates
- Legacy: `ai-studio genesis templates` still works

**"Export failed"** *(NEW)*
- Verify flow JSON format is valid
- Check if flow contains supported component types
- Use `--validate-only` to check export compatibility
- Review error messages for unsupported components

**"Validation failed"**
- Check YAML syntax
- Verify component types exist
- Review error messages for specific issues

### Getting Help

- Use `--help` on any command for detailed usage
- Check AI Studio logs for backend errors
- Enable debug mode for verbose output

## Contributing

Contributions are welcome! Please:

1. Follow existing code patterns
2. Add comprehensive tests
3. Update documentation
4. Ensure backward compatibility