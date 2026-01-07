# Langflow Assistant - PRD Index & Summary

## Overview

This document serves as the central index for all Langflow Assistant Product Requirements Documents. The Langflow Assistant is an AI-powered development assistant that transforms Langflow from a visual workflow builder into an intelligent development platform.

## Document Structure

```
📁 Langflow Assistant PRDs
│
├── 📄 PRD_Langflow_Assistant.md (THIS INDEX)
│   └── Overall vision, architecture, and strategy
│
├── 📄 PRD_Prompt_Generation.md
│   └── Feature: AI-powered prompt generation for component fields
│
├── 📄 PRD_Next_Component_Suggestion.md
│   └── Feature: Intelligent next component recommendations
│
├── 📄 PRD_Vibe_Flow.md
│   └── Feature: Generate complete flows from natural language
│
└── 📄 PRD_Custom_Component_Generation.md
    └── Feature: Generate custom component code from specifications
```

## Quick Reference Matrix

| Feature | Status | Priority | API Endpoint | Flow Template | Target Release |
|---------|--------|----------|--------------|---------------|----------------|
| [Prompt Generation](#prompt-generation) | ✅ Partial | P0 | `/agentic/prompt` | `PromptGeneration.json` | Phase 1 |
| [Next Component Suggestion](#next-component-suggestion) | 🚧 API Only | P0 | `/agentic/next_component` | `NextComponentSuggestion.json` | Phase 2 |
| [Vibe Flow](#vibe-flow-prompt-to-flow) | 🎯 Design | P1 | `/agentic/flow_from_prompt` | `VibeFlow.json` | Phase 3 |
| [Custom Component Generation](#custom-component-generation) | 🎯 Design | P2 | `/agentic/generate_component` | `ComponentCodeGen.json` | Phase 4 |

### Status Legend
- ✅ Partial: Partially implemented
- 🚧 In Progress: Implementation started
- 🎯 Design: Design phase, not yet implemented

### Priority Legend
- P0: Core feature, critical for MVP
- P1: High impact, important for adoption
- P2: Enhanced feature, improves UX

## Feature Summaries

### 1. Prompt Generation

**📄 Full PRD**: [PRD_Prompt_Generation.md](./PRD_Prompt_Generation.md)

**One-liner**: Generate context-aware prompts for any text field in Langflow components.

**Problem Solved**: Users struggle with prompt engineering and writing effective prompts aligned with their flow's purpose.

**Key Capabilities**:
- Flow-context awareness (uses flow name, description, structure)
- Field-type specific formatting
- Existing value enhancement
- Custom instruction support
- Best practices automation

**User Experience**:
```
Component Field → ✨ Generate Button → Dialog (optional instructions) 
→ AI generates prompt → Preview → Accept/Refine
```

**Implementation Status**: 
- ✅ Backend API implemented
- ✅ Flow template exists
- ✅ Context gathering working
- 🚧 Frontend UI integration needed
- 🚧 Refinement flow needed

**Success Metrics**:
- 70%+ acceptance rate
- 50%+ of flows use feature
- >4.0/5.0 user satisfaction

**Estimated Cost**: $0.0002 per generation (~$2/month for 1000 users)

---

### 2. Next Component Suggestion

**📄 Full PRD**: [PRD_Next_Component_Suggestion.md](./PRD_Next_Component_Suggestion.md)

**One-liner**: AI recommends the most relevant next component to add based on flow context.

**Problem Solved**: Users overwhelmed by 200+ components, unsure which to add next or how to complete common patterns.

**Key Capabilities**:
- Flow structure analysis
- Pattern recognition (RAG, Agent, Chat, Pipeline)
- Ranked suggestions with confidence scores
- Connection guidance
- Component compatibility checking

**User Experience**:
```
Canvas → "Suggest Next Component" → AI analyzes flow 
→ Shows top 5 suggestions with reasons → One-click add & connect
```

**Implementation Status**:
- ✅ API endpoint exists
- 🚧 Flow template needed
- 🚧 Pattern recognition logic
- 🚧 Frontend UI
- 🚧 Component compatibility matrix

**Success Metrics**:
- 50%+ top suggestion acceptance
- 60%+ of flows use feature
- >4.0/5.0 relevance rating

**Estimated Cost**: $0.00047 per suggestion (~$9/month for 1000 users)

---

### 3. Vibe Flow (Prompt to Flow)

**📄 Full PRD**: [PRD_Vibe_Flow.md](./PRD_Vibe_Flow.md)

**One-liner**: Generate complete, functional flows from natural language descriptions.

**Problem Solved**: Starting from scratch is intimidating; new users don't know patterns; flow setup is time-consuming.

**Key Capabilities**:
- Natural language parsing
- Template selection or custom building
- Component selection and configuration
- Connection establishment
- Pattern implementation (RAG, Agent, etc.)
- Iterative refinement

**User Experience**:
```
"Create from Description" → User describes flow 
→ Optional clarifying questions → AI builds flow 
→ Shows explanation → User reviews and edits
```

**Implementation Status**:
- 🎯 Design phase
- 📋 API design complete
- 📋 Flow template design in progress
- 🚧 Pattern library needed
- 🚧 Flow construction service

**Success Metrics**:
- 80%+ flows executable without modification
- 30%+ of new flows created via Vibe Flow
- >4.0/5.0 satisfaction
- >10 min time saved per flow

**Estimated Cost**: $0.78-$1.35 per generation (~$3,150/month for 1000 users)

---

### 4. Custom Component Generation

**📄 Full PRD**: [PRD_Custom_Component_Generation.md](./PRD_Custom_Component_Generation.md)

**One-liner**: Generate production-quality custom component code from specifications.

**Problem Solved**: Component development requires deep Langflow knowledge; boilerplate is repetitive; API integrations are complex.

**Key Capabilities**:
- Natural language to Python code
- Pattern-based generation (data processor, API integration, etc.)
- Input/Output definition
- Error handling and logging
- Documentation generation
- Security best practices
- Code validation pipeline

**User Experience**:
```
"Generate Component" → Describe or use template 
→ AI generates code → Validation checks → Preview 
→ One-click install
```

**Implementation Status**:
- 🎯 Design phase
- 📋 Component templates defined
- 📋 Validation pipeline designed
- 🚧 Code generation logic
- 🚧 Frontend Component Studio

**Success Metrics**:
- 95%+ compilation rate
- 70%+ used without modification
- 20%+ users generate components
- >4.0/5.0 satisfaction

**Estimated Cost**: $0.74-$1.25 per generation (~$320/month for 1000 users)

---

## Technical Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Langflow UI Layer                        │
│  • Component Fields    • Canvas    • Dialogs    • Studio   │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│              Agentic API Router (/agentic)                  │
│  • POST /prompt                                             │
│  • POST /next_component                                     │
│  • POST /flow_from_prompt                                   │
│  • POST /generate_component                                 │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│              LFX run_flow Engine                            │
│  Executes assistant flows with global variables             │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│           Assistant Flow Templates                          │
│  • PromptGeneration.json                                    │
│  • NextComponentSuggestion.json                             │
│  • VibeFlow.json                                            │
│  • ComponentCodeGen.json                                    │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│                  MCP Server Tools                           │
│  Component Search  •  Flow Visualization  •  Templates      │
│  Component Fields  •  Flow Operations                       │
└─────────────────────────────────────────────────────────────┘
```

### Core Principles

1. **Flow-Based Architecture**: All assistant logic implemented as Langflow flows
2. **API-First Design**: Generic REST APIs that execute flows via LFX
3. **Context-Aware**: Deep integration with flow metadata and component schemas
4. **Extensible**: Users can customize or create new assistant flows
5. **Transparent**: Show reasoning and allow manual override

### Common Patterns

#### API Endpoint Pattern
```python
@router.post("/agentic/{feature}")
async def run_feature(
    request: FlowRequest,
    current_user: CurrentActiveUser,
    session: DbSession
) -> dict:
    # 1. Authenticate
    # 2. Gather context
    # 3. Execute flow
    # 4. Return result
```

#### Flow Template Pattern
```
ChatInput (User Instructions)
    ↓
TextInput (Context Variables)
    ↓
PromptTemplate (Combines all)
    ↓
LanguageModel (AI Processing)
    ↓
ChatOutput (Structured Result)
```

#### Context Variables
- `FLOW_ID`: Current flow identifier
- `FLOW_DETAILS`: Flow name, description, structure
- `COMPONENT_ID`: Target component (if applicable)
- `FIELD_NAME`: Target field (if applicable)
- `USER_ID`: User identifier
- `OPENAI_API_KEY`: LLM provider key

### MCP Server Tools

Available tools for assistant flows:

**Template Operations**:
- `search_templates()`: Find templates by query/tags
- `get_template()`: Get specific template by ID
- `create_flow_from_template()`: Create flow from template

**Component Operations**:
- `search_components()`: Find components by query/type
- `get_component()`: Get specific component details
- `list_component_types()`: Get all component categories

**Flow Operations**:
- `visualize_flow_graph()`: Get flow structure
- `get_flow_component_details()`: Analyze component in flow
- `get_flow_component_field_value()`: Read field value
- `update_flow_component_field()`: Modify field value
- `list_flow_component_fields()`: List all fields in component

## Implementation Roadmap

### Phase 1: Foundation (Current - Q1 2026)
**Duration**: 3 months  
**Status**: In Progress

**Goals**:
- ✅ Agentic API infrastructure
- ✅ MCP server tools
- ✅ Prompt Generation (backend)
- 🚧 Prompt Generation (frontend)
- 🚧 Documentation and examples

**Deliverables**:
- Working Prompt Generation feature
- Developer documentation
- API documentation
- Example flows

---

### Phase 2: Core Features (Q2 2026)
**Duration**: 3 months  
**Status**: Planned

**Goals**:
- Next Component Suggestion (full implementation)
- Enhanced Prompt Generation UI
- Pattern library for common workflows
- User feedback collection system

**Deliverables**:
- Working Next Component Suggestion
- Improved Prompt Generation UX
- 5+ recognized workflow patterns
- Analytics dashboard

---

### Phase 3: Advanced Features (Q3 2026)
**Duration**: 3 months  
**Status**: Planned

**Goals**:
- Vibe Flow (Prompt to Flow)
- Custom Component Generation
- Iterative refinement flows
- Personalization and learning

**Deliverables**:
- Working Vibe Flow feature
- Working Component Generation
- Refinement capabilities
- User preference system

---

### Phase 4: Ecosystem (Q4 2026)
**Duration**: Ongoing  
**Status**: Future

**Goals**:
- Community template marketplace
- Third-party integrations
- Advanced customization
- Multi-LLM provider support

**Deliverables**:
- Marketplace integration
- Plugin architecture
- Customization options
- Alternative LLM support

## Cost Summary

### Monthly Operating Costs (1000 active users)

| Feature | Avg Usage/User | Cost/Request | Monthly Total |
|---------|----------------|--------------|---------------|
| Prompt Generation | 10 requests | $0.0002 | $2.00 |
| Next Component | 20 requests | $0.0005 | $9.40 |
| Vibe Flow | 3 generations | $1.00 | $3,000.00 |
| Component Generation | 2 components | $0.90 | $360.00 |
| **TOTAL** | - | - | **$3,371.40** |

### Cost Optimization Strategies

1. **Caching**: Cache static data (components, templates) - **30% reduction**
2. **Template Reuse**: Use templates instead of LLM when possible - **50% reduction for Vibe Flow**
3. **Token Pruning**: Send only relevant context - **20% reduction**
4. **Tiered Models**: Use cheaper models for simple tasks - **40% reduction for simple requests**

**Optimized Monthly Cost**: ~$1,800 (47% savings)

## Success Metrics

### Adoption Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| % flows using assistant features | 60% | Track API usage per flow |
| Feature-specific usage rate | 40%+ | Track individual feature adoption |
| Repeat usage rate | 70% | Track users with multiple uses |

### Quality Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Suggestion acceptance rate | 70%+ | Track accept/reject in UI |
| Generated code compilation rate | 95%+ | Automatic validation |
| Flow executability rate | 80%+ | Test execution success |
| Relevance rating | >4.0/5.0 | In-app thumbs up/down |

### Impact Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Time saved per interaction | >30 sec | Session analytics |
| Reduction in empty fields | 50% | Field completion rate |
| Increase in flow completion | 30% | Flow publish rate |
| Support request reduction | 20% | Ticket volume |

### Satisfaction Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Overall satisfaction | >4.0/5.0 | In-app surveys |
| Feature-specific NPS | >40 | Quarterly surveys |
| Retention improvement | +15% | User cohort analysis |

## Security & Privacy

### API Key Management
- User API keys stored encrypted in global variables
- Keys fetched securely per request
- No logging of API keys
- Support for API key rotation

### Data Privacy
- Flow metadata shared only within user's workspace
- No external data transmission (except to configured LLM)
- Assistant flows run in user's environment
- Option to use self-hosted LLMs

### Code Security
- Generated code validated for security issues
- No hardcoded credentials
- Input sanitization patterns
- Secure secret handling (SecretStrInput)

### Rate Limiting
- Per-user rate limits on all endpoints
- Quota management for enterprise plans
- Throttling to prevent abuse

## Extensibility

### Custom Assistant Flows

Users can create custom assistant flows:

1. Build a flow with expected structure:
   - ChatInput for user input
   - TextInput for context (global variables)
   - PromptTemplate for combining
   - LanguageModel for processing
   - ChatOutput for result

2. Register flow in configuration:
   ```python
   ASSISTANT_FLOWS = {
       "custom_feature": "path/to/CustomFlow.json"
   }
   ```

3. Expose via existing API pattern:
   ```python
   @router.post("/agentic/custom_feature")
   async def run_custom_feature(...):
       return await execute_assistant_flow("custom_feature", ...)
   ```

### Plugin Architecture

Third parties can:
- Add new MCP tools
- Contribute assistant flow templates
- Extend context gathering utilities
- Integrate with external services

### Prompt Customization

Users can customize:
- System prompts in assistant flows
- Context inclusion/exclusion rules
- Output formatting preferences
- Default values and behaviors

## Open Questions

### Multi-LLM Support
**Q**: Should we support multiple LLM providers?  
**A**: Phase 4 feature - start with OpenAI, add Anthropic, Groq, local models

**Status**: Deferred to Phase 4

### Offline Mode
**Q**: Can we provide assistance without LLM calls?  
**A**: Investigate template-based fallbacks and rule-based suggestions

**Status**: Research needed

### Telemetry
**Q**: What usage data should we collect?  
**A**: Opt-in telemetry for feature usage, acceptance rates, error rates

**Status**: Privacy policy needed

### Versioning
**Q**: How do we handle assistant flow template updates?  
**A**: Version flows, allow users to pin versions or auto-update

**Status**: Design in progress

### Localization
**Q**: Should assistant responses be localized?  
**A**: LLM naturally supports multilingual, test with non-English users

**Status**: Testing required

## Dependencies

### Internal (LangFlow)
- ✅ LFX run_flow engine
- ✅ Component schema registry
- ✅ Template storage system
- ✅ User authentication
- ✅ Global variables service
- 🚧 Flow construction service
- 🚧 Component installation service

### External Services
- ✅ OpenAI API
- 🚧 FastMCP framework
- 🚧 Analytics service
- Future: Anthropic API
- Future: Groq API

### Frontend
- 🚧 React components
- 🚧 Canvas API
- 🚧 Code editor
- 🚧 Diff viewer

## Getting Started

### For Users

1. **Prerequisites**:
   - Langflow installed and running
   - OpenAI API key configured in Global Variables

2. **Using Prompt Generation**:
   ```
   1. Open any flow
   2. Click on a text field
   3. Click "✨ Generate" button
   4. Optionally add custom instructions
   5. Review and accept generated prompt
   ```

3. **Using Next Component Suggestion** (Coming Soon):
   ```
   1. Open a flow
   2. Right-click on canvas or component
   3. Select "Suggest Next Component"
   4. Review suggestions
   5. Click "Add to Flow"
   ```

### For Developers

1. **Running the Backend**:
   ```bash
   cd src/backend/base
   python -m langflow.agentic.mcp.server
   ```

2. **Testing an Assistant Flow**:
   ```bash
   lfx run_flow \
     --script-path flows/PromptGeneration.json \
     --input-value "Make it friendly" \
     --global-variables '{"FLOW_ID":"test","OPENAI_API_KEY":"sk-..."}' \
     --verbose
   ```

3. **Adding a New MCP Tool**:
   ```python
   # In langflow/agentic/mcp/server.py
   
   @mcp.tool()
   async def my_new_tool(param: str) -> dict:
       """Tool description for LLM."""
       # Implementation
       return {"result": "..."}
   ```

4. **Creating a Custom Assistant Flow**:
   - Copy `PromptGeneration.json` as template
   - Modify components and connections
   - Update prompt template with your logic
   - Save to `flows/` directory
   - Add API endpoint to route to your flow

## Resources

### Documentation
- [Langflow Documentation](https://docs.langflow.org)
- [LFX run_flow Guide](https://docs.langflow.org/lfx/run_flow)
- [Component Development Guide](../.cursor/rules/components/basic_component.mdc)
- [Backend Development Guide](../.cursor/rules/backend_development.mdc)

### Code References
- [Agentic API Router](../src/backend/base/langflow/agentic/api/router.py)
- [MCP Server](../src/backend/base/langflow/agentic/mcp/server.py)
- [Flow Templates](../src/backend/base/langflow/agentic/flows/)
- [Utility Modules](../src/backend/base/langflow/agentic/utils/)

### Community
- GitHub Issues: Report bugs and request features
- Discord: Join #langflow-assistant channel
- Community Forum: Share custom assistant flows

## Contributing

We welcome contributions to the Langflow Assistant!

### How to Contribute

1. **Report Issues**: Use GitHub Issues for bugs and feature requests
2. **Improve Documentation**: Submit PRs for doc improvements
3. **Share Assistant Flows**: Contribute custom assistant flow templates
4. **Add MCP Tools**: Extend functionality with new tools
5. **Optimize Prompts**: Improve system prompts for better results

### Contribution Guidelines

- Follow existing code patterns
- Include tests for new features
- Update documentation
- Add examples where applicable
- Respect the Apache 2.0 license

## Appendix

### Glossary

- **Agentic API**: REST APIs for assistant features at `/agentic/*`
- **LFX**: Langflow Execution framework for running flows
- **MCP**: Model Context Protocol / FastMCP framework
- **Assistant Flow**: A Langflow flow that implements assistant logic
- **Context Variables**: Data passed to assistant flows via global variables
- **Vibe Flow**: Colloquial name for Prompt-to-Flow generation

### Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-07 | Langflow Team | Initial PRD suite |

### Contact

- **Product Owner**: [Name] (email@langflow.org)
- **Engineering Lead**: [Name] (email@langflow.org)
- **Documentation**: docs@langflow.org

---

**Last Updated**: January 7, 2026  
**Status**: Living Document  
**Review Cycle**: Quarterly

---

## Quick Links

- 📄 [Full PRD: Prompt Generation](./PRD_Prompt_Generation.md)
- 📄 [Full PRD: Next Component Suggestion](./PRD_Next_Component_Suggestion.md)
- 📄 [Full PRD: Vibe Flow](./PRD_Vibe_Flow.md)
- 📄 [Full PRD: Custom Component Generation](./PRD_Custom_Component_Generation.md)
- 💻 [Source Code: Agentic Module](../src/backend/base/langflow/agentic/)
- 📚 [User Documentation](https://docs.langflow.org/assistant)
- 🐛 [Report Issues](https://github.com/langflow-ai/langflow/issues)

