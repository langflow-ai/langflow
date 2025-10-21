# Workflow CLI for AI Studio

This directory contains the Workflow CLI for AI Studio, providing unified `ai-studio workflow` commands for managing agent specifications, templates, and workflows.

## Overview

The Workflow CLI enables developers to:
- Create flows from YAML specifications
- Validate specifications with detailed feedback
- Export existing flows to specifications
- List and manage flows, templates, and components
- Configure AI Studio connections
- Browse and use healthcare agent templates

## Installation

The Workflow CLI is automatically available when AI Studio is installed. No additional installation required.

## Quick Start

```bash
# Show available commands
ai-studio workflow --help

# Create a flow from template
ai-studio workflow create -t healthcare/medication-extractor

# Validate a specification
ai-studio workflow validate my-spec.yaml

# Export a flow to specification
ai-studio workflow export flow.json

# List available templates
ai-studio workflow templates

# Configure AI Studio connection
ai-studio workflow config show
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

### `ai-studio workflow export`

Export existing flows to YAML specifications.

```bash
# Export a flow by file
ai-studio workflow export flow.json

# Export with custom options
ai-studio workflow export flow.json --format yaml --output spec.yaml

# Include metadata in export
ai-studio workflow export flow.json --include-metadata

# Preserve variables in export
ai-studio workflow export flow.json --preserve-vars

# Export with agent goal extraction
ai-studio workflow export flow.json --agent-goal "Process healthcare data"
```

**Options:**
- `-f, --format`: Output format (yaml, json)
- `-o, --output`: Output file path
- `--include-metadata`: Include flow metadata
- `--preserve-vars`: Preserve variable placeholders
- `--agent-goal`: Specify agent goal for the specification

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

# Import from legacy genesis-agent-cli
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
ai-studio workflow components --info Agent

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

# Create new template from flow
ai-studio workflow templates --create-from-flow flow-id
```

## Configuration

Workflow CLI configuration is stored in `~/.ai-studio/genesis-config.yaml`:

```yaml
ai_studio:
  url: http://localhost:7860
  api_key: your-api-key
default_project: Healthcare Agents
default_folder: workflow-flows
templates_path: /path/to/custom/templates
verbose: false
```

### Environment Variables

Configuration can be overridden with environment variables:

- `AI_STUDIO_URL` / `LANGFLOW_URL`: AI Studio URL
- `AI_STUDIO_API_KEY` / `LANGFLOW_API_KEY`: API key
- `GENESIS_DEFAULT_PROJECT`: Default project
- `GENESIS_DEFAULT_FOLDER`: Default folder
- `GENESIS_TEMPLATES_PATH`: Custom templates path
- `GENESIS_VERBOSE`: Enable verbose output

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
templates/
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
- **ComponentMapper**: Accesses component type mappings
- **API Endpoints**: Communicates through `/api/v1/spec/` endpoints
- **Database Integration**: Flows are saved to AI Studio database

## Migration from genesis-agent-cli

### Automatic Configuration Import

```bash
ai-studio workflow config import
```

This will automatically detect and import configuration from:
- `~/.genesis-agent.yaml`
- `./.genesis-agent.yaml`
- `./.env` files

### Template Compatibility

All existing genesis-agent-cli templates work without modification:
- Same YAML specification format
- Same variable substitution syntax
- Same component tweaks system
- Backward compatible with all features

### Command Mapping

| genesis-agent-cli | ai-studio workflow |
|------------------|-------------------|
| `genesis-agent create` | `ai-studio workflow create` |
| `genesis-agent validate` | `ai-studio workflow validate` |
| `genesis-agent list` | `ai-studio workflow list` |
| `genesis-agent config` | `ai-studio workflow config` |
| `genesis-agent components` | `ai-studio workflow components` |
| N/A | `ai-studio workflow export` |

## Error Handling

The Workflow CLI provides comprehensive error handling:

- **Connection errors**: Clear messages when AI Studio is unreachable
- **Validation errors**: Detailed feedback with suggestions
- **Template errors**: Variable and syntax validation
- **Configuration errors**: Helpful configuration guidance

## Debugging

Enable verbose output for debugging:

```bash
# Via command line
ai-studio workflow create -t template.yaml --debug

# Via configuration
ai-studio workflow config set verbose true

# Via environment variable
export GENESIS_VERBOSE=true
```

## Development

### Running Tests

```bash
# Run all Workflow CLI tests
pytest tests/unit/cli/workflow/

# Run specific test file
pytest tests/unit/cli/workflow/commands/test_create.py

# Run with coverage
pytest --cov=langflow.cli.workflow tests/unit/cli/workflow/
```

### Test Coverage

The Workflow CLI has comprehensive test coverage with 272 unit tests:

- **Commands**: 7 test modules covering all CLI commands
- **Configuration**: Complete config management testing
- **Utilities**: API client, output formatting, template management
- **Integration**: Main CLI entry point and command registration

### Adding New Commands

1. Create command module in `commands/`
2. Import and register in `main.py`
3. Add tests in `/tests/unit/cli/workflow/commands/`
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

**"Cannot connect to AI Studio"**
- Verify AI Studio is running
- Check URL configuration: `ai-studio workflow config show`
- Test connection: `ai-studio workflow config test`

**"Template not found"**
- Check template path: `ai-studio workflow templates`
- Verify custom templates path if using local templates

**"Validation failed"**
- Check YAML syntax
- Verify component types exist
- Review error messages for specific issues

**"Export failed"**
- Ensure flow file exists and is valid JSON
- Check AI Studio connectivity for flow validation
- Verify output directory permissions

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

## Architecture

The Workflow CLI is organized into several modules:

```
src/backend/base/langflow/cli/workflow/
├── commands/          # CLI command implementations
│   ├── create.py     # Flow creation from templates
│   ├── validate.py   # Specification validation
│   ├── export.py     # Flow to spec export
│   ├── list_cmd.py   # Resource listing
│   ├── config.py     # Configuration management
│   ├── components.py # Component discovery
│   └── templates.py  # Template management
├── config/           # Configuration management
│   └── manager.py    # ConfigManager class
├── utils/            # Utility modules
│   ├── api_client.py # AI Studio API client
│   ├── output.py     # Output formatting
│   └── template_manager.py # Template operations
└── main.py           # Main CLI entry point
```

This modular architecture ensures maintainability and testability while providing a clean separation of concerns.