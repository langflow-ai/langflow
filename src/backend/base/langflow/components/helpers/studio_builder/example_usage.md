# AI Agent Builder System - Usage Example

## Overview
This document demonstrates how to use the AI Agent Builder multi-agent system to create agent specifications.

## System Architecture

```
┌────────────────────────────────────────┐
│     Main Orchestrator Agent            │
├────────────────────────────────────────┤
│ Coordinates all specialized agents     │
│ Tools:                                 │
│ - Requirements Analyst (agent as tool) │
│ - Intent Classifier (agent as tool)    │
│ - Research Agent (agent as tool)       │
│ - Pattern Matcher (agent as tool)      │
│ - Spec Builder (agent as tool)         │
│ - Validation Agent (agent as tool)     │
└────────────────────────────────────────┘
                    │
        ┌──────────┴──────────┐
        │                      │
    Actual Tools        Specialized Agents
    ┌──────────┐        (Each with LLM)
    │ Spec     │
    │ Search   │
    │ Validator│
    │ Memory   │
    └──────────┘
```

## Example Conversation Flow

### User Request
```
User: "I need to build a customer support chatbot that can handle FAQs,
search our knowledge base, and escalate complex issues to human agents."
```

### Phase 1: Understanding & Research

**Orchestrator → Requirements Analyst**
```json
{
  "requirements": {
    "goal": "Handle customer support inquiries with FAQ responses, knowledge search, and escalation",
    "domain": "customer-support",
    "use_case_type": "conversational",
    "inputs": ["user_messages", "chat_history"],
    "outputs": ["bot_responses", "escalation_tickets"],
    "integrations": ["knowledge_base", "ticketing_system"],
    "performance": "real-time",
    "security": {
      "pii_handling": true,
      "data_retention": "30_days"
    }
  },
  "confidence_score": 0.85,
  "missing_fields": ["specific_knowledge_base_type", "ticketing_platform"],
  "clarifying_questions": [
    "What knowledge base system are you using?",
    "Which ticketing platform for escalations?"
  ]
}
```

**Orchestrator → Intent Classifier**
```json
{
  "agent_type": "conversational_support",
  "complexity": "intermediate",
  "suggested_pattern": "conversational_with_tools",
  "reasoning": "Requires memory, multiple tools, and conditional routing",
  "components_needed": [
    "chat_input",
    "memory_component",
    "agent",
    "knowledge_search_tool",
    "escalation_tool",
    "chat_output"
  ]
}
```

**Orchestrator → Research Agent**
```json
{
  "similar_agents": [
    {
      "name": "HelpDesk Assistant",
      "relevance_score": 0.92,
      "reusable_components": ["memory", "knowledge_search"],
      "adaptations_needed": ["Add escalation logic"]
    },
    {
      "name": "FAQ Bot",
      "relevance_score": 0.78,
      "reusable_components": ["faq_matcher"],
      "adaptations_needed": ["Add knowledge search", "Add escalation"]
    }
  ],
  "recommended_pattern": "conversational_with_memory_and_tools",
  "reusable_configs": {
    "memory_config": {
      "type": "agent_state",
      "window_size": 10
    },
    "agent_config": {
      "temperature": 0.7,
      "max_tokens": 500
    }
  }
}
```

### Phase 2: Planning & Design

**Orchestrator → Pattern Matcher**
```json
{
  "primary_pattern": "conversational_with_tools",
  "confidence": 0.88,
  "modifications": [
    "Add conditional routing for escalation",
    "Include fallback to FAQ when knowledge search fails"
  ],
  "components": {
    "required": [
      "genesis:chat_input",
      "genesis:memory",
      "genesis:agent",
      "genesis:knowledge_hub_search",
      "genesis:chat_output"
    ],
    "optional": [
      "genesis:sentiment_analyzer",
      "genesis:language_detector"
    ],
    "configuration": {
      "agent": {
        "system_prompt": "Customer support specialist prompt",
        "tools": ["knowledge_search", "escalation_trigger"]
      }
    }
  },
  "data_flow": "Input → Memory → Agent (with tools) → Conditional Output"
}
```

### Phase 3: Implementation

**Orchestrator → Specification Builder**
```yaml
id: urn:agent:genesis:support:customer-chatbot:1.0.0
name: Customer Support Chatbot
description: Intelligent chatbot for customer support with FAQ, knowledge search, and escalation
kind: Single Agent
domain: customer-support
version: 1.0.0
agentGoal: Provide automated customer support with intelligent escalation

components:
  - id: user-input
    type: genesis:chat_input
    name: Customer Message

  - id: memory
    type: genesis:memory
    name: Conversation History
    config:
      window_size: 10

  - id: knowledge-search
    type: genesis:knowledge_hub_search
    name: Knowledge Base Search
    config:
      index_name: customer_support
      top_k: 3

  - id: support-agent
    type: genesis:agent
    name: Support Agent
    config:
      system_prompt: |
        You are a helpful customer support agent...
      llm_model: gpt-3.5-turbo
      temperature: 0.7

  - id: response-output
    type: genesis:chat_output
    name: Bot Response

# ... rest of specification
```

**Orchestrator → Validation Agent**
```json
{
  "valid": true,
  "errors": [],
  "warnings": [
    "Consider adding error handling for knowledge base timeout"
  ],
  "suggestions": [
    "Add sentiment analysis for better escalation decisions",
    "Include conversation summary in escalation tickets"
  ]
}
```

### Final Response from Orchestrator

```
I've successfully created a customer support chatbot specification for you. Here's what I've built:

**Specification Summary:**
- Type: Conversational agent with tools
- Complexity: Intermediate (6 components)
- Pattern: Memory-enabled chat with knowledge search

**Key Features:**
✅ FAQ handling through knowledge base search
✅ Conversation memory for context
✅ Escalation logic for complex issues
✅ Real-time response generation

**Validation Status:** ✅ Passed

**Suggestions for Enhancement:**
1. Consider adding sentiment analysis to better detect frustrated customers
2. Include conversation summaries when escalating to human agents
3. Add multilingual support if serving international customers

The specification has been validated and is ready for deployment. Would you like me to:
- Add any of the suggested enhancements?
- Modify the escalation criteria?
- Adjust the knowledge base configuration?
```

## How to Use in Langflow

1. **Import Components**: The three tool components are automatically available in Langflow
   - `SpecificationSearchTool`
   - `SpecValidatorTool`
   - `AgentStateManager`

2. **Configure Agents**: Use standard Agent components with the prompts from `prompts.py`

3. **Connect as Tools**: Enable `tool_mode` on sub-agents to make them available to orchestrator

4. **Test Flow**:
   ```python
   # Example test
   from langflow.components.tools.agent_builder import (
       SpecificationSearchTool,
       SpecValidatorTool,
       AgentStateManager
   )

   # Create instances
   search_tool = SpecificationSearchTool()
   validator = SpecValidatorTool()
   state_manager = AgentStateManager()

   # Use in flow
   search_tool.query = "customer support"
   results = search_tool.search()
   ```

## Benefits of Multi-Agent Architecture

1. **Modularity**: Each agent specializes in one task
2. **Reusability**: Agents can be reused in different flows
3. **Maintainability**: Update prompts without changing code
4. **Scalability**: Add new specialized agents easily
5. **Transparency**: Clear reasoning at each step

## Next Steps

1. **Deploy**: Load the specification in Langflow
2. **Configure**: Set up API keys and model preferences
3. **Test**: Run example conversations
4. **Iterate**: Refine prompts based on results
5. **Extend**: Add more specialized agents as needed