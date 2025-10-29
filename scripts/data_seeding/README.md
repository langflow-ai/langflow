# Agent Data Seeding Scripts

This module provides a comprehensive system for seeding AI Studio with agent data from TSV files. It creates both flow entries and published flow entries for the agents.

## Features

- **TSV Parsing**: Robust parsing of tab-separated agent data files
- **Data Validation**: Comprehensive validation of agent data and business rules
- **Flow Generation**: Automatic generation of flow templates based on agent domain
- **Batch Processing**: Efficient batch processing with error recovery
- **Database Seeding**: Creates flows and optionally publishes them
- **Error Handling**: Detailed error reporting and validation summaries

## Project Structure

```
scripts/data_seeding/
├── __init__.py          # Module exports
├── main.py              # Main CLI entry point
├── models.py            # Data models and enums
├── tsv_parser.py        # TSV file parsing
├── templates.py         # Flow template generation
├── seeding_service.py   # Database seeding service
├── validation.py        # Data validation utilities
└── README.md           # This file

scripts/
└── seed_agents.py      # Convenience runner script
```

## Usage

### Basic Usage

```bash
# Dry run to validate data
python scripts/seed_agents.py --tsv-file agents.tsv --user-id <uuid> --dry-run

# Seed agents with publishing
python scripts/seed_agents.py --tsv-file agents.tsv --user-id <uuid>

# Seed without publishing
python scripts/seed_agents.py --tsv-file agents.tsv --user-id <uuid> --no-publish
```

### Advanced Options

```bash
# Custom batch size and database URL
python scripts/seed_agents.py \
  --tsv-file agents.tsv \
  --user-id <uuid> \
  --batch-size 5 \
  --database-url postgresql+asyncpg://user:pass@host:port/db

# Continue on validation errors
python scripts/seed_agents.py \
  --tsv-file agents.tsv \
  --user-id <uuid> \
  --continue-on-error

# Validate TSV structure only
python scripts/seed_agents.py --tsv-file agents.tsv --validate-only
```

### Module Usage

```python
from scripts.data_seeding import (
    TSVParser,
    AgentSeedingService,
    AgentDataValidator
)

# Parse TSV file
parser = TSVParser("agents.tsv")
agents_data = parser.parse_agents()

# Validate data
validator = AgentDataValidator(session)
validation_results = await validator.validate_batch(agents_data)

# Seed database
service = AgentSeedingService(session, user_id)
result = await service.seed_agents_from_data(agents_data)
```

## TSV File Format

The TSV file must contain the following columns:

| Column | Type | Description |
|--------|------|-------------|
| Domain Area | string | Agent domain (e.g., "Patient Experience") |
| Agent Name | string | Unique name for the agent |
| Description | string | Detailed description of the agent |
| Applicable to Payers | Y/N | Whether agent applies to payers |
| Applicable to Payviders | Y/N | Whether agent applies to payviders |
| Applicable to Providers | Y/N | Whether agent applies to providers |
| Connectors | string | Available connectors |
| Goals | string | Agent goals and objectives |
| KPIs | string | Key performance indicators |
| Tools | string | Available tools and capabilities |

### Example TSV Row

```tsv
Patient Experience	Patient Portal Assistant	AI assistant for patient portal support	Y	N	N	Epic, Cerner	Improve patient engagement	Patient satisfaction score	Chat, Forms, Scheduling
```

## Domain Areas

Supported domain areas and their associated colors:

- **Patient Experience** - Blue (#3B82F6)
- **Provider Enablement** - Green (#10B981)
- **Utilization Management** - Amber (#F59E0B)
- **Care Management** - Red (#EF4444)
- **Risk Adjustment** - Purple (#8B5CF6)
- **Claims Operations** - Cyan (#06B6D4)
- **Clinical Operations** - Lime (#84CC16)
- **Population Health** - Pink (#EC4899)

## Database Tables

The seeding process creates entries in two main tables:

### Flow Table
- Contains the main flow definition with nodes and edges
- Includes agent metadata (name, description, tags, etc.)
- Has a unique endpoint name for API access

### Published Flow Table
- Contains published version of the flow
- Clones the original flow for marketplace display
- Includes publication metadata and status

## Error Handling

The system provides comprehensive error handling:

- **Validation Errors**: Field-level validation with detailed messages
- **Database Errors**: Transaction rollback with savepoints
- **Batch Processing**: Continue processing other agents on individual failures
- **Duplicate Detection**: Checks for existing flows and endpoint names

## CLI Options

```
--tsv-file PATH           Path to TSV file (required)
--user-id UUID            User ID for created flows (required unless --validate-only)
--database-url URL        Database connection URL
--batch-size N            Batch size for processing (default: 10)
--dry-run                 Validate without making changes
--no-publish              Don't create published flows
--validate-only           Only validate file structure
--verbose                 Enable verbose logging
--continue-on-error       Continue despite validation errors
```

## Example Output

```
2023-10-27 14:30:00 - INFO - Parsing TSV file: agents.tsv
2023-10-27 14:30:01 - INFO - Successfully parsed 113 agents
2023-10-27 14:30:01 - INFO - Processing 113 valid agents
2023-10-27 14:30:01 - INFO - Starting to seed 113 agents (dry_run=False)
2023-10-27 14:30:01 - INFO - Processing batch 1: agents 1-10
2023-10-27 14:30:02 - INFO - Batch completed: 10 successful, 0 failed
...
2023-10-27 14:30:15 - INFO - Seeding completed: 113/113 successful (100.0%) in 14.2s

=== SEEDING RESULTS ===
Total processed: 113
Successful: 113
Failed: 0
Success rate: 100.0%
Duration: 14.2 seconds

Successfully created 113 flows
```