# Genesis Component Catalog

Complete reference for all Genesis component types available in agent specifications.

## Overview

Genesis components are the building blocks of agent specifications. Each component type serves a specific purpose in the agent workflow and has its own configuration schema and connection patterns.

## Component Index

| Component Type | Purpose | Category | Connections |
|----------------|---------|----------|-------------|
| [`genesis:chat_input`](#genesischat_input) | User input/data entry | Data | → Agents |
| [`genesis:chat_output`](#genesischat_output) | Display results | Data | ← Agents |
| [`genesis:agent`](#genesisagent) | LLM-powered processing | Agent | ↔ All types |
| [`genesis:prompt`](#genesisprompt_template) | Prompt management | Prompt | → Agents |
| [`genesis:mcp_tool`](#genesismcp_tool) | External API/tool access | Tool | → Agents |
| [`genesis:knowledge_hub_search`](#genesisknowledge_hub_search) | Internal knowledge search | Tool | → Agents |
| [`genesis:ehr_connector`](#genesisehr_connector) | Electronic Health Record integration | Healthcare | → Agents |
| [`genesis:claims_connector`](#genesisclaims_connector) | Healthcare claims processing | Healthcare | → Agents |
| [`genesis:eligibility_connector`](#genesiseligibility_connector) | Insurance eligibility verification | Healthcare | → Agents |
| [`genesis:pharmacy_connector`](#genesispharmacy_connector) | Pharmacy and medication management | Healthcare | → Agents |

---

## `genesis:chat_input`

**Purpose**: Entry point for user data and requests
**Category**: Data
**Use Cases**: Accept user queries, document uploads, form data, parameters

### Configuration Schema

```yaml
id: string                    # Required: Unique identifier
name: string                  # Required: Display name
type: "genesis:chat_input"   # Required: Component type
description: string          # Required: Purpose description
kind: "Data"                 # Optional: Component category
provides: array              # Required: Output connections
```

### Connection Patterns

**Connects TO**: Nothing (entry point)
**Connects FROM**: Agents and other processing components
**Connection Type**: `useAs: "input"`

### Configuration Options

No specific configuration options. This component accepts any user input and passes it to connected components.

### Example Usage

#### Basic Input
```yaml
- id: user-input
  type: genesis:chat_input
  name: User Input
  description: Accept user questions and requests
  provides:
    - in: main-agent
      useAs: input
      description: Send user input to processing agent
```

#### Document Input
```yaml
- id: document-input
  type: genesis:chat_input
  name: Document Upload
  description: Upload documents for processing
  provides:
    - in: document-processor
      useAs: input
      description: Send document to processor
```

#### Structured Input
```yaml
- id: patient-data
  type: genesis:chat_input
  name: Patient Information
  description: Patient demographics and service details
  provides:
    - in: eligibility-agent
      useAs: input
      description: Send patient data for eligibility check
```

### Best Practices

1. **Descriptive Names**: Use clear, specific names that indicate expected input type
2. **Clear Descriptions**: Help users understand what data to provide
3. **Single Purpose**: Each input should serve one clear purpose
4. **Connection Logic**: Always connect to exactly one primary processing component

### Common Use Cases

- **User Queries**: General questions and requests
- **Document Processing**: File uploads, OCR text
- **Form Data**: Structured information entry
- **Search Requests**: Search terms and filters
- **Configuration**: Parameters and settings

---

## `genesis:chat_output`

**Purpose**: Display results and responses to users
**Category**: Data
**Use Cases**: Show processed data, analysis results, formatted responses

### Configuration Schema

```yaml
id: string                     # Required: Unique identifier
name: string                   # Required: Display name
type: "genesis:chat_output"   # Required: Component type
description: string           # Required: Purpose description
kind: "Data"                  # Optional: Component category
config:                       # Optional: Output configuration
  should_store_message: boolean  # Optional: Store in message history
```

### Connection Patterns

**Connects TO**: Agents and processing components
**Connects FROM**: Nothing (terminal node)
**Connection Type**: `useAs: "input"`

### Configuration Options

#### `should_store_message`
- **Type**: boolean
- **Default**: false
- **Purpose**: Whether to store the output in conversation history
- **Use When**: You want to maintain conversation context

### Example Usage

#### Basic Output
```yaml
- id: results
  type: genesis:chat_output
  name: Results
  description: Display processing results
```

#### Stored Output
```yaml
- id: analysis-results
  type: genesis:chat_output
  name: Analysis Results
  description: Display detailed analysis with history
  config:
    should_store_message: true
```

#### Formatted Output
```yaml
- id: classification-output
  type: genesis:chat_output
  name: Document Classification
  description: Display document category and confidence scores
```

### Best Practices

1. **Descriptive Names**: Indicate what type of results are displayed
2. **Store When Needed**: Use `should_store_message: true` for conversational agents
3. **Single Output**: Each agent workflow should have one primary output
4. **Clear Purpose**: Description should explain what users will see

### Common Use Cases

- **Analysis Results**: Processed data and insights
- **Classifications**: Categories and confidence scores
- **Extracted Data**: Structured information from documents
- **Recommendations**: Suggested actions or decisions
- **Status Reports**: Process completion and status updates

---

## `genesis:agent`

**Purpose**: Main LLM-powered processing component
**Category**: Agent
**Use Cases**: Text processing, analysis, decision making, content generation

### Configuration Schema

```yaml
id: string                    # Required: Unique identifier
name: string                  # Required: Display name
type: "genesis:agent"        # Required: Component type
description: string          # Required: Purpose description
kind: "Agent"                # Optional: Component category
config:                      # Optional: Agent configuration
  system_prompt: string        # Optional: Inline system prompt
  agent_llm: string           # Optional: LLM provider
  model_name: string          # Optional: Model identifier
  temperature: float          # Optional: Generation randomness
  max_tokens: integer         # Optional: Response length limit
  handle_parsing_errors: boolean  # Optional: Error handling
  max_iterations: integer     # Optional: Tool usage iterations
  verbose: boolean            # Optional: Debug logging
provides: array              # Required: Output connections
```

### Connection Patterns

**Connects TO**: Input components, prompt templates, tools
**Connects FROM**: Output components, other agents
**Connection Types**:
- `useAs: "input"` - Receives data to process
- `useAs: "system_prompt"` - Receives system prompt from template
- `useAs: "tools"` - Receives tool capabilities

### Configuration Options

#### `system_prompt`
- **Type**: string (multiline YAML literal)
- **Purpose**: Define agent behavior and instructions
- **Note**: Not used if prompt template is connected
- **Best Practice**: Use for simple prompts, prompt templates for complex ones

#### `agent_llm`
- **Type**: string
- **Default**: "Azure OpenAI"
- **Options**: "Azure OpenAI", "OpenAI", "Anthropic"
- **Purpose**: Specify LLM provider

#### `model_name`
- **Type**: string
- **Default**: "gpt-4"
- **Options**: "gpt-4", "gpt-3.5-turbo", "claude-3-sonnet", etc.
- **Purpose**: Specify model within provider

#### `temperature`
- **Type**: float (0.0 - 1.0)
- **Default**: 0.1
- **Purpose**: Control randomness in responses
- **Guidelines**:
  - 0.1: Highly deterministic (classification, extraction)
  - 0.3: Mostly consistent (analysis, summarization)
  - 0.7: Creative but controlled (content generation)
  - 0.9: Highly creative (brainstorming, creative writing)

#### `max_tokens`
- **Type**: integer
- **Default**: 2000
- **Purpose**: Limit response length
- **Guidelines**:
  - 500-1000: Short responses (classification, yes/no)
  - 1000-2000: Medium responses (analysis, explanations)
  - 2000-4000: Long responses (detailed reports)
  - 4000+: Very long outputs (comprehensive analysis)

#### `handle_parsing_errors`
- **Type**: boolean
- **Default**: false
- **Purpose**: Robust error handling for malformed responses
- **Use When**: Agent produces structured output or uses tools

#### `max_iterations`
- **Type**: integer
- **Default**: 5
- **Purpose**: Maximum tool usage iterations
- **Use When**: Agent has access to tools
- **Range**: 3-10 (higher for complex workflows)

#### `verbose`
- **Type**: boolean
- **Default**: false
- **Purpose**: Enable debug logging
- **Use When**: Debugging agent behavior

### Example Usage

#### Simple Agent with Inline Prompt
```yaml
- id: classifier
  type: genesis:agent
  name: Document Classifier
  description: Classifies documents by type
  config:
    system_prompt: |
      You are a document classifier.

      Classify documents into these categories:
      - Medical: Health records, prescriptions
      - Legal: Contracts, agreements
      - Financial: Invoices, statements

      Return only the category name.
    temperature: 0.1
    max_tokens: 100
  provides:
    - in: output
      useAs: input
      description: Send classification result
```

#### Agent with External Prompt and Tools
```yaml
- id: analysis-agent
  type: genesis:agent
  name: Data Analysis Agent
  description: Analyzes data using external tools
  config:
    temperature: 0.3
    max_tokens: 2000
    handle_parsing_errors: true
    max_iterations: 8
    verbose: false
  provides:
    - in: results-output
      useAs: input
      description: Send analysis results
```

#### Production Agent Configuration
```yaml
- id: production-agent
  type: genesis:agent
  name: Production Agent
  description: Enterprise-grade processing agent
  config:
    agent_llm: Azure OpenAI
    model_name: gpt-4
    temperature: 0.1
    max_tokens: 3000
    handle_parsing_errors: true
    max_iterations: 10
    verbose: false
  provides:
    - in: formatted-output
      useAs: input
      description: Send processed results
```

### Best Practices

1. **Temperature Selection**: Match temperature to task type
2. **Token Limits**: Set appropriate limits for expected output length
3. **Error Handling**: Enable for production agents and tool users
4. **Prompt Source**: Use inline for simple prompts, templates for complex ones
5. **Iterations**: Set based on tool complexity and workflow needs
6. **Model Selection**: Use appropriate model for task complexity

### Common Patterns

- **Classification**: Low temperature, short tokens, clear categories
- **Analysis**: Medium temperature, moderate tokens, structured output
- **Generation**: Higher temperature, longer tokens, creative freedom
- **Tool Orchestration**: Error handling, multiple iterations, verbose debugging

---

## `genesis:prompt`

**Purpose**: Centralized prompt management and templating
**Category**: Prompt
**Use Cases**: Complex prompts, prompt versioning, reusable prompt logic

### Configuration Schema

```yaml
id: string                          # Required: Unique identifier
name: string                        # Required: Display name
type: "genesis:prompt"    # Required: Component type
description: string                # Required: Purpose description
kind: "Prompt"                     # Optional: Component category
config:                            # Required: Prompt configuration
  saved_prompt: string               # Optional: Reference to saved prompt
  template: string                   # Required: Actual prompt text
provides: array                    # Required: Output connections
```

### Connection Patterns

**Connects TO**: Nothing (prompt provider)
**Connects FROM**: Agents only
**Connection Type**: `useAs: "system_prompt"`

### Configuration Options

#### `saved_prompt`
- **Type**: string
- **Purpose**: Reference to a saved prompt in the system
- **Use When**: Prompt is managed centrally or versioned
- **Example**: "classification_prompt_v2"

#### `template`
- **Type**: string (multiline YAML literal)
- **Purpose**: The actual prompt text
- **Required**: Always required, even if `saved_prompt` is specified
- **Best Practice**: Use YAML literal blocks for multiline prompts

### Example Usage

#### Simple Prompt Template
```yaml
- id: classification-prompt
  type: genesis:prompt
  name: Classification Instructions
  description: Prompt for document classification
  config:
    template: |
      You are a document classification specialist.

      Classify the provided document into one of these categories:
      - Medical Records
      - Insurance Claims
      - Legal Documents
      - Financial Statements

      Provide your classification with confidence level.
  provides:
    - useAs: system_prompt
      in: classifier-agent
      description: Provide classification instructions
```

#### Complex Workflow Prompt
```yaml
- id: workflow-prompt
  type: genesis:prompt
  name: Multi-Step Workflow Instructions
  description: Complex workflow orchestration prompt
  config:
    saved_prompt: workflow_v3
    template: |
      You are a workflow orchestrator with access to multiple tools.

      Your responsibilities:
      1. Analyze the incoming request
      2. Determine required data sources
      3. Orchestrate tool usage in proper sequence
      4. Synthesize results into comprehensive response

      Available tools:
      - Data Retrieval: Get information from databases
      - Calculation Engine: Perform complex calculations
      - Validation Service: Verify data accuracy

      Workflow steps:
      1. Use Data Retrieval to gather baseline information
      2. Apply business rules using Calculation Engine
      3. Validate results using Validation Service
      4. Format final response with recommendations

      Always explain your reasoning and show confidence levels.
  provides:
    - useAs: system_prompt
      in: orchestrator-agent
      description: Provide workflow instructions
```

#### Versioned Prompt with Fallback
```yaml
- id: analysis-prompt
  type: genesis:prompt
  name: Analysis Instructions v2.1
  description: Updated analysis prompt with new requirements
  config:
    saved_prompt: analysis_prompt_v2_1
    template: |
      # Analysis Agent Instructions v2.1

      You are a healthcare data analyst specializing in prior authorization.

      ## Core Responsibilities
      1. Review member eligibility and benefits
      2. Analyze medical necessity based on clinical guidelines
      3. Calculate member financial responsibility
      4. Identify potential coverage issues

      ## Analysis Framework
      ### Step 1: Eligibility Verification
      - Verify member active status
      - Check benefit coverage for requested service
      - Identify any waiting periods or limitations

      ### Step 2: Medical Necessity Review
      - Apply relevant clinical guidelines (LCD/NCD)
      - Review supporting documentation
      - Assess appropriateness of requested service

      ### Step 3: Financial Analysis
      - Calculate deductible impact
      - Determine copay/coinsurance amounts
      - Check out-of-pocket maximum status

      ## Output Requirements
      Provide structured JSON response with:
      - eligibility_status: active/inactive/pending
      - coverage_decision: approved/denied/more_info_needed
      - member_responsibility: dollar amount
      - clinical_rationale: explanation of medical necessity
      - next_steps: required actions

      ## Quality Standards
      - Base decisions on current guidelines and policies
      - Provide clear rationale for all determinations
      - Flag any edge cases or unusual circumstances
      - Maintain HIPAA compliance in all communications
  provides:
    - useAs: system_prompt
      in: analysis-agent
      description: Provide comprehensive analysis instructions
```

### Best Practices

1. **Structure**: Use clear headings and organization
2. **Versioning**: Include version information in saved_prompt reference
3. **Specificity**: Be explicit about expected inputs and outputs
4. **Guidelines**: Include clear rules and decision criteria
5. **Examples**: Show desired behavior when space allows
6. **Formatting**: Use consistent formatting and bullet points
7. **Testing**: Validate prompts with sample inputs

### When to Use Prompt Templates

**Use prompt templates when**:
- Prompts are longer than 10 lines
- Multiple agents share similar prompts
- Prompts need versioning or A/B testing
- Prompts require approval workflows
- Complex formatting or structure is needed

**Use inline prompts when**:
- Prompts are simple and short
- Agent-specific and unlikely to be reused
- Quick prototyping or testing
- No governance requirements

### Common Patterns

#### Classification Prompt
- Clear category definitions
- Output format specification
- Confidence level requirements
- Edge case handling

#### Analysis Prompt
- Step-by-step process
- Decision criteria
- Quality standards
- Structured output format

#### Workflow Orchestration
- Tool descriptions and usage
- Sequence requirements
- Error handling instructions
- Result synthesis guidelines

---

## `genesis:mcp_tool`

**Purpose**: Integration with external APIs, databases, and services via MCP (Model Context Protocol)
**Category**: Tool
**Use Cases**: API calls, database queries, external calculations, third-party integrations

### Configuration Schema

```yaml
id: string                   # Required: Unique identifier
name: string                 # Required: Display name
type: "genesis:mcp_tool"    # Required: Component type
description: string         # Required: Purpose description
kind: "Tool"                # Optional: Component category
asTools: boolean            # Required: Always true for MCP tools
config:                     # Required: Tool configuration
  tool_name: string           # Required: MCP tool identifier
  description: string         # Required: Tool description for agent
  # Tool-specific parameters vary
provides: array             # Required: Output connections
```

### Connection Patterns

**Connects TO**: Nothing (tool provider)
**Connects FROM**: Agents only
**Connection Type**: `useAs: "tools"`

### Configuration Options

#### `tool_name`
- **Type**: string
- **Purpose**: Identifier for the MCP tool
- **Required**: Always required
- **Examples**: "claims_api", "benefit_calculator", "qnext_auth_history"

#### `description`
- **Type**: string
- **Purpose**: Tells the agent what this tool does and when to use it
- **Required**: Always required
- **Best Practice**: Be specific about tool purpose, parameters, and output

#### Tool-Specific Parameters
Additional configuration varies by tool type. Common parameters:

- `timeout`: Request timeout in milliseconds
- `retry_count`: Number of retry attempts
- `base_url`: API endpoint base URL
- `api_version`: API version to use
- `lookback_months`: Time range for data retrieval
- `include_claims`: Whether to include claims data
- `rate_limit`: Requests per second limit

### Example Usage

#### API Integration Tool
```yaml
- id: claims-api
  type: genesis:mcp_tool
  name: Claims History API
  description: Retrieve member claims history
  asTools: true
  config:
    tool_name: claims_history_api
    description: |
      Retrieve detailed claims history for a member.

      Use this tool when you need:
      - Past medical services and procedures
      - Claims costs and payment information
      - Service dates and providers
      - Utilization patterns

      Required parameters:
      - member_id: Member identifier
      - date_range: Start and end dates (YYYY-MM-DD)

      Optional parameters:
      - service_type: Filter by service category
      - provider_npi: Filter by specific provider
    timeout: 30000
    retry_count: 3
    include_details: true
  provides:
    - useAs: tools
      in: analysis-agent
      description: Provide claims data access
```

#### Calculation Tool
```yaml
- id: benefit-calculator
  type: genesis:mcp_tool
  name: Benefit Calculator
  description: Calculate member financial responsibility
  asTools: true
  config:
    tool_name: benefit_calculation_engine
    description: |
      Calculate member costs based on benefits and accumulators.

      This tool calculates:
      - Deductible amounts (individual and family)
      - Copay and coinsurance amounts
      - Out-of-pocket maximum impacts
      - Member responsibility for service

      Required parameters:
      - member_id: Member identifier
      - service_cost: Estimated service cost
      - service_code: CPT or HCPCS code
      - service_date: Date of service

      Returns detailed cost breakdown with explanations.
    calculation_mode: detailed
    include_projections: true
  provides:
    - useAs: tools
      in: financial-agent
      description: Provide cost calculation capability
```

#### Database Query Tool
```yaml
- id: eligibility-db
  type: genesis:mcp_tool
  name: Eligibility Database
  description: Query member eligibility information
  asTools: true
  config:
    tool_name: eligibility_database_query
    description: |
      Query member eligibility and benefit information.

      Available queries:
      - Current eligibility status
      - Benefit plan details
      - Coverage effective dates
      - Dependent information

      Use when you need to verify:
      - Member is currently eligible
      - Specific benefits are covered
      - Coverage limitations or exclusions

      Parameter: member_id (required)
    query_timeout: 15000
    cache_duration: 300
    include_dependents: false
  provides:
    - useAs: tools
      in: eligibility-agent
      description: Provide eligibility query access
```

#### External Service Integration
```yaml
- id: prior-auth-system
  type: genesis:mcp_tool
  name: Prior Authorization System
  description: Submit and check prior authorization requests
  asTools: true
  config:
    tool_name: prior_auth_api
    description: |
      Interface with prior authorization system.

      Capabilities:
      - Submit new PA requests
      - Check PA status
      - Retrieve PA decisions
      - Update PA information

      For submissions, provide:
      - member_id, provider_npi, service_codes
      - diagnosis_codes, supporting_documentation
      - urgency_level (routine/urgent/stat)

      Returns PA number and initial status.
    environment: production
    auto_submit: false
    require_approval: true
  provides:
    - useAs: tools
      in: pa-agent
      description: Provide prior auth system access
```

### Best Practices

1. **Descriptive Names**: Use clear, specific tool names
2. **Detailed Descriptions**: Explain when and how to use the tool
3. **Parameter Documentation**: List required and optional parameters
4. **Return Value Info**: Describe what the tool returns
5. **Error Handling**: Configure appropriate timeouts and retries
6. **Security**: Use proper authentication and authorization
7. **Rate Limiting**: Respect API limits and quotas

### Tool Description Guidelines

Your tool description should answer:
- **What**: What does this tool do?
- **When**: When should the agent use it?
- **How**: What parameters are needed?
- **Output**: What does it return?

#### Good Tool Description Template
```yaml
description: |
  [Tool purpose and main functionality]

  Use this tool when you need:
  - [Use case 1]
  - [Use case 2]
  - [Use case 3]

  Required parameters:
  - param1: Description and format
  - param2: Description and format

  Optional parameters:
  - param3: Description and default

  Returns: [Description of return format and content]

  [Any special notes or limitations]
```

### Common Integration Patterns

#### Healthcare APIs
- Claims history retrieval
- Eligibility verification
- Prior authorization systems
- Clinical decision support
- Benefit calculations

#### Data Processing
- Document processing services
- OCR and text extraction
- Data validation engines
- Calculation services
- Reporting systems

#### External Services
- Payment processing
- Notification services
- Audit logging
- Compliance checking
- Workflow management

---

## `genesis:knowledge_hub_search`

**Purpose**: Search internal knowledge bases and document repositories
**Category**: Tool
**Use Cases**: Policy lookup, guideline retrieval, document search, FAQ access

### Configuration Schema

```yaml
id: string                            # Required: Unique identifier
name: string                          # Required: Display name
type: "genesis:knowledge_hub_search" # Required: Component type
description: string                  # Required: Purpose description
kind: "Tool"                         # Optional: Component category
asTools: boolean                     # Required: Always true
config:                              # Optional: Search configuration
  # Configuration options vary by implementation
provides: array                      # Required: Output connections
```

### Connection Patterns

**Connects TO**: Nothing (search provider)
**Connects FROM**: Agents only
**Connection Type**: `useAs: "tools"`

### Configuration Options

Configuration options for knowledge hub search may include:

- `search_scope`: Limit search to specific document types
- `max_results`: Maximum number of results to return
- `relevance_threshold`: Minimum relevance score
- `document_types`: Filter by document categories
- `date_range`: Limit to recent documents

*Note: Specific configuration options depend on the knowledge hub implementation*

### Example Usage

#### Clinical Guidelines Search
```yaml
- id: guideline-search
  type: genesis:knowledge_hub_search
  name: Clinical Guidelines Search
  description: Search clinical guidelines and protocols
  asTools: true
  config:
    search_scope: clinical_guidelines
    max_results: 10
    document_types: ["LCD", "NCD", "clinical_protocols"]
  provides:
    - useAs: tools
      in: guideline-agent
      description: Provide clinical guideline search capability
```

#### Policy Document Search
```yaml
- id: policy-search
  type: genesis:knowledge_hub_search
  name: Policy Document Search
  description: Search organizational policies and procedures
  asTools: true
  config:
    search_scope: policies
    relevance_threshold: 0.7
    include_archived: false
  provides:
    - useAs: tools
      in: policy-agent
      description: Provide policy document search
```

#### General Knowledge Search
```yaml
- id: knowledge-search
  type: genesis:knowledge_hub_search
  name: Knowledge Base Search
  description: Search comprehensive knowledge base
  asTools: true
  provides:
    - useAs: tools
      in: research-agent
      description: Provide knowledge base search capability
```

### Best Practices

1. **Specific Descriptions**: Clearly describe what knowledge is searchable
2. **Search Scope**: Configure appropriate search boundaries
3. **Result Limits**: Set reasonable limits to avoid overwhelming the agent
4. **Quality Filters**: Use relevance thresholds to ensure good results
5. **Agent Instructions**: Tell the agent when and how to use search

### When to Use Knowledge Hub Search

**Use when agents need to**:
- Find relevant policies or procedures
- Retrieve clinical guidelines or protocols
- Access FAQ or help documentation
- Search historical decisions or precedents
- Find templates or examples

**Typical Use Cases**:
- Prior authorization guideline lookup
- Policy interpretation and application
- Clinical decision support
- Compliance verification
- Best practice recommendations

### Integration with Agent Prompts

When using knowledge hub search, include clear instructions in your agent prompt:

```yaml
system_prompt: |
  You are a clinical guideline specialist.

  Use the Knowledge Hub Search tool to find relevant clinical guidelines.

  When searching:
  1. Use specific medical terms and procedure codes
  2. Look for both local (LCD) and national (NCD) coverage determinations
  3. Search for relevant clinical protocols
  4. Check for recent updates or changes

  Always cite the specific guidelines found and their relevance to the case.
```

## Component Selection Guide

### Decision Matrix

| Need | Component Type | Notes |
|------|----------------|-------|
| User input | `genesis:chat_input` | Always required as entry point |
| Display results | `genesis:chat_output` | Always required as exit point |
| Text processing | `genesis:agent` | Core processing component |
| Complex prompts | `genesis:prompt` | Use for reusable or complex prompts |
| External data | `genesis:mcp_tool` | For APIs, databases, calculations |
| Internal search | `genesis:knowledge_hub_search` | For knowledge base access |

### Common Component Combinations

#### Basic Processing (3 components)
```
chat_input → agent → chat_output
```

#### With External Prompt (4 components)
```
chat_input → agent ← prompt_template
             ↓
         chat_output
```

#### With Single Tool (4-5 components)
```
chat_input → agent → chat_output
             ↑
           tool
```

#### Complex Workflow (6+ components)
```
chat_input → agent → chat_output
             ↑
    prompt + tool1 + tool2 + tool3
```

## Validation Rules

### Component Structure
1. All components must have: `id`, `name`, `type`, `description`
2. Component IDs must be unique within specification
3. Component types must be valid Genesis types

### Connection Rules
1. `provides` array must reference existing component IDs
2. `useAs` values must match target component capabilities:
   - Agents accept: `input`, `system_prompt`, `tools`
   - Output components accept: `input`
3. No circular dependencies allowed

### Type-Specific Rules
1. **Input components**: Must have `provides` connections
2. **Output components**: Must not have `provides` connections
3. **Tools**: Must have `asTools: true` and connect via `useAs: "tools"`
4. **Prompts**: Must connect via `useAs: "system_prompt"`

---

## Healthcare Connectors

Healthcare connectors provide specialized integration capabilities for healthcare systems and workflows, ensuring HIPAA compliance and industry-standard connectivity. All healthcare connectors inherit from a base class that provides standardized audit logging, PHI data protection, and compliance features.

### Common Healthcare Features

All healthcare connectors include:
- **HIPAA Compliance**: Built-in PHI data protection and audit logging
- **Mock Mode**: Comprehensive mock data for development and testing
- **Error Handling**: Healthcare-specific error handling with compliance requirements
- **Industry Standards**: Support for FHIR, HL7, EDI, and other healthcare standards
- **Tool Mode**: Can be used as tools by agents with proper configuration

---

## `genesis:ehr_connector`

**Purpose**: Electronic Health Record (EHR) integration with FHIR R4 and HL7 support
**Category**: Healthcare
**Use Cases**: Patient data retrieval, clinical documentation, care coordination, EHR system integration

### Configuration Schema

```yaml
id: string                            # Required: Unique identifier
name: string                          # Required: Display name
type: "genesis:ehr_connector"        # Required: Component type
description: string                  # Required: Purpose description
kind: "Healthcare"                   # Optional: Component category
asTools: boolean                     # Optional: Expose as tool (default: true)
config:                              # Required: EHR configuration
  ehr_system: string                   # Required: EHR system type
  fhir_version: string                 # Required: FHIR version
  authentication_type: string         # Required: Authentication method
  base_url: string                     # Required: EHR system URL
  operation: string                    # Required: Operation to perform
provides: array                      # Required: Output connections
```

### Configuration Options

#### `ehr_system`
- **Type**: string (dropdown)
- **Options**: "epic", "cerner", "allscripts", "athenahealth"
- **Default**: "epic"
- **Purpose**: Specify the EHR system vendor for integration

#### `fhir_version`
- **Type**: string (dropdown)
- **Options**: "R4", "STU3", "DSTU2"
- **Default**: "R4"
- **Purpose**: FHIR version for resource compatibility and standards compliance

#### `authentication_type`
- **Type**: string (dropdown)
- **Options**: "oauth2", "basic", "api_key"
- **Default**: "oauth2"
- **Purpose**: Authentication method for secure EHR system access

#### `base_url`
- **Type**: string
- **Default**: "${EHR_BASE_URL}"
- **Purpose**: EHR system base URL (use environment variables for production)

#### `operation`
- **Type**: string (dropdown)
- **Options**:
  - "search_patients": Search for patients based on criteria
  - "get_patient_data": Retrieve comprehensive patient information
  - "get_observations": Get patient observations (vital signs, lab results)
  - "get_medications": Retrieve patient medication list
  - "get_conditions": Get patient conditions and diagnoses
  - "get_providers": Retrieve provider information
  - "update_patient_data": Update patient information (requires permissions)
  - "get_care_team": Get patient care team information
  - "get_care_plan": Retrieve patient care plan details
- **Default**: "get_patient_data"
- **Purpose**: EHR operation to perform

### Connection Patterns

**Connects TO**: Nothing (data provider)
**Connects FROM**: Agents only
**Connection Type**: `useAs: "tools"`

### Example Usage

#### Basic EHR Integration
```yaml
- id: ehr-connector
  type: genesis:ehr_connector
  name: Epic EHR Integration
  description: Retrieve patient data from Epic EHR system
  asTools: true
  config:
    ehr_system: epic
    fhir_version: R4
    authentication_type: oauth2
    base_url: "${EPIC_BASE_URL}"
    operation: get_patient_data
  provides:
    - useAs: tools
      in: clinical-agent
      description: Provide EHR data access capability
```

#### Multi-Operation EHR Workflow
```yaml
- id: comprehensive-ehr
  type: genesis:ehr_connector
  name: Comprehensive EHR Data
  description: Access multiple EHR data types for patient
  asTools: true
  config:
    ehr_system: cerner
    fhir_version: R4
    authentication_type: oauth2
    base_url: "${CERNER_BASE_URL}"
    operation: search_patients
  provides:
    - useAs: tools
      in: patient-workflow-agent
      description: EHR search and retrieval tools
```

### Supported Data Formats

- **FHIR R4 Resources**: Patient, Observation, Condition, Medication, Practitioner, CareTeam
- **HL7 Messages**: ADT, ORM, ORU, SIU message types
- **Clinical Terminologies**: LOINC codes, SNOMED CT, ICD-10, CPT codes

---

## `genesis:claims_connector`

**Purpose**: Healthcare claims processing integration supporting EDI transactions and prior authorization
**Category**: Healthcare
**Use Cases**: Claims submission, prior authorization, payment posting, claims status inquiry

### Configuration Schema

```yaml
id: string                              # Required: Unique identifier
name: string                            # Required: Display name
type: "genesis:claims_connector"       # Required: Component type
description: string                    # Required: Purpose description
kind: "Healthcare"                     # Optional: Component category
asTools: boolean                       # Optional: Expose as tool (default: true)
config:                                # Required: Claims configuration
  clearinghouse: string                  # Required: Claims clearinghouse
  payer_id: string                      # Optional: Insurance payer identifier
  provider_npi: string                  # Optional: Provider NPI number
  test_mode: boolean                    # Optional: Development vs production
  operation: string                     # Required: Claims operation
provides: array                        # Required: Output connections
```

### Configuration Options

#### `clearinghouse`
- **Type**: string (dropdown)
- **Options**: "change_healthcare", "availity", "relay_health", "navinet"
- **Default**: "change_healthcare"
- **Purpose**: Healthcare clearinghouse for claims processing

#### `operation`
- **Type**: string (dropdown)
- **Options**:
  - "submit_claim": Submit new healthcare claim (837 transaction)
  - "check_claim_status": Inquire about claim status (276/277 transactions)
  - "get_remittance": Retrieve remittance advice (835 transaction)
  - "prior_authorization": Submit prior authorization request
  - "check_pa_status": Check prior authorization status
  - "validate_claim": Validate claim data before submission
- **Default**: "submit_claim"
- **Purpose**: Claims processing operation to perform

#### `test_mode`
- **Type**: boolean
- **Default**: true
- **Purpose**: Enable test mode for development (prevents real claim submission)

### Example Usage

#### Claims Submission Workflow
```yaml
- id: claims-processor
  type: genesis:claims_connector
  name: Claims Processing System
  description: Submit and track healthcare claims
  asTools: true
  config:
    clearinghouse: change_healthcare
    provider_npi: "${PROVIDER_NPI}"
    test_mode: false
    operation: submit_claim
  provides:
    - useAs: tools
      in: billing-agent
      description: Claims submission and tracking tools
```

#### Prior Authorization Integration
```yaml
- id: pa-connector
  type: genesis:claims_connector
  name: Prior Authorization System
  description: Handle prior authorization requests and status
  asTools: true
  config:
    clearinghouse: availity
    payer_id: "${PAYER_ID}"
    test_mode: true
    operation: prior_authorization
  provides:
    - useAs: tools
      in: authorization-agent
      description: Prior authorization processing tools
```

### Supported Transactions

- **837 Professional**: Physician and outpatient claims
- **837 Institutional**: Hospital and facility claims
- **837 Dental**: Dental service claims
- **835 Remittance**: Payment and adjustment information
- **276/277**: Claim status inquiry and response

---

## `genesis:eligibility_connector`

**Purpose**: Insurance eligibility verification and benefit determination
**Category**: Healthcare
**Use Cases**: Real-time benefit verification, coverage determination, network provider validation

### Configuration Schema

```yaml
id: string                                # Required: Unique identifier
name: string                              # Required: Display name
type: "genesis:eligibility_connector"    # Required: Component type
description: string                      # Required: Purpose description
kind: "Healthcare"                       # Optional: Component category
asTools: boolean                         # Optional: Expose as tool (default: true)
config:                                  # Required: Eligibility configuration
  eligibility_service: string             # Required: Eligibility service provider
  payer_list: array                      # Optional: Supported insurance payers
  provider_npi: string                   # Optional: Provider NPI
  real_time_mode: boolean                # Optional: Real-time vs cached
  cache_duration_minutes: integer        # Optional: Cache duration
  operation: string                      # Required: Eligibility operation
provides: array                          # Required: Output connections
```

### Configuration Options

#### `eligibility_service`
- **Type**: string (dropdown)
- **Options**: "availity", "change_healthcare", "navinet"
- **Default**: "availity"
- **Purpose**: Eligibility verification service provider

#### `operation`
- **Type**: string (dropdown)
- **Options**:
  - "verify_eligibility": Real-time benefit verification (270/271 EDI)
  - "get_benefit_summary": Comprehensive benefit information
  - "check_coverage": Specific service coverage determination
  - "validate_provider": Network provider validation
  - "calculate_costs": Copay and deductible calculations
- **Default**: "verify_eligibility"
- **Purpose**: Eligibility verification operation

#### `real_time_mode`
- **Type**: boolean
- **Default**: true
- **Purpose**: Enable real-time verification vs cached responses

#### `cache_duration_minutes`
- **Type**: integer
- **Default**: 15
- **Purpose**: Duration to cache eligibility responses (in minutes)

### Example Usage

#### Real-Time Eligibility Verification
```yaml
- id: eligibility-checker
  type: genesis:eligibility_connector
  name: Real-Time Eligibility Verification
  description: Verify patient insurance eligibility and benefits
  asTools: true
  config:
    eligibility_service: availity
    provider_npi: "${PROVIDER_NPI}"
    real_time_mode: true
    cache_duration_minutes: 15
    operation: verify_eligibility
  provides:
    - useAs: tools
      in: eligibility-agent
      description: Real-time eligibility verification tools
```

#### Benefit Analysis Workflow
```yaml
- id: benefit-analyzer
  type: genesis:eligibility_connector
  name: Comprehensive Benefit Analysis
  description: Analyze patient benefits and coverage details
  asTools: true
  config:
    eligibility_service: change_healthcare
    payer_list: ["aetna", "anthem", "cigna", "humana"]
    real_time_mode: false
    operation: get_benefit_summary
  provides:
    - useAs: tools
      in: benefit-analysis-agent
      description: Benefit analysis and comparison tools
```

### Supported Transactions

- **270/271 EDI**: Real-time eligibility verification
- **Provider Directory**: Network provider search and validation
- **Benefit Summaries**: Coverage details and limitations
- **Cost Calculations**: Copay, deductible, and out-of-pocket estimates

---

## `genesis:pharmacy_connector`

**Purpose**: Pharmacy and medication management with e-prescribing integration
**Category**: Healthcare
**Use Cases**: E-prescribing, drug interaction checking, formulary verification, medication therapy management

### Configuration Schema

```yaml
id: string                              # Required: Unique identifier
name: string                            # Required: Display name
type: "genesis:pharmacy_connector"     # Required: Component type
description: string                    # Required: Purpose description
kind: "Healthcare"                     # Optional: Component category
asTools: boolean                       # Optional: Expose as tool (default: true)
config:                                # Required: Pharmacy configuration
  pharmacy_network: string              # Required: Pharmacy network
  prescriber_npi: string               # Optional: Prescriber NPI
  dea_number: string                   # Optional: DEA registration number
  drug_database: string                # Optional: Drug database system
  interaction_checking: boolean         # Optional: Enable drug interactions
  formulary_checking: boolean          # Optional: Enable formulary verification
  operation: string                    # Required: Pharmacy operation
provides: array                        # Required: Output connections
```

### Configuration Options

#### `pharmacy_network`
- **Type**: string (dropdown)
- **Options**: "surescripts", "ncpdp", "relay_health"
- **Default**: "surescripts"
- **Purpose**: Pharmacy network for e-prescribing integration

#### `operation`
- **Type**: string (dropdown)
- **Options**:
  - "send_prescription": Send electronic prescription (eRx)
  - "check_interactions": Drug interaction screening
  - "verify_formulary": Check drug formulary status
  - "medication_history": Get patient medication history
  - "prior_auth_medication": Medication prior authorization
  - "pharmacy_search": Find nearby pharmacies
- **Default**: "send_prescription"
- **Purpose**: Pharmacy operation to perform

#### `interaction_checking`
- **Type**: boolean
- **Default**: true
- **Purpose**: Enable automated drug interaction checking

#### `formulary_checking`
- **Type**: boolean
- **Default**: true
- **Purpose**: Enable formulary verification for medications

#### `drug_database`
- **Type**: string (dropdown)
- **Options**: "first_databank", "medi_span", "lexicomp"
- **Default**: "first_databank"
- **Purpose**: Drug database for interaction and formulary checking

### Example Usage

#### E-Prescribing Integration
```yaml
- id: eprescribing-system
  type: genesis:pharmacy_connector
  name: E-Prescribing System
  description: Electronic prescription management with interaction checking
  asTools: true
  config:
    pharmacy_network: surescripts
    prescriber_npi: "${PRESCRIBER_NPI}"
    dea_number: "${DEA_NUMBER}"
    interaction_checking: true
    formulary_checking: true
    operation: send_prescription
  provides:
    - useAs: tools
      in: prescribing-agent
      description: E-prescribing and medication management tools
```

#### Medication Therapy Management
```yaml
- id: mtm-connector
  type: genesis:pharmacy_connector
  name: Medication Therapy Management
  description: Comprehensive medication management and optimization
  asTools: true
  config:
    pharmacy_network: ncpdp
    drug_database: first_databank
    interaction_checking: true
    formulary_checking: true
    operation: medication_history
  provides:
    - useAs: tools
      in: pharmacist-agent
      description: Medication therapy management tools
```

### Supported Standards

- **NCPDP SCRIPT**: E-prescribing standard for electronic prescriptions
- **RxNorm**: Standardized nomenclature for clinical drugs
- **NDC**: National Drug Code directory
- **Formulary Data**: Insurance plan formulary information

---

## Healthcare Connector Best Practices

### Security and Compliance

1. **Environment Variables**: Always use environment variables for sensitive data
```yaml
config:
  base_url: "${EHR_BASE_URL}"
  api_key: "${EHR_API_KEY}"
  provider_npi: "${PROVIDER_NPI}"
```

2. **HIPAA Compliance**: All healthcare connectors include built-in HIPAA compliance features
- Automatic PHI data sanitization
- Comprehensive audit logging
- Secure error handling without PHI exposure

3. **Mock Mode**: Use mock mode for development and testing
```yaml
config:
  test_mode: true  # Enables mock data responses
```

### Integration Patterns

#### Healthcare Multi-Tool Agent
```yaml
- id: comprehensive-healthcare-agent
  type: genesis:agent
  name: Healthcare Integration Agent
  description: Agent with access to multiple healthcare systems
  config:
    system_prompt: |
      You are a healthcare integration specialist with access to:
      - EHR systems for patient data
      - Claims processing for billing
      - Eligibility verification for coverage
      - Pharmacy systems for medications

      Use these tools to provide comprehensive healthcare workflow automation.
    max_iterations: 10
    handle_parsing_errors: true
  provides:
    - in: healthcare-output
      useAs: input
      description: Send comprehensive healthcare results
```

#### Sequential Healthcare Workflow
Use multiple healthcare connectors in sequence for complex workflows:
1. **EHR Connector**: Retrieve patient data
2. **Eligibility Connector**: Verify insurance coverage
3. **Claims Connector**: Process billing information
4. **Pharmacy Connector**: Handle medication management

### Error Handling

Healthcare connectors provide specialized error handling:
- **Timeout Management**: Configurable timeouts for healthcare APIs
- **Retry Logic**: Automatic retry for transient failures
- **Compliance Logging**: HIPAA-compliant error logging
- **Fallback Modes**: Graceful degradation to mock data when services unavailable

### Performance Optimization

1. **Caching**: Use appropriate cache durations for eligibility data
2. **Batch Operations**: Combine multiple operations when possible
3. **Connection Pooling**: Efficient connection management for high-volume usage
4. **Rate Limiting**: Respect healthcare API rate limits

## Next Steps

- **Pattern Selection**: See [Pattern Catalog](../patterns/pattern-catalog.md)
- **Specification Creation**: See [Creating Specifications Guide](../guides/creating-specifications.md)
- **Schema Reference**: See [Specification Schema](../schema/specification-schema.md)
- **Healthcare Integration**: See [Healthcare Connector Integration Guide](../guides/healthcare-integration.md)
- **HIPAA Compliance**: See [HIPAA Compliance Best Practices Guide](../guides/hipaa-compliance.md)