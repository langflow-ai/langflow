# AI Agent Builder System

A sophisticated multi-agent system for building and validating AI agent specifications in Langflow/AI Studio.

## 🎯 Overview

The AI Agent Builder System uses a multi-agent architecture where specialized agents collaborate to guide users through creating validated agent specifications. Instead of building many custom tool components, we leverage the existing `genesis:agent` component configured with specialized prompts.

## 🏗️ Architecture

```
Main Orchestrator Agent
    ├── Requirements Analyst Agent (as tool)
    ├── Intent Classifier Agent (as tool)
    ├── Research Agent (as tool)
    ├── Pattern Matcher Agent (as tool)
    ├── Specification Builder Agent (as tool)
    ├── Validation Agent (as tool)
    └── Actual Tools:
        ├── SpecificationSearchTool (file search)
        ├── SpecValidatorTool (API validation)
        └── AgentStateManager (state management)
```

## 📦 Components

### Tool Components (Actual Python Classes)

Only 3 custom tool components are needed:

1. **SpecificationSearchTool** (`specification_search.py`)
   - Searches existing agent specifications in the library
   - Uses fuzzy matching and relevance scoring
   - No LLM required - pure file search

2. **SpecValidatorTool** (`spec_validator.py`)
   - Validates YAML specifications against schema
   - Uses SpecService when available
   - Falls back to built-in validation

3. **AgentStateManager** (`agent_state_manager.py`)
   - Manages workflow state and context
   - Stores requirements and decisions
   - Session-based memory management

### Agent Components (Standard genesis:agent)

All specialized agents use the standard `genesis:agent` component with custom prompts:

1. **Orchestrator Agent** - Main coordinator
2. **Requirements Analyst** - Extracts structured requirements
3. **Intent Classifier** - Classifies agent type and complexity
4. **Research Agent** - Finds similar agents and patterns
5. **Pattern Matcher** - Matches to specification patterns
6. **Specification Builder** - Generates YAML specifications
7. **Validation Agent** - Validates and fixes specifications

## 🚀 Quick Start

### 1. Import Components

```python
from langflow.components.tools.agent_builder import (
    SpecificationSearchTool,
    SpecValidatorTool,
    AgentStateManager
)
```

### 2. Load Prompts

```python
from langflow.components.tools.agent_builder.prompts import (
    ORCHESTRATOR_PROMPT,
    REQUIREMENTS_ANALYST_PROMPT,
    INTENT_CLASSIFIER_PROMPT,
    # ... other prompts
)
```

### 3. Configure in Langflow

Use the specification at:
`specifications_library/agents/multi-agent/agent-builder-system.yaml`

## 📋 Three-Phase Process

### Phase 1: Understanding & Research
- Extract requirements
- Classify intent
- Search for similar agents

### Phase 2: Planning & Design
- Match patterns
- Design architecture
- Plan components

### Phase 3: Implementation
- Generate specification
- Validate YAML
- Provide final spec

## 💡 Example Usage

```
User: "I need a customer support chatbot"
    ↓
Orchestrator uses Requirements Analyst
    ↓
Extracts: goal, domain, integrations
    ↓
Orchestrator uses Intent Classifier
    ↓
Identifies: conversational pattern
    ↓
Orchestrator uses Research Agent
    ↓
Finds: similar chatbots
    ↓
Orchestrator uses Spec Builder
    ↓
Generates: YAML specification
    ↓
Orchestrator uses Validation Agent
    ↓
Returns: Validated specification
```

## 🔧 Configuration

### Environment Variables

```bash
# Optional: Customize specification library path
SPEC_LIBRARY_PATH=/path/to/specifications_library

# LLM Configuration
OPENAI_API_KEY=your-key-here
```

### Model Selection

Each agent can use different models:
- Orchestrator: GPT-4 (complex reasoning)
- Requirements/Builder: GPT-4 (generation tasks)
- Classifier/Matcher: GPT-3.5 (classification tasks)
- Validation: GPT-3.5 (structured checks)

## 📁 File Structure

```
agent_builder/
├── __init__.py                    # Component exports
├── specification_search.py        # Search tool
├── spec_validator.py              # Validator tool
├── agent_state_manager.py         # State management tool
├── prompts.py                     # Agent prompts
├── example_usage.md              # Usage examples
└── README.md                      # This file
```

## 🎯 Benefits

1. **Minimal Code**: Only 3 actual tool components needed
2. **Reusable Agents**: Standard agent component with different prompts
3. **Modular Design**: Each agent handles one responsibility
4. **Easy Updates**: Change prompts without code changes
5. **Scalable**: Add new agents without new components

## 🔄 Workflow

1. User describes what agent they need
2. Orchestrator coordinates specialized agents
3. Each agent performs its specialized task
4. Results are validated and refined
5. Final specification is returned

## 🧪 Testing

```python
# Test search tool
search = SpecificationSearchTool()
search.query = "healthcare"
results = search.search()

# Test validator
validator = SpecValidatorTool()
validator.spec_yaml = "your_spec_here"
validation = validator.validate()

# Test state manager
state_manager = AgentStateManager()
state_manager.session_id = "test-session"
state_manager.operation = "store"
state_manager.key = "requirements"
state_manager.value = '{"goal": "test"}'
result = state_manager.process()
```

## 📚 Documentation

- **Prompts**: See `prompts.py` for all agent prompts
- **Example**: See `example_usage.md` for detailed flow
- **Specification**: See `agent-builder-system.yaml` for complete spec

## 🤝 Contributing

To add new capabilities:

1. **New Tool**: Create Component class if non-LLM operation
2. **New Agent**: Add prompt to `prompts.py`, use standard agent
3. **New Pattern**: Update pattern matcher prompt

## 📄 License

Part of AI Studio / Langflow - Internal Use