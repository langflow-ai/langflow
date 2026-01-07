# Product Requirements Document: Prompt Generation

## Overview

**Feature**: Prompt Generation  
**Status**: Partially Implemented  
**Priority**: P0 (Core Feature)  
**Target Release**: Phase 1  
**API Endpoint**: `/agentic/prompt`  
**Flow Template**: `PromptGeneration.json`

## Executive Summary

The Prompt Generation feature enables users to generate high-quality, context-aware prompts and messages for any text field in Langflow components. By leveraging LLM intelligence combined with flow context, this feature eliminates the burden of prompt engineering and ensures consistency with the flow's purpose.

## Problem Statement

### Current Pain Points

1. **Blank Field Syndrome**: Users face empty text fields without guidance on what to write
2. **Prompt Engineering Complexity**: Effective prompts require expertise and iteration
3. **Context Misalignment**: Manually written prompts often don't align with flow objectives
4. **Time Consumption**: Crafting quality prompts is time-consuming and repetitive
5. **Inconsistency**: Different users write prompts with varying quality and structure

### User Stories

**As a beginner user**, I want the system to generate appropriate prompts for me so I don't need to understand prompt engineering principles.

**As an intermediate user**, I want to provide high-level instructions and have the system expand them into well-structured prompts that align with my flow's purpose.

**As an advanced user**, I want to quickly generate baseline prompts that I can refine, saving time on boilerplate content.

**As an enterprise user**, I want prompts to follow organizational standards and best practices automatically.

## Solution Design

### Functional Requirements

#### FR1: Context-Aware Generation
- **Description**: Generate prompts that align with the flow's name, description, and structure
- **Priority**: Must Have
- **Success Criteria**: Generated prompts reference flow purpose in >80% of cases

#### FR2: Field-Type Awareness
- **Description**: Adapt generation to field type (system message, user input, template, etc.)
- **Priority**: Must Have
- **Success Criteria**: Format matches field type in 100% of cases

#### FR3: Custom Instructions Support
- **Description**: Accept optional user instructions to guide generation
- **Priority**: Must Have
- **Success Criteria**: Instructions incorporated in 100% of cases when provided

#### FR4: Value Enhancement
- **Description**: Enhance or refine existing field values when present
- **Priority**: Should Have
- **Success Criteria**: Preserved intent in >90% of enhancement cases

#### FR5: Best Practices Application
- **Description**: Apply prompt engineering best practices automatically
- **Priority**: Should Have
- **Success Criteria**: Generated prompts include clear structure, examples, constraints

#### FR6: Multi-Field Support
- **Description**: Support all text field types across all component types
- **Priority**: Must Have
- **Success Criteria**: Works with ChatInput, Prompt, TextInput, System Message fields

### Non-Functional Requirements

#### NFR1: Performance
- **Target**: <3 seconds response time for typical prompts
- **Max**: <10 seconds for complex prompts

#### NFR2: Availability
- **Target**: 99% uptime (dependent on LLM provider)
- **Fallback**: Graceful degradation with clear error messages

#### NFR3: Cost Efficiency
- **Target**: <$0.05 per generation on average (TBD )
- **Optimization**: Token-efficient context passing

#### NFR4: Security
- **Requirement**: No sensitive data logged or transmitted unnecessarily
- **Compliance**: API keys encrypted at rest and in transit

## Technical Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                      UI Layer                               │
│  Component Field → ✨ Generate Button → Dialog              │
└────────────────────┬────────────────────────────────────────┘
                     │ POST /agentic/prompt
┌────────────────────▼────────────────────────────────────────┐
│              Agentic API Router                             │
│  • Authenticate user                                        │
│  • Fetch OPENAI_API_KEY from global variables              │
│  • Gather flow context (name, description, graph)          │
│  • Gather component context (field name, current value)    │
│  • Prepare global variables                                │
└────────────────────┬────────────────────────────────────────┘
                     │ run_flow(PromptGeneration.json)
┌────────────────────▼────────────────────────────────────────┐
│           PromptGeneration Flow                             │
│  ChatInput ← User custom instructions                       │
│  TextInput ← FLOW_DETAILS (global var)                      │
│  TextInput ← FIELD_VALUE (global var)                       │
│  PromptTemplate ← Combines all context                      │
│  LanguageModel ← Processes with OpenAI                      │
│  ChatOutput → Generated prompt text                         │
└────────────────────┬────────────────────────────────────────┘
                     │ Return result
┌────────────────────▼────────────────────────────────────────┐
│                    UI Layer                                 │
│  Display result → Preview → Accept/Reject/Refine            │
└─────────────────────────────────────────────────────────────┘
```

### API Contract

#### Request Schema

```python
POST /agentic/prompt

{
  "flow_id": "uuid-or-endpoint-name",
  "component_id": "ChatInput-abc123",      # Optional
  "field_name": "input_value",             # Optional
  "input_value": "Custom instructions..."  # Optional
}
```

#### Response Schema

```python
{
  "text_output": {
    "message": {
      "text": "Generated prompt content here...",
      "sender": "Machine",
      "sender_name": "AI",
      "session_id": "...",
      "timestamp": "2026-01-07T12:34:56Z"
    }
  }
}
```

#### Error Response

```python
{
  "detail": "Error executing flow: ...",
  "status_code": 500
}
```

### Context Gathering

#### Flow Context
- **Source**: `visualize_flow_graph()` from `mcp/server.py`
- **Data Collected**:
  - `flow_name`: Flow identifier
  - `flow_description`: User-provided flow description
  - `text_repr`: Text representation of flow graph
- **Usage**: Passed as `FLOW_DETAILS` global variable

#### Component Context
- **Source**: `get_flow_component_field_value()` from `mcp/server.py`
- **Data Collected**:
  - `field_name`: Target field name
  - `value`: Current field value (if any)
  - `field_type`: Type of the field
- **Usage**: Passed as `FIELD_VALUE` global variable


### Global Variables Pattern

```python
global_vars = {
    "FLOW_ID": request.flow_id,
    "OPENAI_API_KEY": openai_key,
    "FLOW_DETAILS": f"""
        flow_name: {flow_name}
        flow_description: {flow_description}
        text_repr: {text_repr}
    """,
    "FIELD_VALUE": current_field_value,  # If available
}
```

## User Experience

### UI Flow

#### Scenario 1: Generate for Empty Field

1. User clicks in an empty text field (e.g., System Message in Language Model)
2. "✨ Generate with AI" button appears inline or in toolbar
3. User clicks button
4. Dialog opens with optional "Custom Instructions" field
5. User optionally enters instructions (e.g., "Make it friendly and concise")
6. User clicks "Generate"
7. Loading indicator shows
8. Generated prompt appears in preview pane
9. User reviews and clicks "Accept" → prompt fills field
10. OR user clicks "Refine" → iterative improvement
11. OR user clicks "Cancel" → no changes

#### Scenario 2: Enhance Existing Content

1. User selects text in a field that already has content
2. Context menu or button shows "✨ Enhance with AI"
3. Dialog opens showing current content
4. User provides refinement instructions (e.g., "Add examples", "Make more formal")
5. System generates enhanced version preserving original intent
6. User reviews diff (show changes)
7. User accepts or rejects

#### Scenario 3: Keyboard Shortcut Power User (Do we need this in phase 1)

1. User focused in text field
2. Presses `Cmd/Ctrl + Shift + G` (Generate)
3. Inline popover appears with minimal UI
4. Optional instructions input
5. Press Enter → generate
6. Result appears as suggestion (ghost text)
7. Press Tab → accept, Esc → reject

### Visual Design

#### Generate Button
- **Icon**: ✨ sparkles
- **Placement**: Inline at right edge of text field
- **Hover State**: Tooltip "Generate with AI (⌘⇧G)"
- **Disabled State**: When API key not configured


## Implementation Plan

### Phase 1: Backend Enhancement

#### Tasks
- [x] API endpoint `/agentic/prompt` (DONE)
- [x] Flow template `PromptGeneration.json` (DONE)
- [x] Context gathering utilities (DONE)
- [ ] Enhanced error handling
- [ ] Response caching (optional)
- [ ] Rate limiting implementation
- [ ] Telemetry integration

### Phase 2: Frontend Integration 

#### Tasks
- [ ] Generate button component
- [ ] Generation dialog component
- [ ] Result preview component
- [ ] Keyboard shortcut handling
- [ ] Loading and error states
- [ ] Toast notifications
- [ ] User preferences storage

### Phase 3: Enhancement 

#### Tasks
- [ ] Iterative refinement flow
- [ ] Diff viewer for enhancements
- [ ] History/undo functionality
- [ ] Template library for common patterns
- [ ] A/B testing different system prompts
- [ ] User feedback collection

### Maintenance Phase: Optimization 

#### Tasks
- [ ] Token optimization
- [ ] Response caching strategy
- [ ] Batch generation support
- [ ] Alternative LLM provider support
- [ ] Quality metrics dashboard


## Success Metrics

### Adoption Metrics
- **Target**: 50% of flows use prompt generation at least once
- **Measure**: Track API calls per flow
- **Timeline**: 3 months post-launch

### Quality Metrics
- **Acceptance Rate**: >70% of generated prompts accepted
- **Measure**: Track accept vs. reject in UI
- **Timeline**: Ongoing

### Efficiency Metrics
- **Time Saved**: >30 seconds per generation
- **Measure**: Compare time to manually write equivalent prompt
- **Timeline**: User surveys quarterly

### Satisfaction Metrics
- **User Rating**: >4.0/5.0 stars
- **Measure**: In-app thumbs up/down on results
- **Timeline**: Monthly aggregation


## Risk Assessment

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| LLM API outage | High | Low | Implement fallback, cache recent results |
| Poor quality generations | Medium | Medium | Iterative prompt tuning, user feedback loop |
| Slow response time | Medium | Low | Optimize context size, implement caching |
| High token costs | Low | Medium | Implement token budgets, caching, cheaper models |
| User privacy concerns | High | Low | Clear data usage policy, no logging of content |

## Open Questions

1. **Q**: Should we support multiple LLM providers (Claude, Llama, etc.)?  
   **A**: Phase 2 enhancement, start with OpenAI for MVP

2. **Q**: How do we handle non-English flows?  
   **A**: LLM naturally supports multilingual, but may need explicit instructions

3. **Q**: Should generated prompts be versioned/tracked?  
   **A**: Optional in Phase 3, store in flow metadata

4. **Q**: Can users customize the system prompt?  
   **A**: Phase 3 feature, allow per-workspace customization

5. **Q**: What's the fallback when LLM is unavailable?  
   **A**: Show template library, allow manual entry with examples

## Dependencies

### Internal
- LFX run_flow engine
- Global variables service
- User authentication system
- MCP server tools (visualize_flow_graph, get_component_field_value)

### External
- OpenAI API
- FastMCP framework

### Optional
- Future: Alternative LLM providers (Anthropic, Groq, local models)
- Future: Prompt template library
- Future: Feedback storage system

## Acceptance Criteria

The Prompt Generation feature is complete when:

1. API endpoint `/agentic/prompt` reliably generates prompts
2. Flow context (name, description, structure) is incorporated
3. Custom user instructions are honored
4. Existing field values can be enhanced
5. UI integration allows one-click generation from any text field
6. Error handling covers all edge cases gracefully
7. Response time is <5 seconds for 95% of requests
8. Documentation for users and developers is complete
9. 70%+ acceptance rate achieved in user testing
10. Analytics tracking is in place


## Monetization Strategy

Langflow Prompt Generation will adopt a monetization model inspired by leading developer tools (e.g., Cursor, Gemini, ChatGPT), balancing free access with paid options that unlock premium capabilities.

### Model Gateway Architecture

Prompt Generation will be powered by a "Model Gateway" abstraction, allowing users to access a variety of LLMs (OpenAI GPT-4/3.5, Gemini, Claude, open-source, etc.) via unified APIs. Model routing and authentication is managed centrally, enabling dynamic access policies by user tier.

### Free Tier

- **Available Models**: Access to a limited selection of high-quality open-source models (e.g., Llama, Mistral) and/or a finite number of OpenAI or Anthropic calls via community/shared API keys (subject to rate limits).
- **Features**:
    - Prompt Generation from any text field
    - Limited usage: e.g., X prompts per day or month
    - Basic support and documentation
- **Upgrade Prompt**: Users encounter UI cues to upgrade when limits are reached or when requesting advanced models.

### Paid Tiers (Pro/Team/Enterprise)

- **Available Models**: Full access to commercial models (OpenAI GPT-4 Turbo, Anthropic Claude 3, Gemini Ultra, etc.) and the latest open-source models at higher rate limits.
- **Features**:
    - Higher and/or unlimited usage quotas
    - API key bring-your-own (BYO) for custom throughput
    - Priority in job queuing and faster inference
    - Custom prompt templates and advanced analytics
    - Early access to new prompt-related features and models
- **Management Portal**: Subscription management for individuals or teams, including usage dashboards, billing, and model selection.

### Example Usage Flow

1. **Free User**: Selects "Generate Prompt" - uses default LLM (open source or pooled API key), limited requests/day. Exceeds free quota → prompted to upgrade.
2. **Paid User**: Assigns their own API key(s) or accesses premium models via Model Gateway with higher monthly caps and priority processing.

### Precedent

- Follows proven SaaS developer tool models (like Cursor, Gemini, and ChatGPT Plus) to make core features accessible to all, while offering professionals and power users expanded capabilities and reliability for a subscription fee.

This strategy ensures accessibility and sustainability, incentivizing broader adoption while funding ongoing model access, improvements, and enterprise-level support.
