# Template Search Utilities

This module provides utilities for searching and loading Langflow template data with configurable field selection.

## Location

```
src/backend/base/langflow/agentic/utils/
├── __init__.py
├── template_search.py       # Main module
├── test_template_search.py  # Demo/test script
└── README.md               # This file
```

## Usage

### Basic Import

```python
from langflow.agentic.utils import (
    search_templates,
    get_template_by_id,
    get_all_tags,
    get_templates_count,
)
```

### Functions

#### `search_templates()`

Search and filter templates with customizable field selection.

**Parameters:**
- `search_query` (str | None): Search term to filter by name or description (case-insensitive)
- `fields` (list[str] | None): List of fields to return. If None, returns all fields
- `tags` (list[str] | None): Filter by tags (returns templates with ANY matching tag)
- `starter_projects_path` (str | Path | None): Custom path to starter_projects directory

**Returns:** List of dictionaries with selected fields

**Example:**
```python
# Get basic info for all templates
templates = search_templates(fields=["id", "name", "description"])

# Search for "agent" templates
agent_templates = search_templates(
    search_query="agent",
    fields=["id", "name", "description", "tags"]
)

# Filter by tags
rag_templates = search_templates(
    tags=["rag", "chatbots"],
    fields=["name", "description"]
)
```

#### `get_template_by_id()`

Retrieve a specific template by its UUID.

**Parameters:**
- `template_id` (str): UUID of the template
- `fields` (list[str] | None): Fields to return
- `starter_projects_path` (str | Path | None): Custom path to starter_projects

**Returns:** Dictionary with template data, or None if not found

**Example:**
```python
template = get_template_by_id(
    "0dbee653-41ae-4e51-af2e-55757fb24be3",
    fields=["name", "description", "tags"]
)
```

#### `get_all_tags()`

Get all unique tags across all templates.

**Parameters:**
- `starter_projects_path` (str | Path | None): Custom path to starter_projects

**Returns:** Sorted list of unique tag names

**Example:**
```python
tags = get_all_tags()
# ['agent', 'agents', 'assistants', 'chatbots', ...]
```

#### `get_templates_count()`

Get total count of available templates.

**Parameters:**
- `starter_projects_path` (str | Path | None): Custom path to starter_projects

**Returns:** Integer count of templates

**Example:**
```python
count = get_templates_count()
# 33
```

## Available Template Fields

Common fields in template data:
- `id` - UUID string
- `name` - Template name
- `description` - Template description
- `tags` - List of tag strings
- `is_component` - Boolean
- `last_tested_version` - Version string
- `endpoint_name` - Optional endpoint name
- `data` - Full template data (nodes, edges, etc.)
- `icon` - Icon identifier
- `icon_bg_color` - Background color
- `gradient` - Gradient definition
- `updated_at` - ISO timestamp

## Running the Demo

```bash
cd /Users/edwin.jose/Documents/GitHub/langflow/src/backend/base
python3 -m langflow.agentic.utils.test_template_search
```

## Use Cases for Agentic Features

This utility is designed to support agentic interactions where you might need to:

1. **Search templates dynamically** - Agent can search for relevant templates based on user requests
2. **Recommend templates** - Match user requirements with appropriate templates
3. **Filter by capabilities** - Find templates by tags (agents, rag, chatbots, etc.)
4. **Provide template metadata** - Return minimal info without loading full template data
5. **Template discovery** - Help users explore available templates

## Integration Example

```python
from langflow.agentic.utils import search_templates

# In your agentic interaction handler:
def handle_user_request(user_input: str):
    # Extract intent from user input
    if "rag" in user_input.lower():
        # Find relevant templates
        templates = search_templates(
            search_query="rag",
            fields=["id", "name", "description"],
            tags=["rag"]
        )

        # Present options to user
        return {
            "message": f"Found {len(templates)} RAG templates",
            "templates": templates
        }
```

## Notes

- The module automatically resolves the path to `initial_setup/starter_projects/`
- All search operations are case-insensitive
- Tag filtering uses OR logic (matches ANY provided tag)
- Invalid JSON files are skipped with warnings
- Field selection reduces data transfer for large template datasets
