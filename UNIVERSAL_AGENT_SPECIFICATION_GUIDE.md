# Universal Agent Specification Guide

## Overview

This guide provides comprehensive information for creating agent specifications that work seamlessly in both **AI Studio API mode** and **local MVP mode** without validation errors.

## Problem Analysis

The original issue was a **format incompatibility** between two validation systems:

- **API Mode**: Requires `components` as an **array/list** format with `id` fields
- **Local MVP Mode**: Originally expected `components` as a **dictionary** format

## Solution Summary

✅ **Fixed MVP orchestrator** to handle both formats universally
✅ **Created universal specification** using API-compatible list format
✅ **Validated functionality** in both modes

## Universal Specification Format

### Required Structure

```yaml
# REQUIRED: Standard metadata fields
id: urn:agent:genesis:autonomize.ai:agent-name:1.0.0
name: Agent Name
fullyQualifiedName: genesis.autonomize.ai.agent_name
description: Agent description
domain: autonomize.ai
subDomain: category
version: 1.0.0
environment: development|production
agentOwner: owner@autonomize.ai
agentOwnerDisplayName: Owner Team
email: owner@autonomize.ai
status: ACTIVE
kind: Single Agent
agentGoal: Clear description of what the agent does
targetUser: internal|external
valueGeneration: ProcessAutomation
interactionMode: RequestResponse
runMode: RealTime
agencyLevel: ReflexiveAgent
toolsUse: true|false
learningCapability: None

# REQUIRED: Components in LIST format
components:
- id: component-id-1
  type: genesis:chat_input
  name: Component Name
  description: Component description
  config: {}
  provides:
  - useAs: input
    in: target-component-id
    description: Connection description

- id: component-id-2
  type: genesis:agent
  name: Agent Component
  description: AI agent component
  config:
    system_prompt: "System message"
    temperature: 0.7
    max_tokens: 500
  provides:
  - useAs: response
    in: output-component-id
    description: Response connection

- id: component-id-3
  type: genesis:chat_output
  name: Output Component
  description: Output component
  config: {}
```

## Component Format Requirements

### ✅ Correct Format (List/Array)

```yaml
components:
- id: user-input
  type: genesis:chat_input
  name: User Input
  description: Input component
  # ... rest of component config

- id: agent
  type: genesis:agent
  name: AI Agent
  description: Agent component
  # ... rest of component config
```

### ❌ Incorrect Format (Dictionary)

```yaml
components:
  user-input:
    type: genesis:chat_input
    description: Input component
    # ... rest of component config

  agent:
    type: genesis:agent
    description: Agent component
    # ... rest of component config
```

## Supported Component Types

### Core Components (Always Safe)
- `genesis:chat_input` - User input
- `genesis:chat_output` - Agent output
- `genesis:agent` - AI agent/assistant
- `genesis:model` - LLM model

### Tool Components (Require Tool Configuration)
- `genesis:api_request` - API calls
- Healthcare connectors (when available)

## Tool Configuration Requirements

### When Using Tools

If your specification uses tools (`toolsUse: true`), ensure:

1. **API Request Headers** - Use array format:
```yaml
config:
  method: GET
  url: https://api.example.com
  headers:
  - name: Authorization
    value: Bearer ${API_KEY}
  - name: Content-Type
    value: application/json
```

2. **Tool Capability Marking** - Mark components as tool-capable if needed

## Validation Testing Protocol

### Test Your Specification

```bash
# Test API mode validation
ai-studio workflow validate your-agent.yaml

# Test local MVP mode validation
ai-studio workflow validate your-agent.yaml --local

# Test conversion (local mode)
ai-studio workflow create -t your-agent.yaml --local
```

### Expected Results

✅ **Both modes should pass:**
```
Status: ✅ VALID
✅ Validation passed!
```

✅ **Conversion should succeed:**
```
Flow Statistics:
  Nodes: X
  Edges: Y
  Node Types: [list of types]
```

## Common Validation Errors

### 1. Wrong Component Format
**Error:** `Wrong data type at components: ... is not valid under any of the given schemas`
**Solution:** Use list format with `id` fields

### 2. Header Format Error
**Error:** `headers: ... is not of type 'array'`
**Solution:** Use array format for headers in API requests

### 3. Tool Capability Error
**Error:** `Component used as tool but not marked as tool-capable`
**Solution:** Set `toolsUse: true` and proper tool configuration

## Architecture Fixes Applied

### MVP Orchestrator Updates

Fixed the following methods to handle both component formats:
- `_quick_validate_specification()` - Validation logic
- `_validate_mvp_requirements()` - MVP-specific checks
- `_add_mvp_metadata()` - Metadata processing

### Genesis Converter Updates

Fixed the following areas:
- Component processing loop in `convert()`
- Edge generation in `_generate_edges()`
- Healthcare compliance checking

### Edge Generator Updates

Updated to handle normalized component format for edge generation.

## Best Practices

### 1. Specification Design
- ✅ Use list format for components
- ✅ Include all required metadata fields
- ✅ Use clear, descriptive component IDs
- ✅ Include proper `provides` relationships

### 2. Component Configuration
- ✅ Keep configurations simple and well-tested
- ✅ Avoid experimental component types
- ✅ Use standard connection patterns

### 3. Tool Usage
- ✅ Only use tools when necessary
- ✅ Properly configure tool headers
- ✅ Set `toolsUse` flag correctly

### 4. Testing Strategy
- ✅ Test both validation modes
- ✅ Test conversion functionality
- ✅ Verify edge generation works

## Example: Working Simple Agent

See `/Users/jagveersingh/Developer/studio/ai-studio/universal_simple_agent.yaml` for a complete example that:

✅ Passes API validation completely
✅ Passes local MVP validation
✅ Successfully converts to Langflow JSON
✅ Uses minimal, safe components

## Component Compatibility Matrix

| Component Type | API Mode | Local MVP | Notes |
|---------------|----------|-----------|-------|
| `genesis:chat_input` | ✅ | ✅ | Always safe |
| `genesis:chat_output` | ✅ | ✅ | Always safe |
| `genesis:agent` | ✅ | ✅ | Core component |
| `genesis:model` | ✅ | ✅ | Core component |
| `genesis:api_request` | ⚠️ | ✅ | Requires proper headers format |
| Healthcare connectors | ⚠️ | ✅ | May have specific requirements |

## Troubleshooting

### Validation Fails in API Mode
1. Check component format (use list, not dict)
2. Verify all required metadata fields present
3. Check header format for API requests
4. Ensure proper tool configuration

### Validation Fails in Local MVP Mode
1. Should now work with fixes applied
2. Check component structure and types
3. Verify all components have required fields

### Conversion Fails
1. Ensure validation passes first
2. Check component provides/relationships
3. Verify component types are valid
4. Check for circular dependencies

## Summary

With the architectural fixes in place, you can now create agent specifications that work universally across both validation systems by:

1. **Using the list format** for components
2. **Including all required metadata** fields
3. **Following proper configuration** patterns
4. **Testing in both modes** before deployment

The MVP orchestrator now handles both formats seamlessly, making the system truly universal and eliminating the format incompatibility issue.