# Product Requirements Document: Langflow Assistant

## Executive Summary

Langflow Assistant is an AI-powered development assistant that enhances the Langflow flow-building experience by providing intelligent suggestions, automation, and code generation capabilities. It leverages LFX run_flow to execute dedicated assistant flows, making AI assistance a first-class, extensible capability across the platform.

## Vision

Transform Langflow from a visual workflow builder into an intelligent development platform where AI actively assists developers in:
- Crafting better prompts and messages
- Discovering and connecting the right components
- Generating complete flows from natural language descriptions
- Creating custom components tailored to specific needs

## Product Overview

### Core Philosophy

1. **Flow-Based Architecture**: All assistant capabilities are implemented as Langflow flows, making them transparent, debuggable, and customizable
2. **API-First Design**: Generic REST APIs that execute flows via LFX run_flow, enabling reuse across UI experiences
3. **Context-Aware Intelligence**: Deep integration with flow metadata, component schemas, and user context
4. **Progressive Enhancement**: Assistive features that enhance—not replace—the core workflow building experience

### Target Users

1. **Beginner Users**: Need guidance on component selection and prompt engineering
2. **Intermediate Users**: Want to accelerate development with intelligent suggestions
3. **Advanced Users**: Seek to automate repetitive tasks and extend capabilities
4. **Enterprise Teams**: Require standardized patterns and best practices enforcement

## System Architecture

### High-Level Design

```
┌─────────────────────────────────────────────────────────────┐
│                    Langflow UI Layer                        │
│  • Component Field Inputs   • Flow Canvas   • Chat Panel   │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│               Agentic API Layer (/agentic)                  │
│  • /prompt          • /next_component                       │
│  • /flow_from_prompt • /generate_component                  │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│                  LFX run_flow Engine                        │
│  Executes assistant flows with global variables             │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│              Assistant Flow Templates                       │
│  • PromptGeneration.json    • NextComponentSuggestion.json  │
│  • VibeFlow.json            • ComponentCodeGen.json         │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│                  MCP Server Tools                           │
│  • search_components    • visualize_flow_graph              │
│  • search_templates     • get_component_details             │
│  • list_component_types • update_component_field            │
└─────────────────────────────────────────────────────────────┘
```

### Core Components

#### 1. Agentic API Router
- **Location**: `/src/backend/base/langflow/agentic/api/router.py`
- **Responsibility**: FastAPI endpoints that orchestrate LFX run_flow execution
- **Pattern**: Accept request → fetch context → execute flow → return result

#### 2. Assistant Flow Templates
- **Location**: `/src/backend/base/langflow/agentic/flows/`
- **Responsibility**: Configurable Langflow flows that implement assistant logic
- **Pattern**: Input parameters → AI processing → structured output

#### 3. MCP Server Tools
- **Location**: `/src/backend/base/langflow/agentic/mcp/server.py`
- **Responsibility**: Low-level utilities for flow introspection and manipulation
- **Pattern**: Tool functions exposed via FastMCP for use in assistant flows

#### 4. Utility Modules
- **Location**: `/src/backend/base/langflow/agentic/utils/`
- **Modules**:
  - `component_search.py`: Component discovery and metadata
  - `flow_graph.py`: Flow visualization and analysis
  - `template_search.py`: Template discovery and filtering
  - `flow_component.py`: Component field read/write operations
  - `template_create.py`: Flow creation from templates

## Feature Set

### 1. Prompt Generation [DONE] (Implemented)
**Status**: Partially Complete  
**Priority**: P0 (Core Feature)

Generate intelligent, context-aware prompts for any text field in a component.

**Capabilities**:
- Flow-aware prompt generation aligned with flow purpose
- Field-specific content formatting
- Existing value enhancement and refinement
- Prompt engineering best practices automation

### 2. Next Component Suggestion 🚧 (In Progress)
**Status**: API endpoint exists, flow template needed  
**Priority**: P0 (Core Feature)

Suggest the most relevant next component to add based on current flow context.

**Capabilities**:
- Analyze current flow structure and purpose
- Consider component compatibility and connections
- Rank suggestions by relevance
- Provide connection guidance

### 3. Vibe Flow (Prompt to Flow) 🎯 (Planned)
**Status**: Design Phase  
**Priority**: P1 (High Impact)

Generate complete, functional flows from natural language descriptions.

**Capabilities**:
- Parse natural language requirements
- Select appropriate template or build from scratch
- Configure components with contextual values
- Establish connections between components

### 4. Custom Component Code Generation 🎯 (Planned)
**Status**: Design Phase  
**Priority**: P2 (Enhanced Feature)

Generate custom component code from specifications.

**Capabilities**:
- Generate Python component code following Langflow patterns
- Include proper type hints, documentation, and error handling
- Integrate with existing component ecosystem
- Support iterative refinement

## Technical Implementation

### API Design Pattern

All assistant features follow a consistent API pattern:

```python
@router.post("/feature_name")
async def run_feature_flow(
    request: FlowRequest,
    current_user: CurrentActiveUser,
    session: DbSession
) -> dict:
    """Execute the feature flow with provided parameters."""
    
    # 1. Authenticate and get API keys
    user_id = current_user.id
    openai_key = await get_openai_api_key(variable_service, user_id, session)
    
    # 2. Gather context (flow details, component data, etc.)
    global_vars = {
        "FLOW_ID": request.flow_id,
        "OPENAI_API_KEY": openai_key,
        "USER_ID": str(user_id),
        # ... feature-specific context
    }
    
    # 3. Execute flow via LFX
    flow_path = Path(__file__).parent.parent / "flows" / "FeatureName.json"
    result = await run_flow(
        script_path=flow_path,
        input_value=request.input_value,
        global_variables=global_vars,
        check_variables=False,
    )
    
    return result
```

### Flow Template Pattern

All assistant flows follow a consistent structure:

```
ChatInput (User Instructions)
    ↓
TextInput (Context Variables via Global Variables)
    ↓
Prompt Template (Combines instructions + context)
    ↓
Language Model (AI Processing)
    ↓
ChatOutput (Structured Result)
```

### Context Variables

Standard context passed to assistant flows:

- `FLOW_ID`: Current flow identifier
- `FLOW_DETAILS`: Flow name, description, text representation
- `COMPONENT_ID`: Target component (if applicable)
- `FIELD_NAME`: Target field (if applicable)
- `FIELD_VALUE`: Current field value (if applicable)
- `USER_ID`: User identifier for personalization
- `OPENAI_API_KEY`: LLM provider API key

## Data Models

### FlowRequest Schema

```python
class FlowRequest(BaseModel):
    flow_id: str                      # Flow UUID or endpoint name
    component_id: str | None = None   # Component vertex ID
    field_name: str | None = None     # Field name within component
    input_value: str | None = None    # User-provided input/instruction
```

### Assistant Response Schema

```python
class AssistantResponse(BaseModel):
    success: bool                     # Operation success indicator
    result: dict | str | list         # Feature-specific result
    metadata: dict | None = None      # Additional context
    error: str | None = None          # Error message if failed
```

## User Experience

### UI Integration Points

#### 1. Component Field Enhancement
- **Location**: Any text/prompt field in component properties
- **Trigger**: "✨ Generate" button or keyboard shortcut
- **Behavior**: Open assistant dialog → collect user intent → generate content → preview → apply

#### 2. Canvas Suggestions
- **Location**: Component context menu or canvas toolbar
- **Trigger**: "Suggest Next Component" action
- **Behavior**: Analyze flow → show ranked suggestions → one-click add

#### 3. Flow Creation Wizard
- **Location**: New flow modal or dedicated page
- **Trigger**: "Create from Description" option
- **Behavior**: Conversational interface → build flow iteratively → refine and deploy

#### 4. Component Studio
- **Location**: Custom components section
- **Trigger**: "Generate Custom Component" button
- **Behavior**: Specification form → code generation → preview → install

### Interaction Patterns

#### Progressive Disclosure
1. Simple trigger (button/shortcut)
2. Optional input (additional instructions)
3. Preview with explanation
4. One-click accept or refine


#### Feedback Loop (Do we need this?)
- Thumbs up/down on suggestions
- Refinement through conversation
- Learn from user preferences
- Improve over time

## Success Metrics

### Adoption Metrics
- % of flows using assistant features
- Average assistant invocations per session
- Feature-specific usage rates

### Quality Metrics
- Acceptance rate of suggestions (target: >70%)
- Time saved per interaction (target: >30 seconds)
- User satisfaction scores (target: >4.0/5.0)

### Impact Metrics
- Reduction in empty/placeholder fields
- Increase in flow completion rates
- Decrease in support requests about component selection

## Security & Privacy

### API Key Management
- User API keys stored encrypted in global variables
- Keys fetched securely per request
- No logging of API keys in assistant flows

### Data Privacy
- Flow metadata shared only within user's workspace
- No external data transmission (except to configured LLM)
- Assistant flows run in user's environment

### Rate Limiting
- Per-user rate limits on assistant endpoints
- Throttling to prevent abuse
- Quota management for enterprise plans

## Extensibility

### Custom Assistant Flows
Users can create custom assistant flows by:
1. Building a flow with expected input/output structure
2. Registering it via configuration
3. Exposing it through existing API pattern

### Plugin Architecture
Third-party integrations can:
- Add new MCP tools
- Contribute assistant flow templates
- Extend context gathering utilities

### Prompt Customization
Users can customize:
- System prompts in assistant flows
- Context inclusion/exclusion
- Output formatting preferences

## Rollout Strategy

### Phase 1: Foundation (Current)
- [DONE] Agentic API infrastructure
- [DONE] MCP server tools
- [DONE] Prompt Generation (basic)
- 🚧 Documentation and testing

### Phase 2: Core Features (Ongoing)
- Enhanced Prompt Generation with UI integration
- Next Component Suggestion
- Flow template improvements
- User feedback collection

### Phase 3: Advanced Features
- Vibe Flow (Prompt to Flow)
- Custom Component Code Generation
- Personalization and learning
- Enterprise features (team templates, approval workflows)

### Phase 4: Ecosystem
- Community template marketplace
- Third-party integrations
- Advanced customization
- AI model choice (beyond OpenAI)

## Open Questions

1. **Multi-LLM Support**: Should we support multiple LLM providers for assistant features?
    Suggestion to start with OpenAI and add other LLM providers in future phases.
2. **Offline Mode**: Can we provide basic assistance without LLM calls?
    Suggestion: Not possiblewithit llm we might need to support local llm models in future phases.
3. **Telemetry**: What usage data should we collect (opt-in) for improvement?
    Suggestion: Possible can we use scarf to collect agentic endpoint usage data?
4. **Versioning**: How do we handle assistant flow template updates?


## Dependencies

### External
- LFX run_flow engine
- OpenAI API (or alternative LLM provider)
- FastMCP framework

### Internal
- Component schema registry
- Template storage system
- User authentication and authorization
- Global variables service

## Success Criteria

The Langflow Assistant will be considered successful when:
1. All four core features are implemented and stable
2. 40%+ of active users engage with assistant features monthly
3. 70%+ suggestion acceptance rate across all features
4. Positive sentiment in user feedback (>4.0/5.0)
5. Documented patterns enabling community contributions

## References

- [Existing Agentic API Router](./src/backend/base/langflow/agentic/api/router.py)
- [MCP Server Implementation](./src/backend/base/langflow/agentic/mcp/server.py)
- [Prompt Generation Flow](./src/backend/base/langflow/agentic/flows/PromptGeneration.json)
- [Component Search Utilities](./src/backend/base/langflow/agentic/utils/component_search.py)

---

**Document Version**: 1.0  
**Last Updated**: January 2026  
**Status**: Living Document  
**Owners**: Langflow Engineering Team

