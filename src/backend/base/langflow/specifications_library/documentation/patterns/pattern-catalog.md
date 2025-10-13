# Genesis Agent Pattern Catalog

Reusable architectural patterns for building Genesis Agent specifications.

## Overview

This catalog documents common patterns found in agent specifications. Each pattern represents a proven architectural approach for specific use cases.

## Pattern Index

| Pattern | Complexity | Components | Use Cases | Best For |
|---------|------------|------------|-----------|----------|
| [Simple Linear Agent](#1-simple-linear-agent) | Simple | 3 | Basic processing, classification | Beginners, focused tasks |
| [Agent with External Prompt](#2-agent-with-external-prompt) | Simple | 4 | Complex prompts, reusability | Prompt management, versioning |
| [Agent with Single Tool](#3-agent-with-single-tool) | Medium | 4-5 | Data retrieval, API calls | External data needs |
| [Multi-Tool Agent](#4-multi-tool-agent) | Complex | 6+ | Complex workflows, multiple APIs | Advanced automation |
| [Enterprise Agent](#5-enterprise-agent) | Enterprise | Variable | Production deployments | Governance, monitoring |
| [Multi-Agent Workflow](#6-multi-agent-workflow) | Advanced | 8+ | Specialized agent collaboration | Complex problem-solving |

---

## 1. Simple Linear Agent

**Pattern**: Input → Agent → Output
**Complexity**: Simple (3 components)
**Best For**: Basic processing, classification, extraction tasks

### When to Use
- Single-step processing tasks
- Document classification
- Simple data extraction
- Prototype development
- Learning/tutorial scenarios

### Structure
```
[Chat Input] → [Agent] → [Chat Output]
```

### Components Required
1. `genesis:chat_input` - User input
2. `genesis:agent` - Processing logic
3. `genesis:chat_output` - Results display

### Template
```yaml
name: Simple Agent Template
description: Basic linear processing agent
version: "1.0.0"
agentGoal: Process input and generate output

components:
  - id: input
    type: genesis:chat_input
    name: User Input
    description: Accept user input
    provides:
      - in: agent
        useAs: input
        description: Send input to agent

  - id: agent
    type: genesis:agent
    name: Processing Agent
    description: Main processing logic
    config:
      system_prompt: |
        You are a helpful assistant. Process the user's input and provide a clear response.
      temperature: 0.1
      max_tokens: 1000
    provides:
      - in: output
        useAs: input
        description: Send results to output

  - id: output
    type: genesis:chat_output
    name: Results
    description: Display processed results
```

### Examples in Library
- `document-processor.yaml` - Document processing
- `classification-agent.yaml` - Prior authorization classification
- `medication-extractor.yaml` - Medication extraction

### Variations
- **With inline prompt**: System prompt defined in agent config
- **Different temperatures**: Adjust for creativity vs consistency
- **Specialized processing**: Custom system prompts for domain-specific tasks

---

## 2. Agent with External Prompt

**Pattern**: Input → Prompt Template → Agent → Output
**Complexity**: Simple (4 components)
**Best For**: Complex prompts, prompt management, reusability

### When to Use
- Complex, multi-paragraph prompts
- Prompt versioning and management
- Reusable prompt logic
- A/B testing different prompts
- Template-based prompt generation

### Structure
```
[Chat Input] → [Agent] ← [Prompt Template]
       ↓
[Chat Output]
```

### Components Required
1. `genesis:chat_input` - User input
2. `genesis:prompt_template` - Managed prompt
3. `genesis:agent` - Processing logic
4. `genesis:chat_output` - Results display

### Template
```yaml
name: Agent with External Prompt
description: Agent using managed prompt template
version: "1.0.0"
agentGoal: Process input using managed prompt

components:
  - id: input
    type: genesis:chat_input
    name: User Input
    description: Accept user input
    provides:
      - in: agent
        useAs: input
        description: Send input to agent

  - id: prompt
    type: genesis:prompt_template
    name: Agent Instructions
    description: Managed prompt template
    config:
      saved_prompt: template_v1
      template: |
        You are a specialist agent with the following capabilities:

        1. Analyze the provided input
        2. Apply domain-specific knowledge
        3. Generate structured output

        Follow these guidelines:
        - Be accurate and thorough
        - Use clear, professional language
        - Structure your response logically
    provides:
      - useAs: system_prompt
        in: agent
        description: Provide system prompt to agent

  - id: agent
    type: genesis:agent
    name: Processing Agent
    description: Main processing logic
    config:
      temperature: 0.1
      max_tokens: 2000
    provides:
      - in: output
        useAs: input
        description: Send results to output

  - id: output
    type: genesis:chat_output
    name: Results
    description: Display processed results
```

### Examples in Library
- `guideline-retrieval-agent.yaml` - Clinical guideline retrieval
- `accumulator-check-agent.yaml` - Benefit accumulator checking

### Benefits
- **Prompt Management**: Version and update prompts independently
- **Reusability**: Share prompts across multiple agents
- **A/B Testing**: Switch between prompt versions
- **Governance**: Centralized prompt approval process

---

## 3. Agent with Single Tool

**Pattern**: Input → Agent (with Tool) → Output
**Complexity**: Medium (4-5 components)
**Best For**: Agents needing external data or specific functionality

### When to Use
- Need to query external databases
- Require API integrations
- Search knowledge bases
- Perform calculations
- Access real-time data

### Structure
```
[Chat Input] → [Agent] → [Chat Output]
                 ↑
              [Tool]
```

### Components Required
1. `genesis:chat_input` - User input
2. `genesis:agent` - Processing logic with tool access
3. `genesis:mcp_tool` OR `genesis:knowledge_hub_search` - External capability
4. `genesis:chat_output` - Results display
5. Optional: `genesis:prompt_template` - Complex prompts

### Template
```yaml
name: Single Tool Agent
description: Agent with one external tool
version: "1.0.0"
agentGoal: Process input using external tool capability

components:
  - id: input
    type: genesis:chat_input
    name: User Input
    description: Accept user input
    provides:
      - in: agent
        useAs: input
        description: Send input to agent

  - id: tool
    type: genesis:mcp_tool  # or genesis:knowledge_hub_search
    name: External Tool
    description: Provides external data access
    asTools: true
    config:
      tool_name: example_tool
      description: Example tool for data access
    provides:
      - useAs: tools
        in: agent
        description: Provide tool capability to agent

  - id: agent
    type: genesis:agent
    name: Processing Agent
    description: Agent with tool access
    config:
      system_prompt: |
        You are an agent with access to external tools.
        Use the available tool to gather information and provide comprehensive responses.
      temperature: 0.1
      max_tokens: 2000
    provides:
      - in: output
        useAs: input
        description: Send results to output

  - id: output
    type: genesis:chat_output
    name: Results
    description: Display processed results
```

### Tool Types

#### MCP Tools (`genesis:mcp_tool`)
For external APIs, databases, services:
```yaml
- id: api-tool
  type: genesis:mcp_tool
  config:
    tool_name: claims_api
    description: Access claims database
    # Tool-specific parameters
```

#### Knowledge Hub Search (`genesis:knowledge_hub_search`)
For internal knowledge base search:
```yaml
- id: knowledge-tool
  type: genesis:knowledge_hub_search
  name: Knowledge Search
  description: Search internal knowledge base
  asTools: true
```

### Examples in Library
- `guideline-retrieval-agent.yaml` - With knowledge hub search
- `benefit-check-agent.yaml` - With benefit calculation tool

---

## 4. Multi-Tool Agent

**Pattern**: Input → Prompt → Agent (with Multiple Tools) → Output
**Complexity**: Complex (6+ components)
**Best For**: Complex workflows requiring multiple data sources

### When to Use
- Complex business processes
- Multiple data source integration
- Multi-step workflows
- Decision-making with various inputs
- Comprehensive analysis tasks

### Structure
```
[Chat Input] → [Agent] → [Chat Output]
                 ↑
    [Prompt] + [Tool1] + [Tool2] + [Tool3]
```

### Components Required
1. `genesis:chat_input` - User input
2. `genesis:prompt_template` - Complex workflow prompt
3. `genesis:agent` - Orchestrating agent
4. Multiple `genesis:mcp_tool` - Various external capabilities
5. `genesis:chat_output` - Results display

### Template
```yaml
name: Multi-Tool Agent
description: Agent orchestrating multiple tools
version: "1.0.0"
agentGoal: Complex workflow using multiple tools

components:
  - id: input
    type: genesis:chat_input
    name: User Input
    description: Accept user input
    provides:
      - in: agent
        useAs: input
        description: Send input to agent

  - id: prompt
    type: genesis:prompt_template
    name: Workflow Instructions
    description: Complex workflow prompt
    config:
      template: |
        You are a workflow orchestrator with access to multiple tools:

        1. Tool1: Use for data retrieval
        2. Tool2: Use for calculations
        3. Tool3: Use for validation

        Follow this workflow:
        1. Gather data using appropriate tools
        2. Analyze and cross-reference information
        3. Provide comprehensive recommendations
    provides:
      - useAs: system_prompt
        in: agent
        description: Provide workflow instructions

  - id: tool1
    type: genesis:mcp_tool
    name: Data Retrieval Tool
    description: Retrieve data from external source
    asTools: true
    config:
      tool_name: data_retrieval
      description: Data access tool
    provides:
      - useAs: tools
        in: agent
        description: Data retrieval capability

  - id: tool2
    type: genesis:mcp_tool
    name: Calculation Tool
    description: Perform calculations
    asTools: true
    config:
      tool_name: calculator
      description: Calculation tool
    provides:
      - useAs: tools
        in: agent
        description: Calculation capability

  - id: tool3
    type: genesis:mcp_tool
    name: Validation Tool
    description: Validate results
    asTools: true
    config:
      tool_name: validator
      description: Validation tool
    provides:
      - useAs: tools
        in: agent
        description: Validation capability

  - id: agent
    type: genesis:agent
    name: Orchestrator Agent
    description: Orchestrates workflow using multiple tools
    config:
      temperature: 0.1
      max_tokens: 3000
      max_iterations: 8
    provides:
      - in: output
        useAs: input
        description: Send results to output

  - id: output
    type: genesis:chat_output
    name: Results
    description: Display comprehensive results
```

### Examples in Library
- `accumulator-check-agent.yaml` - 3 MCP tools for benefit analysis
- `eligibility-checker.yaml` - Multiple validation tools
- `extraction-agent.yaml` - Multiple extraction tools

### Best Practices
- **Tool Organization**: Group related tools logically
- **Error Handling**: Configure `handle_parsing_errors: true`
- **Iterations**: Set `max_iterations` for complex workflows
- **Clear Instructions**: Specify when to use each tool
- **Workflow Steps**: Define clear process in prompt

---

## 5. Enterprise Agent

**Pattern**: Any of the above + Comprehensive Metadata
**Complexity**: Enterprise (Variable components)
**Best For**: Production deployments requiring governance

### When to Use
- Production environments
- Regulated industries
- Compliance requirements
- Team collaboration
- Performance monitoring
- Audit trails

### Additional Metadata Required
```yaml
# Identity and Ownership
id: urn:agent:genesis:domain:agent_name:1
fullyQualifiedName: genesis.domain.agent_name
domain: company.domain
subDomain: team-area
agentOwner: team@company.com
agentOwnerDisplayName: Team Name
email: team@company.com
status: ACTIVE

# Classification
kind: Single Agent
targetUser: internal
valueGeneration: ProcessAutomation
interactionMode: RequestResponse
runMode: RealTime
agencyLevel: KnowledgeDrivenWorkflow
toolsUse: true
learningCapability: None

# Configuration Management
variables:
  - name: llm_provider
    type: string
    required: false
    default: Azure OpenAI
    description: LLM provider

# Monitoring and KPIs
kpis:
  - name: Accuracy
    category: Quality
    valueType: percentage
    target: 95
    unit: '%'
    description: Response accuracy

# Security and Compliance
securityInfo:
  visibility: Private
  confidentiality: High
  gdprSensitive: true

# Reusability
reusability:
  asTools: true
  standalone: true
  provides:
    toolName: AgentName
    toolDescription: Description
    inputSchema: {...}
    outputSchema: {...}

# Testing and Examples
sampleInput:
  field1: example_value
  field2: example_value

# Documentation
outputs:
  - result_type1
  - result_type2

tags:
  - domain
  - classification
  - purpose
```

### Examples in Library
- `accumulator-check-agent.yaml` - Full enterprise metadata
- `guideline-retrieval-agent.yaml` - Production-ready agent

### Enterprise Benefits
- **Governance**: Clear ownership and approval processes
- **Monitoring**: KPIs and performance tracking
- **Security**: Classification and access controls
- **Reusability**: Tool interface for other agents
- **Compliance**: Audit trails and documentation
- **Configuration**: Environment-specific variables

---

## 6. Multi-Agent Workflow

**Pattern**: Input → Coordination → Multiple Specialized Agents → Output
**Complexity**: Advanced (8+ components)
**Best For**: Complex problem-solving requiring specialized agent collaboration

### When to Use
- Complex workflows requiring multiple specializations
- Tasks that benefit from agent expertise division
- Sequential processing with specialized handoffs
- Hierarchical decision-making processes
- Problems requiring research, analysis, and synthesis

### Structure

#### Sequential Multi-Agent
```
[Chat Input] → [Sequential Crew] → [Chat Output]
                      ↓
    [Researcher Agent] → [Analyst Agent] → [Synthesizer Agent]
           ↑                 ↑                    ↑
    [Research Tools]  [Analysis Tools]  [Formatting Tools]
```

#### Hierarchical Multi-Agent
```
[Chat Input] → [Hierarchical Crew] → [Chat Output]
                      ↓
         [Manager Agent (GPT-4)]
                ↓         ↓
    [Specialist 1]  [Specialist 2]  [Specialist 3]
         ↑              ↑               ↑
   [Domain Tools]  [Domain Tools]  [Domain Tools]
```

### Components Required

#### CrewAI-Based Implementation
1. `genesis:chat_input` - User input
2. `genesis:sequential_crew` OR `genesis:hierarchical_crew` - Coordination
3. Multiple `genesis:crewai_agent` - Specialized agents
4. `genesis:sequential_task` OR `genesis:hierarchical_task` - Task definitions
5. Multiple `genesis:mcp_tool` OR `genesis:knowledge_hub_search` - Specialized tools
6. `genesis:chat_output` - Results display

#### Flow-Based Implementation
1. `genesis:chat_input` - User input
2. `genesis:conditional_router` - Route to appropriate agent
3. Multiple `genesis:agent` - Specialized agents
4. `genesis:sub_flow` - Sub-workflows for complex agents
5. Tools and prompts per agent
6. `genesis:chat_output` - Results display

### CrewAI Template

```yaml
name: Multi-Agent Research Workflow
description: Collaborative agents for complex research and analysis
version: "1.0.0"
agentGoal: Conduct comprehensive research and analysis using specialized agent collaboration

kind: Multi Agent
toolsUse: true
agencyLevel: CollaborativeWorkflow

components:
  - id: input
    type: genesis:chat_input
    name: Research Request
    description: User research question or topic
    provides:
      - in: crew-coordinator
        useAs: input
        description: Send request to crew

  - id: crew-coordinator
    type: genesis:sequential_crew
    name: Research Crew
    description: Coordinates research workflow
    config:
      process: sequential
      verbose: true
      memory: true
      max_rpm: 100
    provides:
      - in: output
        useAs: input
        description: Send final results

  - id: researcher-agent
    type: genesis:crewai_agent
    name: Research Specialist
    description: Conducts initial research and data gathering
    config:
      role: "Senior Research Analyst"
      goal: "Gather comprehensive information on the given topic"
      backstory: "You are an experienced researcher with expertise in finding reliable sources and extracting key insights."
      memory: true
      verbose: true
      allow_delegation: false
    provides:
      - in: crew-coordinator
        useAs: agents
        description: Provide research capability

  - id: analyst-agent
    type: genesis:crewai_agent
    name: Data Analyst
    description: Analyzes and synthesizes research findings
    config:
      role: "Senior Data Analyst"
      goal: "Analyze research data and identify patterns and insights"
      backstory: "You are a skilled analyst who excels at finding patterns in data and drawing meaningful conclusions."
      memory: true
      verbose: true
      allow_delegation: false
    provides:
      - in: crew-coordinator
        useAs: agents
        description: Provide analysis capability

  - id: synthesizer-agent
    type: genesis:crewai_agent
    name: Content Synthesizer
    description: Creates final comprehensive report
    config:
      role: "Content Strategist"
      goal: "Synthesize research and analysis into clear, actionable insights"
      backstory: "You are an expert at taking complex information and presenting it in clear, compelling formats."
      memory: true
      verbose: true
      allow_delegation: false
    provides:
      - in: crew-coordinator
        useAs: agents
        description: Provide synthesis capability

  - id: research-tools
    type: genesis:knowledge_hub_search
    name: Research Database
    description: Access to research databases and knowledge base
    asTools: true
    provides:
      - in: researcher-agent
        useAs: tools
        description: Provide research tools

  - id: analysis-tools
    type: genesis:mcp_tool
    name: Analysis Engine
    description: Data analysis and statistical tools
    asTools: true
    config:
      tool_name: analysis_engine
      description: Statistical analysis and data processing tools
    provides:
      - in: analyst-agent
        useAs: tools
        description: Provide analysis tools

  - id: research-task
    type: genesis:sequential_task
    name: Research Task
    description: Initial research and data gathering
    config:
      description: "Research the given topic thoroughly, gathering information from reliable sources"
      expected_output: "Comprehensive research summary with key findings and sources"
      agent: researcher-agent
    provides:
      - in: crew-coordinator
        useAs: tasks
        description: Define research task

  - id: analysis-task
    type: genesis:sequential_task
    name: Analysis Task
    description: Analyze research findings
    config:
      description: "Analyze the research findings and identify key patterns, trends, and insights"
      expected_output: "Detailed analysis with conclusions and recommendations"
      agent: analyst-agent
    provides:
      - in: crew-coordinator
        useAs: tasks
        description: Define analysis task

  - id: synthesis-task
    type: genesis:sequential_task
    name: Synthesis Task
    description: Create final report
    config:
      description: "Synthesize research and analysis into a comprehensive, actionable report"
      expected_output: "Final report with executive summary, findings, and recommendations"
      agent: synthesizer-agent
    provides:
      - in: crew-coordinator
        useAs: tasks
        description: Define synthesis task

  - id: output
    type: genesis:chat_output
    name: Research Report
    description: Final comprehensive research report
    config:
      should_store_message: true
```

### Hierarchical Template

```yaml
name: Hierarchical Support Workflow
description: Manager-led agent team for complex customer support
version: "1.0.0"
agentGoal: Provide expert customer support through hierarchical agent coordination

kind: Multi Agent
toolsUse: true
agencyLevel: HierarchicalWorkflow

components:
  - id: input
    type: genesis:chat_input
    name: Support Request
    description: Customer support inquiry
    provides:
      - in: support-crew
        useAs: input
        description: Send request to support team

  - id: support-crew
    type: genesis:hierarchical_crew
    name: Support Team
    description: Hierarchical support team with manager oversight
    config:
      process: hierarchical
      verbose: true
      memory: true
      manager_llm: "gpt-4"
    provides:
      - in: output
        useAs: input
        description: Send support response

  - id: manager-agent
    type: genesis:crewai_agent
    name: Support Manager
    description: Manages support team and handles complex escalations
    config:
      role: "Customer Support Manager"
      goal: "Ensure customer issues are resolved efficiently and effectively"
      backstory: "Experienced support manager with expertise in team coordination and complex issue resolution"
      memory: true
      verbose: true
      allow_delegation: true
    provides:
      - in: support-crew
        useAs: manager_agent
        description: Provide management oversight

  - id: technical-agent
    type: genesis:crewai_agent
    name: Technical Specialist
    description: Handles technical support issues
    config:
      role: "Technical Support Specialist"
      goal: "Resolve technical issues and provide expert guidance"
      backstory: "Technical expert with deep product knowledge and troubleshooting skills"
      memory: true
      verbose: true
    provides:
      - in: support-crew
        useAs: agents
        description: Provide technical expertise

  - id: billing-agent
    type: genesis:crewai_agent
    name: Billing Specialist
    description: Handles billing and account issues
    config:
      role: "Billing Support Specialist"
      goal: "Resolve billing inquiries and account issues"
      backstory: "Billing expert with knowledge of payment systems and account management"
      memory: true
      verbose: true
    provides:
      - in: support-crew
        useAs: agents
        description: Provide billing expertise

  - id: output
    type: genesis:chat_output
    name: Support Response
    description: Comprehensive support response
    config:
      should_store_message: true
```

### Best Practices

#### Agent Design
1. **Clear Role Definition**: Each agent should have a specific, well-defined role
2. **Complementary Skills**: Agents should have complementary rather than overlapping capabilities
3. **Tool Specialization**: Assign tools that match each agent's expertise
4. **Model Selection**: Use appropriate models (GPT-4 for managers, GPT-3.5 for specialists)

#### Coordination Strategy
1. **Sequential for Handoffs**: Use sequential crews for linear workflows
2. **Hierarchical for Complex Decisions**: Use hierarchical crews for complex decision-making
3. **Clear Task Definitions**: Define specific, measurable tasks for each agent
4. **Output Specifications**: Specify expected outputs for each task

#### Performance Optimization
1. **Memory Management**: Enable memory for context retention across agents
2. **Tool Efficiency**: Assign minimal necessary tools to each agent
3. **Rate Limiting**: Configure appropriate rate limits for API calls
4. **Caching**: Enable caching for repeated operations

### Common Use Cases

#### Research and Analysis
- Market research with multiple data sources
- Academic research with literature review
- Business intelligence gathering
- Competitive analysis

#### Customer Support
- Multi-tier support with escalation
- Domain-specific support routing
- Complex issue resolution
- Knowledge base maintenance

#### Content Creation
- Research → Writing → Editing → Publishing
- Multi-language content creation
- Brand consistency across content
- Technical documentation

#### Decision Making
- Multi-criteria decision analysis
- Risk assessment workflows
- Compliance verification
- Strategic planning

### Component Mapping Requirements

**New Mappings Needed:**
```
WARNING - NEW MAPPING REQUIRED

Components needing spec mappers:
1. genesis:crewai_agent → CrewAIAgentComponent
2. genesis:sequential_task → SequentialTaskComponent
3. genesis:hierarchical_task → HierarchicalTaskComponent
4. genesis:sequential_task_agent → SequentialTaskAgentComponent

Location: /Users/jagveersingh/Developer/studio/ai-studio/src/backend/base/langflow/components/crewai/
```

### Validation Checklist

- [ ] Each agent has unique, specific role
- [ ] Tasks are clearly defined with expected outputs
- [ ] Coordination mechanism is appropriate (sequential vs hierarchical)
- [ ] Tools are properly assigned to relevant agents
- [ ] Memory and verbose settings are consistent
- [ ] Rate limiting and performance settings are configured
- [ ] Agent collaboration pattern is clearly documented

---

## Pattern Selection Guide

### Decision Tree

```
Do you need external data or tools?
├─ No → Simple Linear Agent
└─ Yes
   ├─ One tool → Agent with Single Tool
   └─ Multiple tools → Multi-Tool Agent

Is your prompt complex or reusable?
├─ Yes → Add External Prompt Pattern
└─ No → Use inline prompt

Is this for production use?
├─ Yes → Add Enterprise metadata
└─ No → Basic pattern is sufficient
```

### Complexity Progression
1. **Start Simple**: Begin with Simple Linear Agent
2. **Add Capability**: Progress to Single Tool Agent
3. **Increase Complexity**: Move to Multi-Tool Agent
4. **Production Ready**: Add Enterprise metadata

### Common Combinations
- **Simple + External Prompt**: Good for prompt experimentation
- **Single Tool + Enterprise**: Production agent with one integration
- **Multi-Tool + Enterprise**: Complex production workflow
- **Any Pattern + Prompt Template**: Better prompt management

## Next Steps

1. **Choose Your Pattern**: Use the decision tree above
2. **Start with Template**: Copy appropriate template
3. **Customize Components**: Modify for your specific use case
4. **Add Metadata**: Include enterprise fields if needed
5. **Test and Iterate**: Validate with sample inputs
6. **Deploy**: Convert to flow and deploy

See [Creating Specifications Guide](../guides/creating-specifications.md) for detailed implementation steps.