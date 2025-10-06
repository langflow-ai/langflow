# Tool Connection Guide for Genesis Agent YAML

## Problem
Components like `KnowledgeHubSearchComponent` and `MCPToolsComponent` were showing as disconnected tools in AI Studio instead of connecting to agent tools input.

## Root Cause
Missing `provides` declarations in YAML that tell the converter how to connect tool components to agents.

## Solution: Proper YAML Structure

### ✅ Correct YAML Structure
```yaml
components:
  # Tool component with provides declaration
  knowledge-search:
    type: "genesis:knowledge_hub_search"
    config:
      search_query: "search term"
      selected_hubs: ["hub1", "hub2"]
    provides:
      - useAs: "tools"        # Connect to tools input
        in: "agent-id"        # Target agent component ID

  mcp-service:
    type: "genesis:mcp_tool"
    config:
      mcp_server: "server_name"
      tool: "tool_name"
    provides:
      - useAs: "tools"        # Connect to tools input
        in: "agent-id"        # Target agent component ID

  # Agent that receives tools
  agent-id:
    type: "genesis:agent"
    config:
      system_prompt: "Agent instructions"
```

### ❌ Incorrect YAML Structure (Missing provides)
```yaml
components:
  knowledge-search:
    type: "genesis:knowledge_hub_search"
    config:
      search_query: "search term"
    # Missing provides declaration!

  agent-id:
    type: "genesis:agent"
    config:
      system_prompt: "Agent instructions"
```

## What Provides Does

1. **`useAs: "tools"`** - Tells converter this component should connect to a `tools` input field
2. **`in: "component-id"`** - Specifies which component to connect to
3. **Automatic Edge Creation** - Converter creates edges from `component_as_tool` output to target's `tools` input

## Supported Tool Types

All these component types can be used as tools with proper `provides` declarations:

- `genesis:knowledge_hub_search` → `KnowledgeHubSearch`
- `genesis:mcp_tool` → `MCPTools`
- `genesis:calculator` → `Calculator`
- `genesis:document_intelligence` → `AzureDocumentIntelligenceComponent`
- Any component with `component_as_tool` output

## Edge Generation Logic

With `provides` declarations, the converter:

1. Detects component as tool (has `provides` with `useAs: "tools"`)
2. Adds `component_as_tool` output with `"Tool"` type and `"Toolset"` display name
3. Creates edge from tool's `component_as_tool` to agent's `tools` input
4. Sets proper handle types for connection

## Testing

After adding `provides` declarations:
- Tools should show "Toolset" output handles
- Agent should show "Tools" input handle
- Edges should automatically connect tools to agent
- Components should display proper names (not "Generic component")

## Examples

See these example files:
- `eoc-check-agent.yaml` - EOC agent with knowledge search and MCP tools
- `comprehensive-agent-example.yaml` - Multiple tool types with agent