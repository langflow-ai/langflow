# Genesis Agent Specification Schema Reference

Complete reference for creating Genesis Agent specifications in YAML format.

## Overview

A Genesis Agent specification defines an AI agent workflow that gets converted into a Langflow flow. Each specification contains metadata, components, and connection definitions.

## Root-Level Fields

### Basic Metadata (Required)
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `name` | string | ✓ | Human-readable agent name | `"Document Processor"` |
| `description` | string | ✓ | Brief agent description | `"Process and extract information from healthcare documents"` |
| `version` | string | ✓ | Semantic version | `"1.0.0"` |
| `agentGoal` | string | ✓ | Primary objective description | `"Extract structured information from healthcare documents using OCR and NLP"` |
| `components` | array | ✓ | List of workflow components | See [Components](#components) |

### Extended Metadata (Optional)
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `id` | string |  | Unique identifier (URN format) | `"urn:agent:genesis:accumulator_check:1"` |
| `fullyQualifiedName` | string |  | Dotted namespace identifier | `"genesis.autonomize.ai.accumulator_check"` |
| `domain` | string |  | Domain classification | `"autonomize.ai"` |
| `subDomain` | string |  | Sub-domain classification | `"benefit-validation"` |
| `environment` | string |  | Target environment | `"production"` |
| `agentOwner` | string |  | Owner email/identifier | `"benefit-validation@autonomize.ai"` |
| `agentOwnerDisplayName` | string |  | Human-readable owner | `"Benefit Validation Team"` |
| `email` | string |  | Contact email | `"benefit-validation@autonomize.ai"` |
| `status` | string |  | Deployment status | `"ACTIVE"` |

### Classification Fields
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `kind` | string |  | Agent classification | `"Single Agent"` |
| `targetUser` | string |  | Target user type | `"internal"` |
| `valueGeneration` | string |  | Value type provided | `"ProcessAutomation"` |
| `interactionMode` | string |  | Interaction pattern | `"RequestResponse"` |
| `runMode` | string |  | Execution mode | `"RealTime"` |
| `agencyLevel` | string |  | Autonomy level | `"KnowledgeDrivenWorkflow"` |
| `toolsUse` | boolean |  | Whether agent uses tools | `true` |
| `learningCapability` | string |  | Learning capabilities | `"None"` |
| `tags` | array |  | Classification tags | `["UM", "accumulator", "utilization"]` |

### Configuration Arrays
| Field | Type | Required | Description | Structure |
|-------|------|----------|-------------|-----------|
| `variables` | array |  | Configuration variables | `[{name, type, required, default, description}]` |
| `outputs` | array |  | Expected output types | `["accumulator_summary", "member_cost_estimate"]` |
| `kpis` | array |  | Key performance indicators | `[{name, category, valueType, target, unit, description}]` |

### Configuration Objects
| Field | Type | Required | Description | Structure |
|-------|------|----------|-------------|-----------|
| `reusability` | object |  | Reusability configuration | `{asTools, standalone, provides, dependencies}` |
| `sampleInput` | object |  | Example input data | `{member_id, benefit_year, ...}` |
| `promptConfiguration` | object |  | Prompt setup | `{basePromptId, customPrompt}` |
| `securityInfo` | object |  | Security classification | `{visibility, confidentiality, gdprSensitive}` |

## Components

The `components` array defines the workflow elements. Each component has this structure:

### Component Base Structure
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `id` | string | ✓ | Unique component identifier | `"document-input"` |
| `name` | string | ✓ | Human-readable component name | `"Document Input"` |
| `type` | string | ✓ | Component type identifier | `"genesis:chat_input"` |
| `description` | string | ✓ | Component purpose | `"Upload or input document for processing"` |
| `kind` | string |  | Component category | `"Data"`, `"Agent"`, `"Prompt"`, `"Tool"` |
| `config` | object |  | Component-specific configuration | Varies by type |
| `asTools` | boolean |  | Whether to expose as tool | `true` |
| `provides` | array |  | Output connections | `[{in, useAs, description}]` |

### Connection Structure (provides)
| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `in` | string | ✓ | Target component ID | `"processing-agent"` |
| `useAs` | string | ✓ | Connection type | `"input"`, `"tools"`, `"system_prompt"` |
| `description` | string | ✓ | Connection purpose | `"Send document to processing agent"` |

## Component Types

### 1. genesis:chat_input
Input component for user data entry.

**Configuration**: None
**Connections**: Connects to agents via `useAs: "input"`

```yaml
- id: document-input
  type: genesis:chat_input
  name: Document Input
  description: Upload or input document for processing
  provides:
    - in: processing-agent
      useAs: input
      description: Send document to processing agent
```

### 2. genesis:chat_output
Output component for displaying results.

**Configuration**:
```yaml
config:
  should_store_message: boolean  # Optional
```

**Connections**: Receives from agents via `useAs: "input"`

```yaml
- id: document-output
  type: genesis:chat_output
  name: Processed Document
  description: Display structured document information
```

### 3. genesis:agent
Main LLM-powered agent component.

**Configuration**:
```yaml
config:
  system_prompt: string           # Optional, can come from prompt_template
  agent_llm: string              # Optional, default: "Azure OpenAI"
  model_name: string             # Optional, default: "gpt-4"
  temperature: float             # Optional, default: 0.1
  max_tokens: integer            # Optional, default: 2000
  handle_parsing_errors: boolean # Optional
  max_iterations: integer        # Optional
  verbose: boolean               # Optional
```

**Connections**:
- Receives input via `useAs: "input"`
- Receives prompts via `useAs: "system_prompt"`
- Receives tools via `useAs: "tools"`

```yaml
- id: processing-agent
  type: genesis:agent
  name: Document Processing Agent
  description: Agent that processes and extracts information
  config:
    system_prompt: "You are a document processing specialist..."
    temperature: 0.1
    max_tokens: 2000
  provides:
    - in: document-output
      useAs: input
      description: Send processed results
```

### 4. genesis:prompt
Prompt management component.

**Configuration**:
```yaml
config:
  saved_prompt: string  # Optional, reference to saved prompt
  template: string      # Required, actual prompt text
```

**Connections**: Connects to agents via `useAs: "system_prompt"`

```yaml
- id: agent-prompt
  type: genesis:prompt
  name: Agent Instructions
  description: Prompt template for agent instructions
  config:
    saved_prompt: accumulator_check_prompt_v1
    template: "You are a benefit accumulator specialist..."
  provides:
    - useAs: system_prompt
      in: main-agent
      description: System prompt for the agent
```

### 5. genesis:mcp_tool
External tool/API integration via MCP.

**Configuration**:
```yaml
config:
  tool_name: string      # Required, MCP tool identifier
  description: string    # Required, tool description
  # Additional tool-specific parameters
```

**Connections**: Connects to agents via `useAs: "tools"`

```yaml
- id: qnxt-accumulator
  type: genesis:mcp_tool
  name: QNXT Auth History
  description: Retrieve claims and authorization history via MCP
  asTools: true
  config:
    tool_name: qnext_auth_history
    description: QNext authorization history tool
    lookback_months: 12
  provides:
    - useAs: tools
      in: accumulator-agent
      description: Real-time claims history
```

### 6. genesis:knowledge_hub_search
Internal knowledge base search component.

**Configuration**: No specific config shown in examples

**Connections**: Connects to agents via `useAs: "tools"`

```yaml
- id: knowledge-search
  type: genesis:knowledge_hub_search
  name: Knowledge Hub Search
  description: Tool for guideline retrieval agent
  asTools: true
  provides:
    - useAs: tools
      in: main-agent
      description: Knowledge Hub Search tool
```

### 7. genesis:ehr_connector
Electronic Health Record (EHR) integration component.

**Configuration**:
```yaml
config:
  ehr_system: string                   # Required: EHR system type
  fhir_version: string                 # Required: FHIR version
  authentication_type: string         # Required: Authentication method
  base_url: string                     # Required: EHR system URL
  operation: string                    # Required: Operation to perform
```

**Connections**: Connects to agents via `useAs: "tools"`

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

### 8. genesis:claims_connector
Healthcare claims processing integration component.

**Configuration**:
```yaml
config:
  clearinghouse: string                # Required: Claims clearinghouse
  payer_id: string                    # Optional: Insurance payer identifier
  provider_npi: string                # Optional: Provider NPI number
  test_mode: boolean                  # Optional: Development vs production
  operation: string                   # Required: Claims operation
```

**Connections**: Connects to agents via `useAs: "tools"`

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

### 9. genesis:eligibility_connector
Insurance eligibility verification component.

**Configuration**:
```yaml
config:
  eligibility_service: string         # Required: Eligibility service provider
  payer_list: array                  # Optional: Supported insurance payers
  provider_npi: string               # Optional: Provider NPI
  real_time_mode: boolean            # Optional: Real-time vs cached
  cache_duration_minutes: integer    # Optional: Cache duration
  operation: string                  # Required: Eligibility operation
```

**Connections**: Connects to agents via `useAs: "tools"`

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

### 10. genesis:pharmacy_connector
Pharmacy and medication management component.

**Configuration**:
```yaml
config:
  pharmacy_network: string            # Required: Pharmacy network
  prescriber_npi: string              # Optional: Prescriber NPI
  dea_number: string                  # Optional: DEA registration number
  drug_database: string               # Optional: Drug database system
  interaction_checking: boolean        # Optional: Enable drug interactions
  formulary_checking: boolean         # Optional: Enable formulary verification
  operation: string                   # Required: Pharmacy operation
```

**Connections**: Connects to agents via `useAs: "tools"`

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

## Variables Schema

Configuration variables allow parameterization:

```yaml
variables:
  - name: llm_provider
    type: string
    required: false
    default: Azure OpenAI
    description: LLM provider (AzureOpenAI, OpenAI, Anthropic, etc.)
```

### Variable Types
- `string` - Text values
- `float` - Decimal numbers
- `integer` - Whole numbers
- `boolean` - True/false values

## KPIs Schema

Key performance indicators for monitoring:

```yaml
kpis:
  - name: Accumulator Accuracy
    category: Quality
    valueType: percentage
    target: 99
    unit: '%'
    description: Accuracy of accumulator calculations
```

### KPI Categories
- `Quality` - Accuracy, precision, recall
- `Performance` - Response time, throughput

### Value Types
- `percentage` - 0-100% values
- `numeric` - Raw numbers

## Security Schema

Security classification information:

```yaml
securityInfo:
  visibility: Private        # Public, Internal, Private
  confidentiality: High      # Low, Medium, High
  gdprSensitive: true       # boolean
```

## Reusability Schema

Defines how agents can be reused:

```yaml
reusability:
  asTools: true              # Can be used as a tool
  standalone: true           # Can run independently
  provides:
    toolName: AccumulatorChecker
    toolDescription: Checks deductibles, OOP max, and benefit utilization
    inputSchema:             # JSON Schema for inputs
      type: object
      properties: {...}
    outputSchema:            # JSON Schema for outputs
      type: object
      properties: {...}
  dependencies: []           # Array of dependencies
```

## Validation Rules

1. **Required Fields**: `name`, `description`, `version`, `agentGoal`, `components`
2. **Component IDs**: Must be unique within the specification
3. **Connections**: `provides[].in` must reference existing component IDs
4. **useAs Values**: Must be valid connection types (`input`, `tools`, `system_prompt`)
5. **Component Types**: Must be valid genesis component types

## Healthcare-Specific Schema Extensions

### Healthcare Component Category
Healthcare connectors use a specific component category:
```yaml
kind: "Healthcare"                    # Optional: Healthcare component category
```

### Healthcare Domain Classification
Healthcare agents should include specific domain classification:
```yaml
domain: autonomize.ai
subDomain: healthcare-{area}          # e.g., clinical-workflow, patient-care
targetUser: internal                  # Restrict to internal users for PHI data
```

### HIPAA Compliance Metadata
Healthcare agents handling PHI data must include security metadata:
```yaml
securityInfo:
  visibility: Private                 # Required for PHI data
  confidentiality: High              # High security classification
  gdprSensitive: true               # GDPR compliance flag
```

### Healthcare KPIs
Healthcare agents should include compliance and quality metrics:
```yaml
kpis:
  - name: HIPAA Compliance Score
    category: Security
    valueType: percentage
    target: 100
    unit: '%'
    description: HIPAA compliance rating for data handling

  - name: Clinical Accuracy
    category: Quality
    valueType: percentage
    target: 98
    unit: '%'
    description: Accuracy of clinical recommendations

  - name: Workflow Completion Rate
    category: Quality
    valueType: percentage
    target: 95
    unit: '%'
    description: Percentage of healthcare workflows completed successfully
```

### Healthcare Configuration Variables
Healthcare agents commonly use these configuration variables:
```yaml
variables:
  - name: ehr_base_url
    type: string
    required: true
    description: EHR system base URL

  - name: provider_npi
    type: string
    required: true
    description: National Provider Identifier

  - name: encryption_key
    type: string
    required: true
    description: Encryption key for PHI data

  - name: audit_endpoint
    type: string
    required: true
    description: Audit logging endpoint URL
```

### Healthcare Output Types
Common healthcare output types:
```yaml
outputs:
  - patient_data_summary
  - clinical_assessment
  - treatment_recommendations
  - eligibility_verification_result
  - claims_processing_status
  - medication_interaction_analysis
  - compliance_audit_report
```

## Healthcare Validation Rules

1. **Healthcare Components**: Healthcare connectors must have `asTools: true`
2. **PHI Data Handling**: Agents handling PHI must include `securityInfo` with `confidentiality: High`
3. **Environment Variables**: Healthcare credentials must use environment variables (e.g., `"${EHR_BASE_URL}"`)
4. **HIPAA Compliance**: Healthcare agents must include HIPAA compliance KPIs
5. **Healthcare Domain**: Healthcare agents should use `subDomain` starting with "healthcare-"

## Best Practices

### General Best Practices
1. Use descriptive IDs and names for components
2. Include detailed descriptions for complex agents
3. Specify appropriate temperature values (0.1 for deterministic, higher for creative)
4. Use prompt templates for complex or reusable prompts
5. Include KPIs for production agents
6. Add security classification for sensitive agents
7. Define variables for configurable parameters
8. Use tags for discoverability

### Healthcare-Specific Best Practices
1. **Security First**: Always include HIPAA compliance metadata for PHI data
2. **Environment Variables**: Never hardcode healthcare credentials or API keys
3. **Clinical Quality**: Include clinical accuracy and guideline compliance KPIs
4. **Audit Requirements**: Define audit logging and compliance tracking variables
5. **Mock Mode**: Use test_mode configuration for development and testing
6. **Error Handling**: Implement secure error handling that doesn't expose PHI
7. **Data Minimization**: Only request necessary healthcare data fields
8. **Clinical Context**: Include clear clinical rationale in agent prompts