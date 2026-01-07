# Product Requirements Document: Next Component Suggestion

## Overview

**Feature**: Next Component Suggestion  
**Status**: Partially Implemented (API exists, flow template needed)  
**Priority**: P0 (Core Feature)  
**Target Release**: Phase 2  
**API Endpoint**: `/agentic/next_component` (exists)  
**Flow Template**: `NextComponentSuggestion.json` (to be created)

## Executive Summary

Next Component Suggestion uses template-based AI to recommend the most relevant components to add to a flow. By leveraging proven flow patterns from templates and semantic vector search, it reduces cognitive load, accelerates development, and helps users discover established patterns.

## Problem Statement

**Pain Points**: 200+ components overwhelm users; uncertain what connects where; manual search breaks flow; established patterns (RAG, agents) unknown to beginners

**User Stories**: 
- Beginners want guided suggestions instead of browsing 200+ components
- Intermediate users want fast, pattern-aware suggestions  
- Advanced users want to discover new relevant components
- Enterprise users want pattern consistency and best practices

## Solution Design

### Functional Requirements
- **FR1**: Context-aware suggestions (>80% relevance)
- **FR2**: Connection guidance (100% of suggestions)
- **FR3**: Template pattern recognition (RAG, Agent, Chat, etc.)

### Non-Functional Requirements
- **Performance**: <2s typical, <5s max
- **Relevance**: >80% user approval
- **Scalability**: Handle 50+ component flows
- **Consistency**: Deterministic suggestions for similar flows

## Technical Approach: Template + Component Vector Search

### Two-Stage Vector Search Architecture

The system uses a two-stage vector search approach that leverages existing flow templates to improve suggestion relevance:

**Stage 1: Template Pattern Discovery**  
- Ingest all flow templates with text representations of their graphs
- Store template embeddings in vector database with metadata (template name, description, pattern type)
- When user requests suggestions, embed their current flow context
- Vector search retrieves 3-5 most similar template patterns
- Identifies what components typically come next in those patterns

**Stage 2: Component Retrieval**  
- Based on discovered template patterns, identify relevant component categories
- Vector search on component database filtered by categories
- Returns top 10-20 candidate components
- LLM ranks and explains suggestions with connection guidance

This approach leverages proven flow patterns from templates to guide component suggestions, ensuring recommendations follow established, working architectures.

### Version Roadmap

**V0 (Initial Release)**: Works effectively as long as template library is diversified across common patterns (RAG, agents, chatbots, data pipelines). Quality depends on template coverage.

**V1 (Enhanced)**: Improve template library with more variations, edge cases, and specialized patterns. Add template metadata for better semantic search. Include component usage statistics from templates.

### Database Strategy

**Registered Users (Astra DB)**:  
Astra DB provides monetization opportunity through managed service offering. Registered users get access to centralized, always-updated vectors for all templates and components. Zero setup required, automatic updates, free tier sufficient for most users.

**OSS Users (Local FAISS/Chroma)**:  
Ship pre-computed vectors bundled with Langflow installation. Local vector database (FAISS or Chroma) provides fully offline capability with no external dependencies. Users can generate embeddings locally for custom components/templates. Adds approximately 5-10MB to installation size.

## Technical Architecture

### System Flow

1. **User Triggers**: Context menu or toolbar action → POST to `/agentic/next_component`
2. **Context Gathering**: Use MCP tools/ functions to collect flow structure (visualize_flow_graph), current component details, and flow metadata
3. **Template Search**: Embed flow context → vector search template database → retrieve 3-5 similar templates → identify pattern
4. **Component Search**: Based on template pattern → vector search component database → retrieve top 10-20 relevant components
5. **LLM Ranking**: Pass flow context + filtered components → LLM ranks, explains, and provides connection guidance
6. **Response**: Return 3-5 suggestions 

### Vector Search Implementation

The system implements a two-stage vector search using:

1. **Template Database**: Text representations of all flow templates embedded and searchable by semantic similarity to identify relevant patterns
2. **Component Database**: Core component metadata embedded and searchable, filtered by categories identified from template patterns

This reduces LLM token costs by 90% while improving suggestion quality through pattern-based recommendations. See "Technical Approach" section above for deployment details (Astra DB for registered users, local FAISS/Chroma for OSS).

### Request and Response Contract

**Request**: flow_id (UUID or endpoint), optional component_id, optional custom_requirements  
**Response**: 3-5 ranked suggestions with component_name, confidence (0-1), explanation, connection_guidance, pattern_type; flow_analysis with detected_patterns, completion_status, missing_components

### Context Assembly

- **Flow Graph**: name, description, text representation, component/edge counts
- **Current Component** (if selected): type, display name, outputs, connected inputs
- **Template Matches**: Similar flow patterns from vector search
- **Component Candidates**: Pre-filtered components from vector search

### AI Processing Instructions

**LLM Role**: Component Recommendation Assistant that ranks pre-filtered components

**Analysis Steps**:
1. Review flow name/description and existing components
2. Analyze template patterns identified from vector search
3. Evaluate component compatibility and data flow
4. Rank filtered components by relevance
5. Generate explanations and connection guidance

**Output Rules**:
- Return 3-5 components ranked by relevance
- Connection guidance (how to wire it) (planning required)
- Validate component compatibility (planning required)


## User Experience

### UI Integration Points

1. **Canvas Context Menu**: Right-click component → "✨ Suggest Next Component" option
2. **Toolbar**: "Add Component" dropdown → "✨ Suggest Next Component" (AI-powered)

### Interaction Flow

**Scenario 1: Entire Flow** - User with ChatInput + OpenAI → clicks toolbar suggestion → panel shows ChatOutput (5★), Memory (4★), etc. → click "Add to Flow" → auto-positioned and connected

**Scenario 2: From Component** - Right-click DocumentLoader → suggestions filtered to compatible: TextSplitter (5★), Embeddings (4★) → hover shows connection preview → "Add & Connect" auto-wires



### Visual Design

**Suggestions Panel**: Slides in from right, shows "Suggested Components" with context subtitle. Each suggestion card displays:
- Component icon and name
- Confidence stars (5★ green "Highly Recommended" 0.90-1.0, 4★ blue "Recommended" 0.75-0.89, 3★ yellow "Worth Considering" 0.60-0.74)
- One-sentence explanation
- Pattern type (e.g., "RAG Pipeline")
- Connection guidance
- "Add to Flow" button

**Connection Preview**: Hover shows ghost component on canvas with dashed connection line

**Progressive Disclosure**: "Show More Suggestions" link expands to reveal additional lower-confidence options

## Implementation Plan

### Phase 1: Vector Infrastructure

#### Tasks
- [ ] Build template ingestion pipeline (extract text representations)
- [ ] Generate embeddings for all templates and core components
- [ ] Set up Astra DB with template and component collections
- [ ] Bundle FAISS/Chroma with pre-computed vectors for OSS
- [ ] Implement vector search utilities (template + component)
- [ ] Test vector search quality and performance

### Phase 2: Backend Implementation

#### Tasks
- [ ] Create `NextComponentSuggestion.json` flow template
- [ ] Implement `/agentic/next_component` endpoint with two-stage search
- [ ] Context gathering utilities (MCP tools integration)
- [ ] Response caching strategy
- [ ] Unit and integration tests

### Phase 3: Frontend Implementation 

#### Tasks
- [ ] Suggestions panel component
- [ ] Context menu and toolbar integration
- [ ] Add & connect functionality
- [ ] Connection preview visualization
- [ ] Loading and error states
- [ ] Analytics integration

### Phase 4: V1 Enhancement

#### Tasks
- [ ] Expand template library with more patterns
- [ ] Add template metadata for better search
- [ ] Component usage analytics from templates
- [ ] User feedback loop for continuous improvement

## Testing Strategy

### Unit Tests
- **Vector Search**: Verify template and component retrieval accuracy, embedding quality
- **Flow Analysis**: Validate context extraction, pattern detection, component parsing
- **Suggestion Ranking**: Confirm 3-5 suggestions, sorted by confidence, all required fields present

### Integration Tests
- **End-to-End Pipeline**: API request → template search → component search → LLM ranking → response
- **Flow Scenarios**: Empty flows, simple chat, partial RAG, complete agents, custom components
- **Error Handling**: Invalid flow IDs, missing API keys, service outages

### UAT Scenarios
- **ChatInput only** → suggests LLM + ChatOutput
- **Loader + Splitter** → suggests Embeddings + Vector Store (RAG pattern)
- **"Customer Support Bot"** → suggests ConversationMemory + Agent
- **Right-click DocumentLoader** → suggests compatible downstream components only

## Success Metrics

- **Adoption**: 60% of flows use feature at least once (3 months post-launch)
- **Acceptance Rate**: >50% of top suggestions accepted
- **Relevance**: >4.0/5.0 average rating (thumbs up/down)
- **Efficiency**: >60 seconds saved vs manual search


## Open Questions

1. **Learn from user's past usage?** → V1 feature, track patterns
2. **Custom components not in registry?** → Include in local vector DB
3. **Suggest multi-component sub-flows?** → V1, start with single components
4. **No good suggestions?** → Fallback to "Browse all", explain why

## Dependencies

### Internal (Existing)
- **LFX run_flow**: Execute suggestion flow template
- **MCP Tools**: visualize_flow_graph, search_components, get_flow_component_details
- **Component Registry**: Source of truth for components
- **Frontend Canvas API**: Add/connect components (WIP - Phase 3)

### External Services
- **OpenAI API**: LLM for ranking and explanations (user-provided key)
- **Astra DB**: Vector database for templates and components

### Vector Search (New)
- **Embedding Model**: text-embedding-3-small 
- **OSS**: FAISS or Chroma library bundled with installation
- **Registered**: Astra DB Python SDK + network connectivity
- **Template Database**: Flow templates with text representations (new artifact to create)

## Acceptance Criteria

1. Template + component vector databases operational (Astra + OSS)
2. Two-stage vector search returns contextually relevant results
3. API endpoint returns 3-5 ranked suggestions with confidence scores
4. Flow patterns recognized from template matches
5. UI allows one-click add from suggestions panel
6. Response time <3 seconds for 95% of requests
7. 50%+ acceptance rate in user testing
8. Analytics tracking acceptance/rejection

## Related Documentation

Part of Langflow Assistant suite: Langflow Assistant Overview, Prompt Generation PRD, Vibe Flow PRD, Custom Component Generation PRD

---

**Document Version**: 1.0  
**Last Updated**: January 2026  
**Status**: Planning - Template-Based Two-Stage Vector Search  
**Owner**: Langflow Engineering Team

