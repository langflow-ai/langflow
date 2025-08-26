# Response for Issue #9437: Gemini with MCP Tools Returns Error 400

Hi @omerabr,

Thank you for reporting this issue with Gemini models and MCP tools. This is a **confirmed compatibility problem** between Google's Gemini API requirements and Langflow's MCP tool message handling.

## Root Cause Identified

The error you're encountering:
```
GenerateContentRequest.contents[X].parts[0].function_response.name: Name cannot be empty
```

This occurs due to **missing tool message handling** in Langflow's message conversion system:

### 1. Missing Tool Message Type Handling
Located in `src/backend/base/langflow/schema/message.py:156-170`:
- The `from_lc_message` method only handles "human", "ai", and "system" message types
- **No handling for "tool" message types** which carry function responses
- This causes function response names to be empty when sent to Gemini

### 2. Gemini vs OpenAI Differences
- **OpenAI**: More permissive, accepts function responses without strict name validation
- **Gemini**: Requires explicit `function_response.name` field to be populated
- **Validation**: Gemini's API strictly validates and rejects empty name fields

### 3. MCP Tool Result Formatting
The MCP component returns raw tool results without proper message wrapping:
- Tool results are not converted to proper `ToolMessage` objects
- Missing the required `name` field that Gemini expects

## Why It's Intermittent

The sporadic nature occurs because:
- Some tool calls may include name fields by chance
- Error only triggers when multiple function responses accumulate without names
- OpenAI works fine because it doesn't enforce this validation

## Immediate Workarounds

**Option 1: Use OpenAI Models** (Recommended)
- Switch to OpenAI models which don't have this strict validation
- Works seamlessly with current MCP implementation

**Option 2: Disable Tool Mode**
- Set `Tool Model Enabled = false` in your Agent component
- This prevents MCP tools from being passed to Gemini

**Option 3: Wait for Fix**
- Monitor issue #9437 for updates
- Related issue #9309 also tracks Gemini MCP tool registration problems

## Technical Details

**Files requiring modification:**
- `src/backend/base/langflow/schema/message.py` - Add tool message handling
- `src/backend/base/langflow/base/mcp/util.py` - Format tool responses properly
- Message conversion needs to populate `function_response.name` for Gemini compatibility

## Expected Resolution

This requires updates to:
1. Extend message conversion to handle tool message types
2. Populate function response names for Gemini compatibility
3. Add LLM-specific formatting for different providers

## Related Issues

- Issue #9437 (this issue) - Gemini MCP error 400
- Issue #9309 - Gemini API not registering MCP tools

Thank you for the detailed error report - it clearly shows the validation failures from Gemini's API.

Best regards,
Langflow Support

---

## For Developers

The fix requires:
1. Adding "tool" message type handling in `from_lc_message` method
2. Ensuring `function_response.name` is populated for all tool responses
3. Creating LLM-specific message formatters for Gemini vs OpenAI