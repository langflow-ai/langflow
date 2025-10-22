# Genesis Agent Specifications Library

A comprehensive library of agent specifications, patterns, and documentation for building AI agents in the Genesis platform.

## Quick Start

### For Beginners
1. **Read the Basics**: Start with [Getting Started Guide](documentation/guides/creating-specifications.md)
2. **Choose a Pattern**: Browse [Pattern Catalog](documentation/patterns/pattern-catalog.md)
3. **Study Examples**: Look at `agents/simple/` for basic examples
4. **Create Your First Spec**: Follow the step-by-step guide

### For Experienced Users
1. **Browse Patterns**: Check [Pattern Catalog](documentation/patterns/pattern-catalog.md) for advanced patterns
2. **Component Reference**: Use [Component Catalog](documentation/components/component-catalog.md) for detailed configs
3. **Schema Reference**: See [Specification Schema](documentation/schema/specification-schema.md) for complete field reference

## Library Structure

```
specifications_library/
├── agents/                     # Healthcare agent specifications by pattern
│   ├── simple/                 # Basic linear agents (3 components)
│   ├── prompted/               # Agents with external prompts
│   ├── single-tool/            # Agents with one tool
│   ├── multi-tool/             # Agents with multiple tools
│   ├── patient-experience/     # Patient-focused agents
│   └── enterprise/             # Full production metadata
├── documentation/              # Complete documentation
│   ├── schema/                 # YAML schema reference
│   ├── components/             # Component type documentation
│   ├── patterns/               # Architectural patterns
│   ├── guides/                 # How-to guides
│   └── reference/              # API and conversion reference
└── README.md                   # This file
```

## Current Specifications (17)

### By Complexity
- **Simple (3-4 components)**: `document-processor`, `classification-agent`, `medication-extractor`
- **Medium (4-6 components)**: `benefit-check-agent`, `clinical-processing-agent`, `guideline-retrieval-agent`
- **Complex (6+ components)**: `accumulator-check-agent`, `eligibility-checker`, `extraction-agent`, `appointment-concierge-agent`, `virtual-health-navigator-agent`

### By Use Case
- **Document Processing**: `document-processor`, `attach-document-agent`
- **Classification**: `classification-agent`
- **Healthcare Analysis**: `accumulator-check-agent`, `benefit-check-agent`, `eligibility-checker`
- **Clinical Support**: `guideline-check-agent`, `guideline-retrieval-agent`, `clinical-processing-agent`
- **Data Extraction**: `extraction-agent`, `medication-extractor`
- **Patient Experience**: `post-visit-qa-agent`, `patient-feedback-analyzer-agent`, `appointment-concierge-agent`, `virtual-health-navigator-agent`

## Component Types Available

| Component | Purpose | Use Case |
|-----------|---------|----------|
| `genesis:chat_input` | User input | Accept requests, documents, data |
| `genesis:chat_output` | Display results | Show processed outputs |
| `genesis:agent` | LLM processing | Main agent logic and decision making |
| `genesis:prompt` | Prompt management | Complex, reusable prompts |
| `genesis:mcp_tool` | External APIs | Database queries, calculations, APIs |
| `genesis:knowledge_hub_search` | Internal search | Policy lookup, guideline retrieval |

## Architectural Patterns

### 1. Simple Linear Agent (3 components)
```
Input → Agent → Output
```
**Best for**: Classification, basic processing, prototypes
**Examples**: `document-processor.yaml`, `classification-agent.yaml`

### 2. Agent with External Prompt (4 components)
```
Input → Agent ← Prompt Template
        ↓
      Output
```
**Best for**: Complex prompts, prompt versioning
**Examples**: `guideline-retrieval-agent.yaml`

### 3. Agent with Single Tool (4-5 components)
```
Input → Agent → Output
        ↑
      Tool
```
**Best for**: External data access, API integration
**Examples**: `benefit-check-agent.yaml`

### 4. Multi-Tool Agent (6+ components)
```
Input → Agent → Output
        ↑
Multiple Tools + Prompt
```
**Best for**: Complex workflows, multiple data sources
**Examples**: `accumulator-check-agent.yaml`

### 5. Enterprise Agent (Variable)
Any pattern + comprehensive metadata for production use
**Examples**: `accumulator-check-agent.yaml`, `guideline-retrieval-agent.yaml`

## Documentation Index

### Essential Reading
- **[Creating Specifications](documentation/guides/creating-specifications.md)** - Step-by-step creation guide
- **[Pattern Catalog](documentation/patterns/pattern-catalog.md)** - Architectural patterns with examples
- **[Component Catalog](documentation/components/component-catalog.md)** - Complete component reference

### Reference Documentation
- **[Specification Schema](documentation/schema/specification-schema.md)** - Complete YAML schema
- **[Field Reference](documentation/schema/field-reference.md)** - Searchable field catalog

### Advanced Topics
- **[Conversion Guide](documentation/guides/conversion-guide.md)** - How specs become flows
- **[Best Practices](documentation/guides/best-practices.md)** - Production guidelines
- **[Troubleshooting](documentation/guides/troubleshooting.md)** - Common issues

## Getting Help

### Common Questions

**Q: Which pattern should I use?**
A: Start with Simple Linear Agent. Add tools if you need external data. Use Enterprise pattern for production.

**Q: How do I connect components?**
A: Use the `provides` array to define connections. See [Component Catalog](documentation/components/component-catalog.md) for connection types.

**Q: What's the difference between inline prompts and prompt templates?**
A: Use inline prompts for simple cases. Use templates for complex prompts, versioning, or reuse across agents.

**Q: How do I add external tools?**
A: Use `genesis:mcp_tool` for APIs/databases or `genesis:knowledge_hub_search` for internal search.

### Need More Help?
1. Check the [Troubleshooting Guide](documentation/guides/troubleshooting.md)
2. Study similar examples in the `agents/` directory
3. Review the [complete documentation](documentation/)

## Examples by Use Case

### Document Processing
```bash
# Simple document processing
agents/simple/document-processor.yaml

# Document classification
agents/simple/classification-agent.yaml

# Advanced document handling
agents/multi-tool/attach-document-agent.yaml
```

### Healthcare/Benefits Analysis
```bash
# Benefit checking with single tool
agents/single-tool/benefit-check-agent.yaml

# Complex accumulator analysis
agents/multi-tool/accumulator-check-agent.yaml

# Eligibility verification
agents/multi-tool/eligibility-checker.yaml
```

### Knowledge Retrieval
```bash
# Guideline search with knowledge hub
agents/prompted/guideline-retrieval-agent.yaml

# Complex guideline checking
agents/multi-tool/guideline-check-agent.yaml
```

### Data Extraction
```bash
# Simple medication extraction
agents/simple/medication-extractor.yaml

# Advanced data extraction
agents/multi-tool/extraction-agent.yaml
```

## Quick Templates

### Basic Agent Template
```yaml
name: "Your Agent Name"
description: "What your agent does"
version: "1.0.0"
agentGoal: "Detailed objective"

components:
  - id: input
    type: genesis:chat_input
    name: "Input"
    description: "User input"
    provides:
      - in: agent
        useAs: input
        description: "Send to agent"

  - id: agent
    type: genesis:agent
    name: "Processing Agent"
    description: "Main logic"
    config:
      system_prompt: "You are a helpful assistant..."
      temperature: 0.1
      max_tokens: 1000
    provides:
      - in: output
        useAs: input
        description: "Send results"

  - id: output
    type: genesis:chat_output
    name: "Results"
    description: "Display results"
```

### Agent with Tool Template
```yaml
# Add after basic template components:
  - id: tool
    type: genesis:mcp_tool  # or genesis:knowledge_hub_search
    name: "Tool Name"
    description: "Tool purpose"
    asTools: true
    config:
      tool_name: tool_identifier
      description: "When and how to use this tool"
    provides:
      - useAs: tools
        in: agent
        description: "Provide tool capability"
```

## Contributing

When adding new specifications to the library:

1. **Choose the right directory** based on complexity and pattern
2. **Include comprehensive metadata** for enterprise agents
3. **Add clear descriptions** for all components
4. **Follow naming conventions** (kebab-case for IDs)
5. **Test thoroughly** before adding to library
6. **Document unique patterns** if creating new architectural approaches

## Version History

- **v1.0.0**: Initial library with 13 specifications and complete documentation
- **Current**: 13 healthcare-focused agent specifications across 5 architectural patterns

---

*This library serves as the foundation for building AI agents in the Genesis platform. It provides both specific examples and reusable patterns for creating effective agent workflows.*