# Response for Issue #9003: MCP Component Tool Mode Build Error

Hi @purleaf,

Thank you for reporting this issue with the MCP Tools component in tool mode. I've analyzed the error and can confirm this is a **bug in the component's tool mode implementation**.

## Root Cause Confirmed

The `KeyError: None` occurs at line 454 in `mcp_component.py`:
```python
exec_tool = self._tool_cache[self.tool]
```

When tool mode is enabled:
1. The component hides the tool selection dropdown (as intended for dynamic selection)
2. However, `self.tool` remains `None` or empty
3. The `build_output` method still tries to access `self._tool_cache[self.tool]`
4. This causes the KeyError when it attempts `self._tool_cache[None]`

## Why This Happens

The code at line 447 checks `if self.tool != "":` but doesn't properly handle the `None` case that occurs in tool mode. This is a **design gap** - the component expects tool mode to work with agent-driven dynamic selection, but the build process still attempts to execute even without a selected tool.

## Immediate Workaround

Since you confirmed the component works with `tool_mode=false`, the best immediate solution is:

1. **Disable tool mode** in the MCP Tools component
2. Select your desired tool from the dropdown (e.g., "ss_text")
3. The component should build successfully

## Understanding Tool Mode

Tool mode is designed for **agent-driven workflows** where:
- An agent component dynamically selects which tool to use based on context
- The tool selection happens at runtime during agent reasoning
- Direct component execution (clicking "Build") isn't the intended use case

## For Your Use Case

Based on your MCP server tool declaration, if you need to:
- **Execute a specific tool directly**: Keep tool mode disabled
- **Use with an agent**: Enable tool mode but ensure the MCP Tools component is connected to an agent that will provide the tool selection

## Next Steps

This is a legitimate bug where the component should either:
1. Skip build execution in tool mode when no tool is selected
2. Provide better error messaging about tool mode requirements
3. Handle the `None` case gracefully

The issue affects the current MCP Connection component (not the deprecated MCP Tools SSE/STDIO versions in `/deactivated/`).

Would you like guidance on setting up the agent-driven workflow, or does disabling tool mode solve your immediate needs?

Best regards,  
Langflow Support