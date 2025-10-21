# Genesis CLI for AI Studio

This directory contains the Genesis Agent CLI integration for AI Studio, providing unified `ai-studio genesis` commands for managing agent specifications, templates, and workflows.

## Overview

The Genesis CLI enables developers to:
- Create flows from YAML specifications
- Validate specifications with detailed feedback
- List and manage flows, templates, and components
- Configure AI Studio connections
- Browse and use healthcare agent templates

## Installation

The Genesis CLI is automatically available when AI Studio is installed. No additional installation required.

## Quick Start

```bash
# Show available commands
ai-studio genesis --help

# Create a flow from template
ai-studio genesis create -t healthcare/medication-extractor

# Validate a specification
ai-studio genesis validate my-spec.yaml

# List available templates
ai-studio genesis templates

# Configure AI Studio connection
ai-studio genesis config show
```

## Command Reference

### `ai-studio genesis create`

Create flows from YAML specifications.

```bash
# Create from local file
ai-studio genesis create -t template.yaml

# Create from library template
ai-studio genesis create -t healthcare/eligibility-checker

# Use variables and tweaks
ai-studio genesis create -t template.yaml \
  --var api_key=test \
  --var temperature=0.7 \
  --tweak agent.model=gpt-4

# Validate only
ai-studio genesis create -t template.yaml --validate-only

# Save to file instead of creating in AI Studio
ai-studio genesis create -t template.yaml -o flow.json
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

### `ai-studio genesis validate`

Validate YAML specifications with comprehensive feedback.

```bash
# Basic validation
ai-studio genesis validate template.yaml

# Detailed validation with semantic analysis
ai-studio genesis validate template.yaml --detailed

# Quick validation for real-time feedback
ai-studio genesis validate template.yaml --quick

# JSON output for integration
ai-studio genesis validate template.yaml --format json
```

**Options:**
- `-d, --detailed`: Perform detailed semantic validation
- `-q, --quick`: Quick validation optimized for speed
- `-f, --format`: Output format (table, report, json)

### `ai-studio genesis list`

List Genesis resources.

```bash
# List flows
ai-studio genesis list flows

# List templates with category filter
ai-studio genesis list templates --category healthcare

# List components with search
ai-studio genesis list components --search agent

# List folders
ai-studio genesis list folders
```

**Options:**
- `--filter`: Filter results by name or pattern
- `--project`: Filter flows by project name
- `--category`: Filter templates by category
- `--format`: Output format (table, json, simple)
- `--limit`: Maximum number of results

### `ai-studio genesis config`

Manage CLI configuration.

```bash
# Show current configuration
ai-studio genesis config show

# Set configuration values
ai-studio genesis config set ai_studio_url http://localhost:7860
ai-studio genesis config set ai_studio_api_key your-api-key

# Test connection
ai-studio genesis config test

# Import from genesis-agent-cli
ai-studio genesis config import

# Reset to defaults
ai-studio genesis config reset
```

**Configuration Keys:**
- `ai_studio_url`: AI Studio URL
- `ai_studio_api_key`: API key for authentication
- `default_project`: Default project for flows
- `default_folder`: Default folder for flows
- `templates_path`: Custom templates directory
- `verbose`: Enable verbose output

### `ai-studio genesis components`

Discover and explore Genesis components.

```bash
# List all components
ai-studio genesis components

# Search for specific components
ai-studio genesis components --search healthcare

# Show only tool components
ai-studio genesis components --tools-only

# Get detailed component info
ai-studio genesis components --info genesis:agent

# Filter by category
ai-studio genesis components --category healthcare
```

### `ai-studio genesis templates`

Browse and manage specification templates.

```bash
# List all templates
ai-studio genesis templates

# Filter by category
ai-studio genesis templates --category healthcare

# Search templates
ai-studio genesis templates --search medication

# Show template details
ai-studio genesis templates --show healthcare/medication-extractor

# List local custom templates
ai-studio genesis templates --local
```

## Configuration

Genesis CLI configuration is stored in `~/.ai-studio/genesis-config.yaml`:

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
ai-studio genesis create -t template.yaml \
  --var agent_name="My Agent" \
  --var temperature=0.7
```

### Component Tweaks

Modify component configurations at runtime:

```bash
ai-studio genesis create -t template.yaml \
  --tweak agent.config.temperature=0.8 \
  --tweak agent.config.model=gpt-4
```

### Template Directory Structure

Built-in templates are organized by category:

```
templates/genesis/
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

The Genesis CLI includes a comprehensive library of healthcare agent templates:

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

The Genesis CLI is tightly integrated with AI Studio backend:

- **SpecService**: Leverages existing spec validation and conversion
- **FlowConverter**: Uses enhanced spec-to-flow conversion
- **ComponentMapper**: Accesses Genesis type mappings
- **API Endpoints**: Communicates through `/api/v1/spec/` endpoints
- **Database Integration**: Flows are saved to AI Studio database

## Migration from genesis-agent-cli

### Automatic Configuration Import

```bash
ai-studio genesis config import
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

| genesis-agent-cli | ai-studio genesis |
|------------------|-------------------|
| `genesis-agent create` | `ai-studio genesis create` |
| `genesis-agent validate` | `ai-studio genesis validate` |
| `genesis-agent list` | `ai-studio genesis list` |
| `genesis-agent config` | `ai-studio genesis config` |
| `genesis-agent components` | `ai-studio genesis components` |

## Error Handling

The Genesis CLI provides comprehensive error handling:

- **Connection errors**: Clear messages when AI Studio is unreachable
- **Validation errors**: Detailed feedback with suggestions
- **Template errors**: Variable and syntax validation
- **Configuration errors**: Helpful configuration guidance

## Debugging

Enable verbose output for debugging:

```bash
# Via command line
ai-studio genesis create -t template.yaml --debug

# Via configuration
ai-studio genesis config set verbose true

# Via environment variable
export GENESIS_VERBOSE=true
```

## Development

### Running Tests

```bash
# Run all Genesis CLI tests
pytest src/backend/base/langflow/cli/genesis/tests/

# Run specific test file
pytest src/backend/base/langflow/cli/genesis/tests/test_template_manager.py

# Run with coverage
pytest --cov=langflow.cli.genesis src/backend/base/langflow/cli/genesis/tests/
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

**"Genesis CLI not available"**
- Ensure AI Studio is properly installed
- Check Python environment and dependencies

**"Cannot connect to AI Studio"**
- Verify AI Studio is running
- Check URL configuration: `ai-studio genesis config show`
- Test connection: `ai-studio genesis config test`

**"Template not found"**
- Check template path: `ai-studio genesis templates`
- Verify custom templates path if using local templates

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