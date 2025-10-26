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
| [Healthcare Integration](#7-healthcare-integration) | Healthcare | 4-8 | Healthcare system integration | Medical workflows, HIPAA compliance |
| [Multi-Connector Healthcare](#8-multi-connector-healthcare) | Healthcare | 8+ | Complex healthcare orchestration | End-to-end healthcare automation |
| [HIPAA Compliance](#9-hipaa-compliance) | Healthcare | Variable | Secure healthcare data handling | PHI protection, audit requirements |
| [Clinical Workflow](#10-clinical-workflow) | Healthcare | 6+ | Clinical decision support | Evidence-based healthcare |

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
2. `genesis:prompt` - Managed prompt
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
    type: genesis:prompt
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
5. Optional: `genesis:prompt` - Complex prompts

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
2. `genesis:prompt` - Complex workflow prompt
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
    type: genesis:prompt
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

## 7. Healthcare Integration

**Pattern**: Input → Healthcare Connector → Agent → Output
**Complexity**: Healthcare (4-8 components)
**Best For**: Healthcare system integration, medical workflows, HIPAA-compliant data processing

### When to Use
- Integration with EHR, claims, eligibility, or pharmacy systems
- HIPAA-compliant healthcare data processing
- Clinical workflow automation
- Healthcare decision support systems
- Medical record processing and analysis
- Patient journey automation

### Structure
```
[Chat Input] → [Agent] → [Chat Output]
                 ↑
     [Healthcare Connector]
```

### Components Required
1. `genesis:chat_input` - Healthcare data input
2. `genesis:healthcare_connector` - EHR, Claims, Eligibility, or Pharmacy connector
3. `genesis:agent` - Healthcare processing logic
4. `genesis:chat_output` - Clinical results display
5. Optional: `genesis:prompt` - Clinical prompt management

### Template

```yaml
name: Healthcare Integration Agent
description: Agent with healthcare system integration
version: "1.0.0"
agentGoal: Process healthcare data using integrated healthcare systems

# Healthcare-specific metadata
domain: autonomize.ai
subDomain: healthcare-integration
targetUser: internal
valueGeneration: ProcessAutomation
securityInfo:
  visibility: Private
  confidentiality: High
  gdprSensitive: true

components:
  - id: patient-input
    type: genesis:chat_input
    name: Patient Data Input
    description: Accept patient information for processing
    provides:
      - in: healthcare-agent
        useAs: input
        description: Send patient data to healthcare agent

  - id: ehr-connector
    type: genesis:ehr_connector
    name: EHR System Integration
    description: Retrieve patient data from EHR system
    asTools: true
    config:
      ehr_system: epic
      fhir_version: R4
      authentication_type: oauth2
      base_url: "${EHR_BASE_URL}"
      operation: get_patient_data
    provides:
      - useAs: tools
        in: healthcare-agent
        description: Provide EHR data access

  - id: healthcare-agent
    type: genesis:agent
    name: Clinical Processing Agent
    description: Process patient data with EHR integration
    config:
      system_prompt: |
        You are a healthcare integration specialist with access to EHR systems.

        Your responsibilities:
        1. Retrieve patient data from EHR systems
        2. Process clinical information following HIPAA guidelines
        3. Provide comprehensive healthcare analysis
        4. Maintain data security and patient privacy

        Always:
        - Protect patient PHI (Protected Health Information)
        - Follow clinical best practices
        - Provide evidence-based recommendations
        - Log all data access for audit compliance
      temperature: 0.1
      max_tokens: 2000
      handle_parsing_errors: true
    provides:
      - in: clinical-output
        useAs: input
        description: Send processed clinical results

  - id: clinical-output
    type: genesis:chat_output
    name: Clinical Results
    description: Display processed healthcare information
    config:
      should_store_message: true
```

### Healthcare Connector Variations

#### EHR Integration
```yaml
- id: ehr-connector
  type: genesis:ehr_connector
  config:
    ehr_system: epic
    operation: get_patient_data
```

#### Claims Processing
```yaml
- id: claims-connector
  type: genesis:claims_connector
  config:
    clearinghouse: change_healthcare
    operation: submit_claim
```

#### Eligibility Verification
```yaml
- id: eligibility-connector
  type: genesis:eligibility_connector
  config:
    eligibility_service: availity
    operation: verify_eligibility
```

#### Pharmacy Integration
```yaml
- id: pharmacy-connector
  type: genesis:pharmacy_connector
  config:
    pharmacy_network: surescripts
    operation: send_prescription
```

---

## 8. Multi-Connector Healthcare

**Pattern**: Input → Multiple Healthcare Connectors → Agent → Output
**Complexity**: Healthcare (8+ components)
**Best For**: Complex healthcare orchestration, end-to-end healthcare automation, comprehensive patient workflows

### When to Use
- End-to-end patient journey automation
- Complex healthcare workflows requiring multiple system integrations
- Revenue cycle management
- Comprehensive clinical decision support
- Multi-system healthcare data aggregation
- Complete patient care coordination

### Structure
```
[Chat Input] → [Healthcare Agent] → [Chat Output]
                        ↑
    [EHR] + [Claims] + [Eligibility] + [Pharmacy]
```

### Components Required
1. `genesis:chat_input` - Patient data input
2. `genesis:prompt` - Healthcare workflow prompt
3. `genesis:ehr_connector` - Electronic health records
4. `genesis:claims_connector` - Claims processing
5. `genesis:eligibility_connector` - Insurance verification
6. `genesis:pharmacy_connector` - Medication management
7. `genesis:agent` - Healthcare orchestration agent
8. `genesis:chat_output` - Comprehensive results

### Template

```yaml
name: Multi-Connector Healthcare Orchestration
description: Comprehensive healthcare workflow with multiple system integrations
version: "1.0.0"
agentGoal: Orchestrate complete healthcare workflow from patient data to billing

# Enterprise healthcare metadata
domain: autonomize.ai
subDomain: healthcare-orchestration
kind: Single Agent
targetUser: internal
valueGeneration: ProcessAutomation
interactionMode: RequestResponse
runMode: RealTime
agencyLevel: KnowledgeDrivenWorkflow
toolsUse: true

# HIPAA compliance
securityInfo:
  visibility: Private
  confidentiality: High
  gdprSensitive: true

components:
  - id: patient-input
    type: genesis:chat_input
    name: Patient Workflow Input
    description: Accept patient information for comprehensive processing
    provides:
      - in: orchestration-agent
        useAs: input
        description: Send patient data to orchestration agent

  - id: healthcare-prompt
    type: genesis:prompt
    name: Healthcare Orchestration Instructions
    description: Comprehensive healthcare workflow prompt
    config:
      template: |
        You are a healthcare workflow orchestrator with access to multiple healthcare systems:

        1. EHR System: Patient clinical data and medical history
        2. Claims System: Billing and prior authorization processing
        3. Eligibility System: Insurance verification and benefits
        4. Pharmacy System: Medication management and e-prescribing

        Healthcare Workflow Process:
        1. Patient Data Retrieval: Use EHR connector to get comprehensive patient information
        2. Insurance Verification: Use eligibility connector to verify coverage and benefits
        3. Clinical Assessment: Analyze patient data for clinical decision support
        4. Medication Management: Use pharmacy connector for drug interactions and prescriptions
        5. Billing Coordination: Use claims connector for billing and prior authorization

        HIPAA Compliance Requirements:
        - Protect all PHI (Protected Health Information)
        - Log all system access for audit trails
        - Use secure data handling practices
        - Provide clear clinical rationale for all decisions

        Quality Standards:
        - Follow evidence-based clinical guidelines
        - Ensure data accuracy across all systems
        - Provide comprehensive patient care coordination
        - Maintain detailed workflow documentation
    provides:
      - useAs: system_prompt
        in: orchestration-agent
        description: Provide healthcare orchestration instructions

  - id: ehr-system
    type: genesis:ehr_connector
    name: EHR Integration
    description: Electronic health record system access
    asTools: true
    config:
      ehr_system: epic
      fhir_version: R4
      authentication_type: oauth2
      base_url: "${EHR_BASE_URL}"
      operation: get_patient_data
    provides:
      - useAs: tools
        in: orchestration-agent
        description: EHR data access capability

  - id: claims-system
    type: genesis:claims_connector
    name: Claims Processing
    description: Healthcare claims and prior authorization system
    asTools: true
    config:
      clearinghouse: change_healthcare
      provider_npi: "${PROVIDER_NPI}"
      test_mode: false
      operation: submit_claim
    provides:
      - useAs: tools
        in: orchestration-agent
        description: Claims processing capability

  - id: eligibility-system
    type: genesis:eligibility_connector
    name: Insurance Eligibility
    description: Real-time insurance eligibility verification
    asTools: true
    config:
      eligibility_service: availity
      provider_npi: "${PROVIDER_NPI}"
      real_time_mode: true
      cache_duration_minutes: 15
      operation: verify_eligibility
    provides:
      - useAs: tools
        in: orchestration-agent
        description: Eligibility verification capability

  - id: pharmacy-system
    type: genesis:pharmacy_connector
    name: Pharmacy Integration
    description: E-prescribing and medication management
    asTools: true
    config:
      pharmacy_network: surescripts
      prescriber_npi: "${PRESCRIBER_NPI}"
      interaction_checking: true
      formulary_checking: true
      operation: send_prescription
    provides:
      - useAs: tools
        in: orchestration-agent
        description: Pharmacy and medication tools

  - id: orchestration-agent
    type: genesis:agent
    name: Healthcare Orchestration Agent
    description: Orchestrates comprehensive healthcare workflow
    config:
      agent_llm: Azure OpenAI
      model_name: gpt-4
      temperature: 0.1
      max_tokens: 4000
      handle_parsing_errors: true
      max_iterations: 12
      verbose: false
    provides:
      - in: healthcare-output
        useAs: input
        description: Send comprehensive healthcare results

  - id: healthcare-output
    type: genesis:chat_output
    name: Healthcare Workflow Results
    description: Comprehensive healthcare workflow results
    config:
      should_store_message: true

# Key Performance Indicators
kpis:
  - name: Workflow Completion Rate
    category: Quality
    valueType: percentage
    target: 95
    unit: '%'
    description: Percentage of healthcare workflows completed successfully

  - name: HIPAA Compliance Score
    category: Quality
    valueType: percentage
    target: 100
    unit: '%'
    description: HIPAA compliance rating for data handling

  - name: Clinical Accuracy
    category: Quality
    valueType: percentage
    target: 98
    unit: '%'
    description: Accuracy of clinical recommendations and data processing
```

---

## 9. HIPAA Compliance

**Pattern**: Any Healthcare Pattern + Comprehensive Security Metadata
**Complexity**: Healthcare (Variable components)
**Best For**: Secure healthcare data handling, PHI protection, audit requirements

### When to Use
- Any healthcare workflow handling PHI data
- Regulated healthcare environments
- Clinical systems requiring audit trails
- Patient data processing workflows
- Healthcare compliance requirements
- Medical record handling systems

### Additional Metadata Required

```yaml
# HIPAA Compliance Metadata
securityInfo:
  visibility: Private              # Required for PHI data
  confidentiality: High           # High security classification
  gdprSensitive: true            # GDPR compliance flag

# Healthcare Domain Classification
domain: autonomize.ai
subDomain: healthcare-{specific_area}  # e.g., clinical-workflow, patient-care
targetUser: internal             # Restrict to internal users
valueGeneration: ProcessAutomation

# Audit and Monitoring
kpis:
  - name: HIPAA Compliance Score
    category: Quality
    valueType: percentage
    target: 100
    unit: '%'
    description: HIPAA compliance rating

  - name: Data Access Audit
    category: Security
    valueType: numeric
    target: 100
    unit: 'logs'
    description: Complete audit logging of PHI access

# Configuration Variables for Security
variables:
  - name: encryption_key
    type: string
    required: true
    description: Encryption key for PHI data

  - name: audit_endpoint
    type: string
    required: true
    description: Audit logging endpoint URL
```

### HIPAA Compliance Features

All healthcare patterns include:
- **PHI Data Protection**: Automatic sanitization and encryption
- **Audit Logging**: Comprehensive access logging for compliance
- **Secure Error Handling**: Error messages that don't expose PHI
- **Access Controls**: Role-based access to healthcare data
- **Data Minimization**: Only process necessary healthcare data elements

---

## 10. Clinical Workflow

**Pattern**: Input → Knowledge Search + Healthcare Connector → Agent → Output
**Complexity**: Healthcare (6+ components)
**Best For**: Clinical decision support, evidence-based healthcare, guideline-driven workflows

### When to Use
- Clinical decision support systems
- Evidence-based treatment recommendations
- Medical guideline compliance
- Clinical protocol automation
- Treatment plan generation
- Medical research and analysis

### Structure
```
[Chat Input] → [Clinical Agent] → [Chat Output]
                      ↑
    [Knowledge Hub] + [Healthcare Connector]
```

### Components Required
1. `genesis:chat_input` - Clinical query input
2. `genesis:knowledge_hub_search` - Clinical guideline search
3. `genesis:healthcare_connector` - Patient data access
4. `genesis:prompt` - Clinical reasoning prompt
5. `genesis:agent` - Clinical decision agent
6. `genesis:chat_output` - Clinical recommendations

### Template

```yaml
name: Clinical Decision Support Agent
description: Evidence-based clinical decision support with guideline integration
version: "1.0.0"
agentGoal: Provide evidence-based clinical recommendations using current guidelines and patient data

# Clinical workflow metadata
domain: autonomize.ai
subDomain: clinical-decision-support
kind: Single Agent
targetUser: internal
valueGeneration: InsightGeneration
agencyLevel: KnowledgeDrivenWorkflow
toolsUse: true

components:
  - id: clinical-query
    type: genesis:chat_input
    name: Clinical Query Input
    description: Accept clinical questions and patient scenarios
    provides:
      - in: clinical-agent
        useAs: input
        description: Send clinical query to decision agent

  - id: clinical-prompt
    type: genesis:prompt
    name: Clinical Decision Support Instructions
    description: Evidence-based clinical reasoning prompt
    config:
      template: |
        You are a clinical decision support specialist with access to:
        1. Current clinical guidelines and protocols
        2. Patient electronic health records
        3. Evidence-based medical literature

        Clinical Decision Process:
        1. Patient Assessment: Review available patient data and clinical history
        2. Guideline Review: Search for relevant clinical guidelines and protocols
        3. Evidence Analysis: Analyze current medical evidence for the condition
        4. Risk Assessment: Evaluate potential risks and contraindications
        5. Recommendation Generation: Provide evidence-based treatment recommendations

        Quality Standards:
        - Base all recommendations on current clinical guidelines
        - Consider patient-specific factors and contraindications
        - Provide clear rationale for each recommendation
        - Include relevant clinical references and evidence levels
        - Highlight any clinical red flags or urgent considerations

        Output Format:
        - Clinical Assessment: Summary of patient condition
        - Evidence Review: Relevant guidelines and literature
        - Recommendations: Evidence-based treatment options
        - Rationale: Clear reasoning for recommendations
        - Follow-up: Monitoring and next steps
    provides:
      - useAs: system_prompt
        in: clinical-agent
        description: Provide clinical decision support instructions

  - id: guideline-search
    type: genesis:knowledge_hub_search
    name: Clinical Guidelines Search
    description: Search clinical guidelines and protocols
    asTools: true
    config:
      search_scope: clinical_guidelines
      max_results: 10
      document_types: ["LCD", "NCD", "clinical_protocols", "treatment_guidelines"]
    provides:
      - useAs: tools
        in: clinical-agent
        description: Clinical guideline search capability

  - id: patient-data
    type: genesis:ehr_connector
    name: Patient Data Access
    description: Access patient clinical data from EHR
    asTools: true
    config:
      ehr_system: epic
      fhir_version: R4
      authentication_type: oauth2
      operation: get_patient_data
    provides:
      - useAs: tools
        in: clinical-agent
        description: Patient data access for clinical context

  - id: clinical-agent
    type: genesis:agent
    name: Clinical Decision Agent
    description: Evidence-based clinical decision support agent
    config:
      agent_llm: Azure OpenAI
      model_name: gpt-4
      temperature: 0.1
      max_tokens: 3000
      handle_parsing_errors: true
      max_iterations: 8
    provides:
      - in: clinical-output
        useAs: input
        description: Send clinical recommendations

  - id: clinical-output
    type: genesis:chat_output
    name: Clinical Recommendations
    description: Evidence-based clinical recommendations and rationale
    config:
      should_store_message: true

# Clinical Quality Metrics
kpis:
  - name: Clinical Accuracy
    category: Quality
    valueType: percentage
    target: 98
    unit: '%'
    description: Accuracy of clinical recommendations

  - name: Guideline Compliance
    category: Quality
    valueType: percentage
    target: 95
    unit: '%'
    description: Adherence to current clinical guidelines

  - name: Evidence Quality
    category: Quality
    valueType: percentage
    target: 90
    unit: '%'
    description: Quality of supporting clinical evidence
```

---

## Healthcare Pattern Selection Guide

### Decision Matrix for Healthcare Patterns

```
What type of healthcare integration do you need?

Single System Integration
├─ EHR only → Healthcare Integration (EHR Connector)
├─ Claims only → Healthcare Integration (Claims Connector)
├─ Eligibility only → Healthcare Integration (Eligibility Connector)
└─ Pharmacy only → Healthcare Integration (Pharmacy Connector)

Multiple System Integration
├─ 2-3 systems → Multi-Tool Agent (with healthcare connectors)
└─ 4+ systems → Multi-Connector Healthcare

Clinical Decision Making
├─ Guideline-based → Clinical Workflow
├─ Evidence-based → Clinical Workflow + Knowledge Hub
└─ Patient-specific → Clinical Workflow + EHR Connector

Compliance Requirements
├─ HIPAA required → Add HIPAA Compliance metadata
├─ Audit trails → Enterprise + HIPAA patterns
└─ PHI handling → All healthcare patterns include compliance
```

### Healthcare Complexity Progression
1. **Start with Single Connector**: Begin with Healthcare Integration pattern
2. **Add Clinical Guidelines**: Progress to Clinical Workflow pattern
3. **Multiple Systems**: Move to Multi-Connector Healthcare
4. **Enterprise Deployment**: Add HIPAA Compliance and Enterprise metadata

### Common Healthcare Combinations
- **Clinical Assessment**: Clinical Workflow + EHR Connector
- **Patient Journey**: Multi-Connector Healthcare + all four connectors
- **Revenue Cycle**: Healthcare Integration (Claims + Eligibility)
- **Medication Management**: Healthcare Integration (Pharmacy + EHR)
- **Prior Authorization**: Multi-Tool Agent (Claims + Eligibility + EHR)

### Healthcare Best Practices

#### Security and Compliance
- Always include HIPAA compliance metadata for PHI data
- Use environment variables for all healthcare credentials
- Enable audit logging for all healthcare data access
- Implement proper error handling that doesn't expose PHI

#### Performance Optimization
- Cache eligibility data appropriately (typically 15 minutes)
- Use batch operations for multiple claims or prescriptions
- Implement proper timeout handling for healthcare APIs
- Consider rate limiting for high-volume healthcare workflows

#### Clinical Quality
- Base all recommendations on current clinical guidelines
- Include evidence levels and quality ratings
- Provide clear clinical rationale for all decisions
- Implement clinical decision support safeguards

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