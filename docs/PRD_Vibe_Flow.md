# Product Requirements Document: Vibe Flow (Prompt to Flow)

## Overview

**Feature**: Vibe Flow (Prompt to Flow)  
**Status**: Exploration Phase - Advanced Next Component Suggestion  
**Priority**: P2 (Future Feature)  
**Target Release**: Phase 4+  
**API Endpoint**: `/agentic/flow_from_prompt` (to be created)  
**Flow Template**: `VibeFlow.json` (to be created)

## Executive Summary

Vibe Flow is an advanced application of Next Component Suggestion that generates complete flows from natural language descriptions. Instead of suggesting one component at a time, it applies the same template + component vector search approach iteratively to build entire flows. This document explores potential implementation methods and positions Vibe Flow as a natural evolution of single-component suggestions.

## Problem Statement

### Current Pain Points

1. **Steep Learning Curve**: New users overwhelmed by component library and connection rules
2. **Time-Consuming Setup**: Even experienced users spend 15-30 minutes on basic flow scaffolding
3. **Pattern Knowledge Required**: Users must know established patterns (RAG, agent loops, etc.)
4. **Blank Canvas Problem**: Starting from scratch is intimidating and error-prone
5. **Template Limitations**: Existing templates are fixed; can't be customized to specific needs

### User Stories

**As a beginner user**, I want to describe what I want to build and get a working flow so I can start testing immediately without learning every component.

**As an intermediate user**, I want to quickly scaffold complex flows from a description so I can focus on fine-tuning rather than basic setup.

**As an advanced user**, I want to prototype flow ideas rapidly by describing them in natural language, then iterate on the generated result.

**As a business user**, I want to create flows without technical knowledge by describing my business process in plain English.

**As an enterprise architect**, I want to generate flows that follow organizational patterns and include required components (logging, auth, etc.).

## Relationship to Next Component Suggestion

Vibe Flow extends Next Component Suggestion from single-component to full-flow generation:

**Next Component**: User has partial flow → suggest 1 next component  
**Vibe Flow**: User has description → suggest N components to create complete flow

Both use the same underlying architecture:
1. Vector search on templates to identify patterns
2. Vector search on components to find relevant candidates  
3. LLM ranks and configures components with explanations

The key difference is iteration: Next Component suggests once, Vibe Flow applies the suggestion logic repeatedly until flow is complete.

## Solution Design (Methods to Explore)

### Functional Requirements
- **FR1**: Natural language parsing to extract intent and requirements (>90% accuracy)
- **FR2**: Template selection via vector search or custom build from scratch (>85% optimal choice)
- **FR3**: Component selection using two-stage vector search (>90% relevance)
- **FR4**: Component configuration with contextual values (>70% usable without modification)
- **FR5**: Valid connection establishment (100% valid, >80% executable)
- **FR6**: Iterative refinement through follow-up prompts (>80% correct)

### Non-Functional Requirements
- **Performance**: <15s simple flows, <30s complex flows, <60s max
- **Quality**: >80% flows run without modification, >90% user satisfaction
- **Scalability**: Support up to 50 components, handle concurrent requests
- **Cost**: <$0.50 per generation (template reuse optimization)

## Technical Approach: Iterative Vector Search

### Extending Next Component Suggestion to Full Flows

Vibe Flow applies the two-stage vector search iteratively:

**Stage 1: Template Pattern Matching**
- Embed user's natural language description
- Vector search template database for similar complete flows
- If strong match found (confidence >0.85): Use template as starting point and customize
- If no strong match: Build from scratch using Stage 2 iteratively

**Stage 2: Iterative Component Selection**
- Start with empty flow or template baseline
- For each position in flow:
  - Embed current partial flow context + user requirements
  - Vector search component database for next logical component
  - LLM ranks top candidates and selects best fit
  - Add component with configuration
  - Repeat until flow is complete (termination conditions met)

**Termination Conditions**:
- Required endpoints connected (input → output path exists)
- Pattern requirements satisfied (e.g., RAG has all required stages)
- User-specified component count reached
- LLM determines flow is functionally complete

**Database Strategy** (same as Next Component Suggestion):
- **Registered Users**: Astra DB with complete template and component vectors
- **OSS Users**: Bundled FAISS/Chroma with pre-computed vectors

### Methods to Explore

**Method 1: Template Completion**
- Find best matching template via vector search
- Identify missing or customizable components
- Fill gaps using component vector search
- Configure based on user description

**Method 2: Iterative Construction**  
- Build flow step-by-step like Next Component Suggestion
- Each iteration: suggest next component given current state
- Continue until flow complete
- More flexible but slower

**Method 3: Hybrid Approach**
- Use template as scaffold
- Iteratively add/modify components as needed
- Balance speed (template) with customization (iteration)

**Recommended**: Start with Method 3 (Hybrid) for best balance of quality and performance.

## Technical Architecture

### System Flow

1. **User Input**: Description via "Create from Description" modal → POST `/agentic/flow_from_prompt`
2. **Template Search**: Embed description → vector search template database → find similar patterns
3. **Decision Point**: 
   - Strong template match (>0.85): Customize template
   - Weak match: Build from scratch
4. **Iterative Component Selection**: For each flow position:
   - Embed partial flow + requirements → vector search components → LLM selects best
   - Configure component with contextual values
   - Add to flow, repeat until complete
5. **Flow Construction**: Validate → assign IDs → establish connections → create DB record
6. **Response**: Return flow ID, URL, and explanation

### Generation Strategies

**Strategy A: Template-Based (Fast)**
- Vector search finds matching template (e.g., "RAG chatbot" → RAG template)
- Customize component configurations based on user requirements
- Add/remove components as needed
- Best for: Common patterns with minor variations

**Strategy B: Iterative Build (Flexible)**
- Start with empty canvas
- Apply Next Component Suggestion repeatedly
- Each step: suggest → configure → connect → continue
- Best for: Novel flows, unique requirements

**Strategy C: Hybrid (Recommended)**
- Use template as scaffold if available
- Apply iterative suggestions for gaps
- Balance speed and customization
- Best for: Most use cases

### API Contract

**Request**: 
```json
{
  "description": "Create a RAG chatbot for company docs",
  "preferences": { "llm_provider": "openai", "complexity": "simple" },
  "constraints": { "max_components": 15 },
  "conversation_id": "uuid",  // For refinement
  "refinement": false
}
```

**Response**:
```json
{
  "success": true,
  "flow": {
    "id": "uuid",
    "name": "RAG Chatbot",
    "url": "/flow/uuid",
    "component_count": 8
  },
  "explanation": {
    "template_used": "RAG Pipeline",
    "components_added": [{"component": "ChatInput", "reason": "Collects questions"}],
    "next_steps": ["Upload docs", "Configure API key", "Test"]
  },
  "suggested_refinements": ["Add memory", "Include reranker"]
}
```

### LLM Processing Instructions

**Role**: Flow Architect that uses vector search results to build complete flows

**Input Context** (filtered by vector search):
- User's natural language description
- Top 3-5 similar template patterns from vector search
- Top 10-20 relevant components per position from vector search
- Current partial flow state (for iterative building)

**Process**:
1. Review template matches and decide: customize template OR build from scratch
2. For each component position:
   - Evaluate pre-filtered component candidates
   - Select best fit for current position
   - Configure with contextual values
   - Establish connections to previous components
3. Validate flow completeness (input → output path exists)
4. Generate explanation and next steps

**Output Format**:
```json
{
  "flow_specification": {
    "strategy": "template_customize|iterative_build|hybrid",
    "template_id": "uuid",  // if using template
    "components": [
      {"type": "ChatInput", "id": "chat_1", "config": {...}},
      // ... more
    ],
    "connections": [
      {"source": "chat_1", "target": "llm_1"},
      // ... more
    ]
  },
  "explanation": {
    "pattern": "RAG Pipeline",
    "component_rationale": {"chat_1": "Collects questions"},
    "next_steps": ["Configure API keys", "Upload docs", "Test"]
    }
}
```

**Common Patterns** (discovered via template vector search):
- RAG: DocumentLoader → TextSplitter → Embeddings → VectorStore → Retriever → LLM
- Agent: ChatInput → Agent → Tools → Memory → ChatOutput
- Simple Chat: ChatInput → LLM → ChatOutput
- Data Pipeline: Loader → Processor → Transformer → Output

## User Experience

### UI Integration

**New Flow Modal**: 
- Blank Flow
- From Template  
- ✨ Describe Your Flow (Vibe Flow)

**Vibe Flow Page** (`/flow/create/vibe`): Text area with examples, advanced options, Generate button

### Interaction Scenarios

**Simple Generation**: User types "GPT-4 chatbot" → Progress indicator → Flow created → Explanation panel shows components and next steps

**With Clarification**: User types ambiguous request → System asks questions (data source? analysis type? output format?) → User answers → Flow generated

**Iterative Refinement**: Existing flow → "Refine Flow" button → "Add conversation memory" → System adds component and updates connections → Show diff → Accept

### Visual Elements

**Progress**: Checkmark steps (Analyzed, Selected, Configuring, Connecting, Validating) with percentage bar

**Explanation Panel**: Flow name, pattern description, component list with icons and purposes, next steps, suggested improvements, action buttons

## Implementation Plan

**Note**: Vibe Flow is an advanced feature that builds on Next Component Suggestion. Implement Next Component first, then extend to full flows.

### Phase 1: Extend Vector Infrastructure (Week 1-2)

#### Tasks
- [ ] Ensure template vector database includes complete flow patterns (from Next Component Suggestion)
- [ ] Add component vector database with positional metadata (first, middle, last, etc.)
- [ ] Test template matching for flow descriptions
- [ ] Implement iterative component selection logic

### Phase 2: Backend - Iterative Flow Generation (Week 3-5)

#### Tasks
- [ ] Create `/agentic/flow_from_prompt` API endpoint
- [ ] Implement hybrid generation strategy:
  - Template matching via vector search
  - Gap filling via iterative component selection
- [ ] Flow construction service (JSON → DB with validation)
- [ ] Termination logic (flow completeness detection)
- [ ] Unit and integration tests

### Phase 3: Frontend UI (Week 6-7)

#### Tasks
- [ ] "Create from Description" modal
- [ ] Progress indicator with steps
- [ ] Flow explanation panel
- [ ] Refinement dialog
- [ ] Error handling

### Phase 4: Refinement & Optimization (Week 8+)

#### Tasks
- [ ] Clarifying questions for ambiguous requests
- [ ] Diff visualization for refinements
- [ ] Quality metrics and feedback loop
- [ ] Token usage optimization
- [ ] A/B test generation strategies

## Testing Strategy

### Unit Tests
- **Template Matching**: Verify vector search finds correct template for description
- **Iterative Selection**: Test component selection at each position
- **Flow Validation**: Verify all components valid, connections correct, input→output path exists
- **Termination Logic**: Confirm flow completion detection works

### Integration Tests
- **Simple Chat**: "GPT-4 chatbot" → 3+ components (ChatInput, LLM, ChatOutput)
- **RAG Pipeline**: "RAG for PDFs" → 7+ components (Loader, Splitter, Embeddings, VectorStore, Retriever, LLM, Output)
- **Agent**: "Agent with tools" → Agent component with tool connections
- **Data Pipeline**: "Summarize CSV" → CSVLoader → LLM → TextOutput

### UAT Scenarios
- Template match (>0.85): Customizes existing template correctly
- No template match: Builds from scratch using iterative selection
- Refinement: "Add memory" correctly modifies existing flow
- Ambiguous request: Triggers clarifying questions

## Success Metrics

- **Adoption**: 30% of new flows created via Vibe Flow (6 months)
- **Executability**: >80% of flows run without modification
- **Satisfaction**: >4.0/5.0 rating
- **Efficiency**: >10 minutes saved vs manual creation
- **Retention**: >60% repeat usage (3 months)

## Cost Analysis (with Vector Search Optimization)

### Per-Generation Cost (GPT-4o-mini)

**Without Vector Search**:
- Simple flow: ~2000 input + 800 output = $0.78
- Complex flow: ~3000 input + 1500 output = $1.35
- Refinement: ~2500 input + 600 output = $0.73

**With Vector Search** (template + component filtering):
- Simple flow: ~800 input + 800 output = $0.36 (54% savings)
- Complex flow: ~1200 input + 1500 output = $0.63 (53% savings)
- Refinement: ~900 input + 600 output = $0.37 (49% savings)

**Monthly Estimate** (1000 users, 3 generations avg, 50% simple / 30% complex / 20% refinement):
- Without vector search: ~$3,150/month
- With vector search: ~$1,470/month (53% savings)

### Cost Optimization Strategies

1. **Template Reuse**: Vector search finds existing template (70% token reduction when match found)
2. **Component Pre-filtering**: Only top 10-20 components per position (vs all 200+)
3. **Iterative Generation**: Build incrementally instead of all-at-once (better context efficiency)
4. **Caching**: Static component/template vectors computed once

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Poor flow quality | High | Template-based patterns + extensive testing + user feedback |
| Hallucinated components | High | Validate against registry, use vector-filtered candidates |
| Invalid connections | High | Strict validation, type checking, pattern compliance |
| Slow generation time | Medium | Vector search pre-filtering, template reuse |
| High token costs | Medium | Vector optimization (53% savings) |

## Open Questions

1. **Multi-language descriptions?** → LLM supports naturally, test extensively
2. **Vague descriptions?** → Implement clarifying questions flow
3. **Modify generated flow?** → Full edit support + "Refine" for AI-assisted changes
4. **Generation history?** → Yes, for debugging and learning
5. **Complex flows (50+ components)?** → Start with 20 limit, expand based on quality
6. **Custom components?** → Include in local vector DB like Next Component Suggestion

## Dependencies

### Internal (Required)
- ✅ Next Component Suggestion infrastructure (template + component vector databases)
- ✅ LFX run_flow engine
- ✅ Component registry
- ✅ Template system
- 🚧 Flow construction service (JSON → DB with validation)
- 🚧 Iterative generation logic (extends Next Component)

### External
- ✅ OpenAI API (user-provided key)
- 🚧 Frontend flow rendering and explanation UI
- 🚧 Analytics service

### Vector Search (Inherited from Next Component Suggestion)
- ✅ Template database with text representations
- ✅ Component database with metadata
- ✅ Astra DB for registered users / FAISS/Chroma for OSS

## Acceptance Criteria

1. 🚧 Next Component Suggestion fully implemented and tested
2. 🚧 Vector search successfully filters templates and components
3. 🚧 Simple flows (3-5 components) generated from descriptions
4. 🚧 5+ common patterns supported (Chat, RAG, Agent, Pipeline, API)
5. 🚧 80% of flows run without modification
6. 🚧 Hybrid strategy (template + iterative) operational
7. 🚧 Generation <30 seconds for typical flows
8. 🚧 UI provides clear explanation and refinement option
9. 🚧 4.0+ user satisfaction in testing

## Related Documentation

**Foundation**: [Next Component Suggestion](./PRD_Next_Component_Suggestion.md) - Vibe Flow extends this feature from single to multiple components

**Related**: [Langflow Assistant Overview](./PRD_Langflow_Assistant.md), [Prompt Generation](./PRD_Prompt_Generation.md), [Custom Component Generation](./PRD_Custom_Component_Generation.md)

**Existing Code**:
- Template utilities: `template_search.py`, `template_create.py`
- Component utilities: `component_search.py`
- Flow utilities: `flow_graph.py`, `flow_component.py`

**Inspirations**: Vercel v0, GitHub Copilot Workspace, Replit Agent

---

**Document Version**: 2.0  
**Last Updated**: January 2026  
**Status**: Exploration Phase - Advanced Next Component Suggestion  
**Owner**: Langflow Engineering Team

