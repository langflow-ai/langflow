# Conversation Memory Tool Attachment

## Where ConversationMemoryTool is Attached

The `ConversationMemoryTool` is attached directly to the **Main Orchestrator Agent** as one of its tools.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                 MAIN ORCHESTRATOR AGENT                 │
│                                                          │
│  Tools Available:                                       │
│  ┌────────────────────────────────────────────────┐    │
│  │ • Requirements Analyst (agent as tool)         │    │
│  │ • Intent Classifier (agent as tool)            │    │
│  │ • Research Agent (agent as tool)               │    │
│  │ • Pattern Matcher (agent as tool)              │    │
│  │ • Spec Builder (agent as tool)                 │    │
│  │ • Validation Agent (agent as tool)             │    │
│  │ ⭐ CONVERSATION MEMORY (direct tool)           │    │
│  └────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

## Why Attached to Orchestrator?

1. **Central State Management**: The orchestrator needs to maintain state across all phases
2. **Cross-Phase Context**: Information from Phase 1 is needed in Phase 2 and 3
3. **Decision Tracking**: All design decisions are stored centrally
4. **Session Persistence**: Maintains context throughout the entire conversation

## How It's Used

### Phase 1: Understanding & Research
```python
# Orchestrator stores requirements after extraction
orchestrator.use_tool("conversation_memory", {
    "operation": "store",
    "key": "requirements",
    "value": requirements_data
})
```

### Phase 2: Planning & Design
```python
# Retrieve requirements for planning
requirements = orchestrator.use_tool("conversation_memory", {
    "operation": "retrieve",
    "key": "requirements"
})

# Store design decisions
orchestrator.use_tool("conversation_memory", {
    "operation": "store",
    "key": "design_decisions",
    "value": design_data
})
```

### Phase 3: Implementation
```python
# Retrieve all context for spec building
context = orchestrator.use_tool("conversation_memory", {
    "operation": "retrieve",
    "key": "_summary"  # Get all stored data
})
```

## Configuration in YAML

```yaml
components:
  # Memory Tool Definition
  - id: conversation-memory
    type: genesis:conversation_memory_tool
    name: Conversation Memory
    provides:
      - useAs: tool
        in: orchestrator  # ← Attached here
        description: Session state management

  # Orchestrator Configuration
  - id: orchestrator
    type: genesis:agent
    name: AI Builder Orchestrator
    config:
      tools:
        - requirements_analyst
        - intent_classifier
        - research_agent
        - pattern_matcher
        - spec_builder
        - validation_agent
        - conversation_memory  # ← Listed as available tool
```

## Memory Operations

The orchestrator can perform these operations:

| Operation | Purpose | Example |
|-----------|---------|---------|
| `store` | Save new data | Store extracted requirements |
| `retrieve` | Get stored data | Retrieve requirements for planning |
| `update` | Modify existing data | Update design decisions |
| `clear` | Remove data | Clear session after completion |

## Data Flow Example

```
User Input
    ↓
Orchestrator
    ↓
Requirements Analyst (extracts requirements)
    ↓
Orchestrator stores in Memory: {"requirements": {...}}
    ↓
Intent Classifier (classifies intent)
    ↓
Orchestrator stores in Memory: {"intent": {...}}
    ↓
[Later phases retrieve this stored context]
    ↓
Spec Builder (retrieves all context from Memory)
    ↓
Generates specification using full context
```

## Benefits of This Attachment

1. **Centralized Control**: Orchestrator manages all state
2. **No Duplication**: Single memory instance for entire session
3. **Clear Ownership**: Orchestrator owns conversation flow
4. **Simplified Access**: Sub-agents don't need direct memory access
5. **Consistent State**: All decisions tracked in one place

## Alternative Approaches (Not Used)

We could have attached memory to:
- ❌ Each sub-agent (too complex, duplicate state)
- ❌ As a separate component (harder to coordinate)
- ❌ External service (unnecessary complexity)

The current approach (attached to orchestrator) is the simplest and most effective.