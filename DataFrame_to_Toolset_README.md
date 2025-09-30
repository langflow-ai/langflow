# DataFrame to Toolset Component

A powerful Langflow component that converts each row of a DataFrame into a callable tool/action within a toolset. This allows you to dynamically create tools from structured data that can be used by LLM agents.

## Overview

The DataFrame to Toolset component takes a DataFrame where each row represents a tool, and converts it into a collection of callable tools. Each tool can be executed by an agent to retrieve specific information or perform actions.

## Components

### 1. DataFrameToToolsetComponent

**Purpose**: Converts DataFrame rows into callable tools
**Inputs**:
- `dataframe`: DataFrame where each row becomes a tool/action
- `tool_name_column`: Name of the column containing the names for each tool/action (string input)
- `tool_output_column`: Name of the column containing the content/response for each tool/action (string input)

**Outputs**:
- `tools`: List of callable tools created from the DataFrame
- `message`: Human-readable summary of created tools

### 2. DataFrameToolsetExecutor (Optional)

**Purpose**: Execute a specific tool from the toolset
**Inputs**:
- `tools`: Tools from the DataFrame to Toolset component
- `tool_to_execute`: Select which tool to execute

## Use Cases

### 1. **API Documentation as Tools**
Convert API documentation into callable tools that agents can use:

```python
api_data = [
    {
        "endpoint": "GET /users",
        "description": "Retrieves list of all users with pagination support",
        "example": '{"users": [...], "total": 150, "page": 1}'
    },
    {
        "endpoint": "POST /users", 
        "description": "Creates a new user account",
        "example": '{"user_id": "12345", "status": "created"}'
    }
]
```

### 2. **Knowledge Base as Tools**
Turn FAQ or knowledge base entries into tools:

```python
knowledge_data = [
    {
        "question": "How to reset password",
        "answer": "Click 'Forgot Password' on login page, enter email, check inbox for reset link",
        "category": "account"
    },
    {
        "question": "How to upgrade plan",
        "answer": "Go to Settings > Billing > Choose Plan > Confirm payment details",
        "category": "billing"  
    }
]
```

### 3. **Database Query Results as Tools**
Convert database query results into callable information:

```python
company_data = [
    {
        "department": "Engineering",
        "info": "50 employees, 3 teams: Backend, Frontend, DevOps. Led by John Smith.",
        "budget": "$2M"
    },
    {
        "department": "Marketing", 
        "info": "12 employees, 2 teams: Digital, Content. Led by Jane Doe.",
        "budget": "$500K"
    }
]
```

### 4. **Configuration Data as Tools**
Make configuration settings accessible as tools:

```python
config_data = [
    {
        "setting": "Database Connection",
        "details": "PostgreSQL cluster on AWS RDS, 3 read replicas, auto-failover enabled",
        "status": "healthy"
    },
    {
        "setting": "Cache Configuration",
        "details": "Redis cluster with 6 nodes, 32GB memory, TTL: 1 hour",
        "status": "optimal"
    }
]
```

## How It Works

1. **Input Processing**: The component reads your DataFrame and identifies the specified columns
2. **Tool Creation**: For each row, it creates a `StructuredTool` with:
   - **Name**: Sanitized version of the action name (alphanumeric + underscore/dash only)
   - **Description**: Auto-generated based on the original name and content preview
   - **Function**: Returns the content from the content column when called
   - **Metadata**: Stores original name, display name, and content preview

3. **Tool Execution**: When an agent calls a tool, it returns the associated content from the DataFrame

## Example Usage in Langflow

### Step 1: Prepare Your Data
Create a DataFrame with your data:
```python
import pandas as pd
from langflow.schema.dataframe import DataFrame

data = [
    {"action": "Get Weather", "response": "Sunny, 75°F"},
    {"action": "Check Stock", "response": "AAPL: $190.25 (+2.5%)"},
    {"action": "System Status", "response": "All systems operational"}
]

df = DataFrame(data)
```

### Step 2: Configure the Component
- Connect your DataFrame to the `dataframe` input
- Type "action" in the `tool_name_column` field
- Type "response" in the `tool_output_column` field
### Step 3: Connect to an Agent
- Connect the `tools` output to an agent's tools input
- The agent can now call any of these tools by name

### Step 4: Agent Interaction
The agent can now make calls like:
- "Get_Weather" → Returns "Sunny, 75°F"
- "Check_Stock" → Returns "AAPL: $190.25 (+2.5%)"
- "System_Status" → Returns "All systems operational"

## Advanced Features

### Tool Name Sanitization
Tool names are automatically sanitized to meet requirements:
- Only alphanumeric characters, underscores, and dashes allowed
- Invalid characters replaced with underscores
- Names starting with numbers get "tool_" prefix

### Metadata Storage
Each tool stores rich metadata:
- `display_name`: Original, human-readable name
- `original_name`: Exactly as provided in DataFrame
- `content_preview`: First 200 characters of content
- `display_description`: Auto-generated description

### Error Handling
- Invalid DataFrames are caught with clear error messages
- Missing columns are detected and reported
- Tool execution errors are handled gracefully

## Integration with Agents

The created tools work seamlessly with Langflow agents:

```python
# Agent can call tools like this:
agent_prompt = """
You have access to these tools. Use them to answer user questions:
- Get_Weather: Get current weather information
- Check_Stock: Get current stock prices  
- System_Status: Check system operational status

User question: What's the weather like?
"""
# Agent will automatically call Get_Weather tool
```

## Benefits

1. **Dynamic Tool Creation**: Create tools from any structured data
2. **No Code Required**: Visual interface in Langflow
3. **Flexible Data Sources**: Works with any DataFrame format
4. **Agent Integration**: Seamlessly works with LLM agents
5. **Scalable**: Handle hundreds of tools efficiently
6. **Metadata Rich**: Preserves context and descriptions

## Best Practices

1. **Clear Action Names**: Use descriptive, unique names for better agent understanding
2. **Concise Content**: Keep content focused and informative
3. **Consistent Format**: Maintain consistent data structure across rows
4. **Meaningful Categories**: Add category columns for better organization
5. **Regular Updates**: Keep DataFrame content current and relevant

## Limitations

- Tool names must follow alphanumeric + underscore/dash pattern
- Currently returns static content (future versions could support dynamic parameters)
- Large DataFrames may impact performance with many tools

## Future Enhancements

- **Parameterized Tools**: Allow tools to accept input parameters
- **Dynamic Content**: Enable runtime content generation
- **Tool Categories**: Group tools by categories for better organization
- **Caching**: Cache tool results for improved performance
- **Validation**: Add content validation and formatting options