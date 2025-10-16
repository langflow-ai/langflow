Create Agent Specifications from Requirements

CONTEXT:
You have analyzed the specification system and created comprehensive documentation. Now you will create new agent specifications based on requirements I provide. This includes single agents and multi-agent workflows.

DOCUMENTATION REFERENCE:
- Schema: /Users/jagveersingh/Developer/studio/ai-studio/src/backend/base/langflow/specifications_library/documentation/schema/specification-schema.md
- Patterns: /Users/jagveersingh/Developer/studio/ai-studio/src/backend/base/langflow/specifications_library/documentation/patterns/pattern-catalog.md
- Components: /Users/jagveersingh/Developer/studio/ai-studio/src/backend/base/langflow/specifications_library/documentation/components/component-catalog.md
- Guide: /Users/jagveersingh/Developer/studio/ai-studio/src/backend/base/langflow/specifications_library/documentation/guides/creating-specifications.md

OUTPUT LOCATIONS:
- Specifications: /Users/jagveersingh/Developer/studio/ai-studio/src/backend/base/langflow/specifications_library/
- Genesis Agent CLI: /Users/jagveersingh/Developer/studio/genesis-agent-cli/
- AI Studio: /Users/jagveersingh/Developer/studio/ai-studio/

---

CRITICAL: Specification Validation

After creating EACH specification:

1. Validate Using Spec Validation Function
   - Location: Check /Users/jagveersingh/Developer/studio/ai-studio/src/backend/base/langflow for spec validation module
   - If validation function exists:
     - Run validation on created spec
     - Fix any validation errors
     - Ensure spec passes all checks
   - If validation function does NOT exist:
     - Create validation function in spec module
     - Implement validation rules:
       - Required field checks
       - Field type validation
       - URN format validation
       - Component type validation
       - Provides relationship validation
       - Configuration schema validation
     - Return clear error messages
     - Document validation function

2. Validation Rules to Implement (if creating validator):
   - Metadata validation:
     - id follows URN format: urn:agent:genesis:[domain]:[name]:[version]
     - All required fields present (name, description, domain, etc.)
     - Valid email format for agentOwner
     - Valid status value (ACTIVE, INACTIVE, etc.)
   - Component validation:
     - All component types exist in catalog
     - Required component fields present
     - Valid provides relationships
     - Configuration matches component schema
   - Relationship validation:
     - provides.useAs values are valid
     - provides.in references exist
     - No circular dependencies
   - Configuration validation:
     - Config values match expected types
     - Required config fields present
     - Valid enum values

3. After Validation Passes:
   - Save specification file
   - Update knowledge base documentation
   - Report validation success

---

CRITICAL: Knowledge Base Maintenance

After creating and validating EACH specification:

1. Update Component Catalog if new components used
   - Add to: documentation/components/component-catalog.md
   - Document configuration schema
   - Add usage examples

2. Update Pattern Catalog if new pattern emerges
   - Add to: documentation/patterns/pattern-catalog.md
   - Define pattern characteristics
   - Provide template

3. Update Specification Schema if new fields used
   - Update: documentation/schema/specification-schema.md
   - Document new fields
   - Provide validation rules

4. Request Converter Mappings for new components
   - Identify Langflow components without spec mappers
   - Propose spec type names
   - Document in task list for implementation

This ensures the knowledge base stays current and complete for AI agent builder use.

---

WORKFLOW FOR EACH REQUIREMENT:

Step 1: Analyze Requirement

When I provide an agent/workflow requirement, analyze:

1. Purpose and Goal:
   - What is the agent/workflow supposed to do?
   - What problem does it solve?
   - What are the inputs and outputs?

2. Agent Type Decision:
   - Single Agent: One agent handles everything
   - Multi-Agent: Multiple specialized agents collaborate
   - CrewAI: Sequential or hierarchical crew coordination

3. Complexity Assessment:
   - Simple (3-4 components)
   - Intermediate (5-6 components)
   - Advanced (7+ components)
   - Multi-Agent (8+ components with CrewAI coordination)

4. Pattern Selection:
   - Simple Linear Agent
   - Agent with External Prompt
   - Agent with Single Tool
   - Multi-Tool Agent
   - Enterprise Agent
   - Multi-Agent Workflow (CrewAI Sequential)
   - Multi-Agent Workflow (CrewAI Hierarchical)
   - Or combination/variation?

5. Component Requirements:
   - What components are needed?
   - Input/output types
   - Processing logic (single or multiple agents)
   - Tools required (genesis components or MCP)
   - Prompts needed
   - Coordination mechanisms (CrewAI crew/tasks)

---

Step 2: Tool and Component Identification

For each tool/capability needed:

1. Check Existing Genesis Components:
   - genesis:chat_input / genesis:chat_output
   - genesis:agent
   - genesis:prompt_template
   - genesis:knowledge_hub_search
   - genesis:mcp_tool
   - genesis:crewai_agent
   - genesis:crewai_sequential_task
   - genesis:crewai_sequential_crew
   - genesis:crewai_hierarchical_crew
   - Any others in component catalog

2. Check Langflow Components:
   - Search in /Users/jagveersingh/Developer/studio/ai-studio/src/backend/base/langflow/components/
   - Look for components that match requirement
   - Document component capabilities
   - Check if spec mapper exists

3. API Components vs MCP Tools:

   **Use genesis:api_request for:**
   - Direct HTTP API calls (REST, GraphQL endpoints)
   - Simple external service integration
   - Standard authentication (API keys, Bearer tokens)
   - Known endpoint URLs with predictable responses

   **Use genesis:mcp_tool for:**
   - Complex healthcare-specific integrations
   - Multi-step workflows requiring state management
   - Domain-specific data transformations
   - Tools requiring specialized business logic
   - When MCP servers provide additional capabilities

   **API Request Configuration:**
   - Supports all HTTP methods: GET, POST, PUT, PATCH, DELETE
   - Secure header handling for API keys and auth tokens
   - Body support for POST/PUT/PATCH operations
   - Query parameter and timeout configuration
   - Use environment variables for sensitive data

4. MCP Tool Requirements:
   - If using genesis:mcp_tool, MUST provide mock template
   - Document what MCP tool is needed
   - Define tool configuration and expected responses
   - Specify API requirements and data structures

5. Component Mapping Gaps:
   - If Langflow component exists but no spec mapper:
     - Document the component with WARNING
     - Note its location
     - Propose spec type name (genesis:component_name)
     - Add to mapping task list
     - We will add mapper support

---

Step 3: Create Specification

Create complete YAML specification:

1. Metadata Section (REQUIRED):

id: urn:agent:genesis:[domain]:[name]:[version]
name: [Clear descriptive name]
fullyQualifiedName: genesis.autonomize.ai.[name]
description: [What it does - be specific]
domain: autonomize.ai
subDomain: [category like patient-experience, fraud-detection]
version: 1.0.0
environment: production
agentOwner: [team@autonomize.ai]
agentOwnerDisplayName: [Team Name]
email: [team@autonomize.ai]
status: ACTIVE

2. Kind and Characteristics:

kind: Single Agent OR Multi Agent
agentGoal: [Clear goal statement]
targetUser: internal/external/customer
valueGeneration: ProcessAutomation/InsightGeneration/DecisionSupport/etc.
interactionMode: RequestResponse/Streaming/Batch
runMode: RealTime/Scheduled
agencyLevel: [ReflexiveAgent/ModelBasedReflexAgent/GoalBasedAgent/UtilityBasedAgent/LearningAgent/KnowledgeDrivenWorkflow]
toolsUse: true/false
learningCapability: None/Supervised/Reinforcement/etc.

3. Variables (if needed):
   - Configuration variables
   - Environment-specific settings
   - Default values

4. Tags:
   - Categorization tags
   - Use case tags
   - Domain tags

5. Reusability (if applicable):
   - asTools: true/false
   - Standalone capability
   - Tool interface definition

6. Sample Input/Output:
   - Example inputs
   - Expected outputs
   - Data structures

7. Components Section:
   - Input component (genesis:chat_input)
   - Prompt components (genesis:prompt_template if needed)
   - Tools (genesis:knowledge_hub_search, genesis:mcp_tool, etc.)
   - Agent component(s):
     - Single: genesis:agent
     - Multi: genesis:crewai_agent (multiple)
   - Tasks (genesis:crewai_sequential_task if CrewAI)
   - Crew coordination (genesis:crewai_sequential_crew if CrewAI)
   - Output component (genesis:chat_output)
   - Proper provides relationships between ALL components

8. Outputs:
   - List expected output fields
   - Data types
   - Descriptions

9. KPIs (if applicable):
   - Performance metrics
   - Quality metrics
   - Business metrics

10. Security Info (if handling sensitive data):
    - Visibility
    - Confidentiality level
    - GDPR sensitivity
    - Compliance requirements

---

Step 4: Validate Specification

BEFORE saving the specification:

1. Use Existing Validation Service:
   - Location: /Users/jagveersingh/Developer/studio/ai-studio/src/backend/base/langflow/services/spec/service.py
   - The SpecService class has a validate_spec(spec_yaml) method
   - This is the proper validation function used by the API endpoint /api/v1/spec/validate

2. Validation Process:
   - Load specification YAML content
   - Use SpecService().validate_spec(spec_yaml) method
   - Check validation result for errors and warnings
   - Fix any errors found in specification
   - Re-validate until passes
   - Report validation results

3. Validation Implementation Details:
   - SpecService.validate_spec() returns: {"valid": bool, "errors": list, "warnings": list}
   - Validates basic structure: required fields (name, description, agentGoal, components)
   - Validates component structure and types
   - Checks component mappings and provides relationships
   - No need to create separate validation function

4. Validation Output:
   - If PASS: Proceed to save specification
   - If FAIL: 
     - Display all validation errors
     - Fix errors in specification
     - Re-validate
     - Repeat until passes

---

Step 5: Categorization and Placement

After validation passes, determine where to save the spec:

Existing Categories:
- agents/simple/ - Simple linear agents
- agents/multi-tool/ - Agents with multiple tools
- agents/knowledge-base/ - Agents using knowledge search
- agents/specialized/ - Domain-specific single agents
- agents/multi-agent/ - Multi-agent CrewAI workflows
- agents/patient-experience/ - Healthcare patient workflows
- agents/fraud-detection/ - Fraud and compliance workflows
- agents/prior-authorization/ - PA automation workflows

Create new categories as needed for:
- Domain-specific groupings
- Use case groupings
- Workflow type groupings

Save as: [category]/[agent-name].yaml

---

Step 6: Update Knowledge Base Documentation

IMMEDIATELY after saving validated specification:

1. Check if new components were used:
   - Add to documentation/components/component-catalog.md
   - Full component documentation
   - Configuration schema
   - Usage examples

2. Check if new pattern emerged:
   - Add to documentation/patterns/pattern-catalog.md
   - Pattern definition
   - Template specification
   - When to use guidance

3. Check if schema extended:
   - Update documentation/schema/specification-schema.md
   - Document new fields
   - Add validation rules
   - Provide examples

4. List new converter mappings needed:
   - Component name and location
   - Proposed spec type
   - Configuration fields
   - Add to converter task list

5. Update validation rules if needed:
   - Add new field validations
   - Update schema constraints
   - Document validation changes

---

Step 7: Documentation Output

For each created spec, provide:

1. Validation Results:
   - Validation status (PASSED/FAILED)
   - Any errors found and fixed
   - Final validation confirmation

2. Specification Summary:
   - Name and purpose
   - Single or multi-agent
   - Pattern used
   - Components included
   - Category placement
   - File path

3. Architecture Overview:
   - Flow diagram description
   - Component relationships
   - Data flow
   - Agent coordination (if multi-agent)

4. Component Justification:
   - Why each component was chosen
   - Tool selection rationale
   - Configuration decisions
   - Multi-agent coordination approach (if applicable)

5. New Mappings Needed (if any):
   - List all unmapped components
   - Proposed spec type names
   - Component locations
   - Required for converter implementation

6. Usage Example:
   - Sample input with realistic data
   - Expected output structure
   - Use case scenarios
   - Agent interaction flow (if multi-agent)

7. Implementation Notes:
   - Dependencies required
   - External API requirements
   - Alternative approaches
   - Performance considerations

8. Knowledge Base Updates:
   - What was added to component catalog
   - What was added to pattern catalog
   - Schema changes made
   - Validation rules updated
   - Mapping tasks created

---

SPECIAL CASES TO HANDLE:

Case 1: Multi-Agent Workflow (CrewAI)

For requirements needing multiple specialized agents:

kind: Multi Agent

Use CrewAI components:
- genesis:crewai_agent (multiple agents with roles)
- genesis:crewai_sequential_task (tasks for each agent)
- genesis:crewai_sequential_crew OR genesis:crewai_hierarchical_crew

Define:
- Each agent's role, goal, backstory
- Tasks with expected outputs
- Sequential or hierarchical coordination
- Tool assignments per agent
- Memory and delegation settings

Case 2: Langflow Component Without Spec Mapper

When component exists in Langflow but no spec support:

WARNING - NEW MAPPING REQUIRED

Component: [Component name]
Location: [file path]
Proposed Spec Type: genesis:[type_name]
Purpose: [description]
Configuration: [key fields]
Priority: [High/Medium/Low]

Add to converter mapping task list.

Case 3: External Tool via MCP

For external APIs, connectors, or services:

- id: [tool-id]
  name: [Tool Name]
  kind: Tool
  type: genesis:mcp_tool
  description: [What the tool does]
  asTools: true
  config:
    tool_name: [mcp_tool_identifier]
    description: [Tool description for agent context]
  provides:
  - useAs: tools
    in: [agent-id]
    description: [How agent uses this tool]

Document external dependencies and API requirements.

Case 4: Custom Processing Logic

If requirement needs capabilities not available:

NOTE - CUSTOM COMPONENT NEEDED

Requirement: [description]
Suggested Approach: [implementation strategy]
Alternative: [workaround if possible]
Complexity: [estimation]

Discuss feasibility and alternatives.

Case 5: Using Existing Validation Service

The validation function already exists in the SpecService:

VALIDATION SERVICE AVAILABLE

Location: /Users/jagveersingh/Developer/studio/ai-studio/src/backend/base/langflow/services/spec/service.py

Implementation:
- SpecService.validate_spec(spec_yaml) method
- Comprehensive validation rules already implemented
- Returns {"valid": bool, "errors": list, "warnings": list}
- Used by API endpoint /api/v1/spec/validate
- Validates structure, components, and relationships

Use this existing service for all specification validation.

---

VALIDATION CHECKLIST:

Before finalizing each specification:

Pre-Validation:
- [ ] Specification created with all sections
- [ ] All required fields present
- [ ] Configuration complete
- [ ] Relationships defined

Automated Validation:
- [ ] Validation function executed
- [ ] All validation errors fixed
- [ ] Re-validated successfully
- [ ] Validation passed

Manual Validation:
- [ ] Proper URN format for id
- [ ] Description is clear and specific
- [ ] Components use valid types
- [ ] Configuration optimized
- [ ] Sample input/output realistic

Quality Checks:
- [ ] Follows schema standards
- [ ] Matches appropriate pattern
- [ ] Component choices justified
- [ ] Security considerations addressed
- [ ] KPIs aligned with goals

Multi-Agent Specific (if applicable):
- [ ] Agent roles clearly defined
- [ ] Tasks have expected outputs
- [ ] Crew coordination specified
- [ ] Tool assignments clear
- [ ] Agent communication flow documented

Knowledge Base:
- [ ] New components documented
- [ ] New patterns documented
- [ ] Schema updates made
- [ ] Validation rules updated
- [ ] Mapping tasks created
- [ ] Examples added

---

OUTPUT FORMAT FOR EACH REQUIREMENT:

When I provide a requirement, respond with:

1. Analysis:
   - Requirement summary
   - Single agent or multi-agent decision with rationale
   - Complexity level
   - Pattern selected with justification
   - Components needed with descriptions

2. Component Mapping:
   - Existing genesis components to use
   - MCP tools needed with descriptions
   - CrewAI components (if multi-agent)
   - New mappings required with WARNING notices
   - External dependencies

3. Complete Specification:
   - Full YAML spec
   - Proper formatting
   - All required sections complete
   - Inline comments for clarity

4. Validation Results:
   - Validation status
   - Errors found and fixed (if any)
   - Final validation confirmation
   - Validator status (exists/created)

5. File Placement:
   - Recommended category with rationale
   - File name (kebab-case)
   - Full path

6. Documentation:
   - Architecture overview
   - Component justifications
   - Usage examples with realistic data
   - Implementation notes
   - Alternative approaches

7. Knowledge Base Updates:
   - Components added to catalog
   - Patterns added to catalog
   - Schema updates made
   - Validation rules updated
   - Mapping tasks created

---

EXECUTION WORKFLOW:

For each requirement I provide:

1. Analyze thoroughly
2. Make agent type decision (single vs multi)
3. Select appropriate pattern
4. Identify all components needed
5. Check for mapping gaps
6. Create complete specification
7. VALIDATE specification (create validator if needed)
8. Fix any validation errors
9. Save to appropriate category
10. Update knowledge base documentation
11. Provide comprehensive output
12. List any follow-up tasks (mappings, custom components, validator)

---

CRITICAL: MCP Mock Template Requirements

When using genesis:mcp_tool in specifications, you MUST ensure mock templates exist for development without MCP servers.

Mock Template Creation Process:

1. Check Existing Mock Templates:
   - Location: /Users/jagveersingh/Developer/studio/ai-studio/src/backend/base/langflow/components/agents/mcp_component.py
   - Dictionary: MOCK_TOOL_TEMPLATES
   - Verify tool_name has corresponding mock template

2. Create New Mock Templates (if missing):
   - Add to MOCK_TOOL_TEMPLATES dictionary
   - Include realistic healthcare data structures
   - Use clinical terminology and medical codes
   - Provide comprehensive input/output schemas
   - Include KPIs, metrics, and actionable insights

3. Mock Template Structure:
```python
"tool_name": {
    "name": "Tool Display Name",
    "description": "Clear description of tool functionality",
    "input_schema": {
        "param1": {"type": "string", "description": "Parameter description"},
        "param2": {"type": "array", "description": "Array parameter with enum", "enum": ["opt1", "opt2"]}
    },
    "mock_response": {
        "realistic_healthcare_data": "with_clinical_terminology",
        "metrics": {"accuracy": 0.95, "processing_time_ms": 234},
        "actionable_insights": ["recommendation1", "recommendation2"]
    }
}
```

4. Healthcare Mock Standards:
   - Use FHIR-compatible data structures
   - Include medical codes (ICD-10, CPT, HCPCS, NDC)
   - Provide realistic patient demographics
   - Include quality metrics and KPIs
   - Add healthcare workflow status information
   - Use industry-standard terminology

5. Automatic Mock Fallback:
   - MCP component automatically falls back to mock mode
   - Timeout detection triggers mock mode
   - Seamless server migration when available
   - No specification changes required

---

MCP MARKETPLACE PREPARATION

Future MCP Marketplace Integration:

1. Mock Template Catalog:
   - Complete mock coverage for all healthcare tools
   - Standardized metadata and descriptions
   - Tool categorization and tagging
   - Usage examples and documentation

2. Tool Discovery Standards:
   - Consistent naming conventions (tool_name format)
   - Comprehensive tool descriptions
   - Input/output schema documentation
   - Healthcare domain categorization

3. Marketplace Metadata:
   - Tool provider information
   - Version compatibility
   - Dependencies and requirements
   - Performance characteristics
   - Security and compliance information

4. Integration Guidelines:
   - Server connection protocols (STDIO, SSE)
   - Authentication and authorization
   - Rate limiting and timeout handling
   - Error handling and fallback strategies

5. Quality Assurance:
   - Mock template validation
   - Healthcare data accuracy
   - Clinical terminology consistency
   - Performance benchmarking

---

API REQUEST vs MCP TOOL DECISION FRAMEWORK

Use this decision tree when selecting components:

**Choose genesis:api_request when:**
- ✅ Simple HTTP REST API call
- ✅ Standard authentication (API key, Bearer token)
- ✅ Direct endpoint with known response format
- ✅ Minimal data transformation required
- ✅ Performance-critical operations
- ✅ Well-documented public APIs

**Choose genesis:mcp_tool when:**
- ✅ Healthcare-specific data processing
- ✅ Complex multi-step workflows
- ✅ Domain-specific business logic
- ✅ State management required
- ✅ Specialized data transformations
- ✅ Integration with healthcare systems
- ✅ Tools requiring mock fallback capability

**API Request Configuration Examples:**

```yaml
# GET with authentication
- id: api-get-secure
  type: genesis:api_request
  config:
    method: "GET"
    url_input: "https://api.healthcare.gov/v1/eligibility"
    headers: [
      {"key": "Authorization", "value": "Bearer ${HEALTHCARE_API_TOKEN}"},
      {"key": "Content-Type", "value": "application/json"}
    ]
    timeout: 30

# POST with JSON body
- id: api-post-data
  type: genesis:api_request
  config:
    method: "POST"
    url_input: "https://api.example.com/submit"
    headers: [
      {"key": "X-API-Key", "value": "${API_KEY}"},
      {"key": "Content-Type", "value": "application/json"}
    ]
    body: [
      {"key": "patient_id", "value": "PAT123"},
      {"key": "action", "value": "eligibility_check"}
    ]
```

**Security Best Practices:**
- Never hardcode API keys or tokens in specifications
- Use environment variables: ${VARIABLE_NAME}
- Implement proper error handling
- Configure appropriate timeouts
- Use HTTPS endpoints only

Ready to create specifications from requirements.

Provide requirements one at a time.

---

# HEALTHCARE CONNECTOR IMPLEMENTATION PLAN

## Overview
This section defines the comprehensive implementation plan for healthcare-specific connector components as part of Epic AUTPE-6043 "AI Studio - Readiness & Launch - 1st Release". These connectors provide specialized integration capabilities for healthcare systems and workflows.

## Healthcare Connector Architecture

### Base Healthcare Connector Pattern
All healthcare connectors follow a standardized architecture for consistency and maintainability:

```python
class HealthcareConnectorBase(Component):
    """Base class for all healthcare connectors."""

    display_name: str = "Healthcare Connector"
    description: str = "Base healthcare integration component"
    icon: str = "Heart"  # Healthcare-themed icon

    def __init__(self):
        super().__init__()
        self.mock_mode = True  # Default to mock for development
        self.hipaa_compliant = True

    def validate_healthcare_data(self, data: Dict[str, Any]) -> bool:
        """HIPAA-compliant data validation."""
        # Validate PHI/PII handling
        # Check data structure compliance
        # Verify required healthcare fields
        pass

    def process_healthcare_request(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Core processing with medical data handling."""
        # Healthcare-specific business logic
        # Error handling for medical data
        # Audit logging for compliance
        pass

    def format_healthcare_response(self, response: Any) -> Dict[str, Any]:
        """Standardize medical data response format."""
        # FHIR-compatible output structure
        # Healthcare metrics inclusion
        # Compliance metadata
        pass

    def get_mock_response(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Provide realistic healthcare mock data."""
        # Return comprehensive mock healthcare data
        # Include medical terminology and codes
        # Provide realistic patient scenarios
        pass
```

### Healthcare Connector Types

#### 1. EHR Healthcare Connector (AUTPE-6162)
**Purpose**: Electronic Health Record integration
**Component**: `EHRConnector`
**Genesis Type**: `genesis:ehr_connector`

**Capabilities**:
- FHIR R4 resource management (Patient, Observation, Condition, Medication)
- HL7 message processing (ADT, ORM, ORU, SIU)
- Epic MyChart and Cerner PowerChart integration patterns
- Patient data retrieval, updates, and synchronization
- Clinical documentation and care coordination

**Configuration Schema**:
```yaml
config:
  ehr_system: "epic" | "cerner" | "allscripts" | "athenahealth"
  fhir_version: "R4" | "STU3" | "DSTU2"
  authentication_type: "oauth2" | "basic" | "api_key"
  base_url: "${EHR_BASE_URL}"
  client_id: "${EHR_CLIENT_ID}"
  client_secret: "${EHR_CLIENT_SECRET}"
  timeout_seconds: 30
```

**Mock Data Structure**:
- Realistic patient demographics (HIPAA-compliant test data)
- Clinical observations with LOINC codes
- Medication lists with RxNorm codes
- Condition records with ICD-10 codes
- Provider and facility information

#### 2. Claims Healthcare Connector (AUTPE-6163)
**Purpose**: Health insurance claims processing
**Component**: `ClaimsConnector`
**Genesis Type**: `genesis:claims_connector`

**Capabilities**:
- 837 EDI transaction submission (Professional, Institutional, Dental)
- 835 EDI remittance advice processing
- Prior authorization request and status checking
- Claims status inquiry (276/277 transactions)
- Real-time adjudication and payment posting

**Configuration Schema**:
```yaml
config:
  clearinghouse: "change_healthcare" | "availity" | "relay_health"
  payer_id: "${PAYER_ID}"
  provider_npi: "${PROVIDER_NPI}"
  submitter_id: "${SUBMITTER_ID}"
  authentication_type: "x12" | "api_key" | "oauth2"
  test_mode: true | false
  timeout_seconds: 45
```

**Mock Data Structure**:
- Sample 837 claim submissions with CPT/HCPCS codes
- 835 remittance advice with payment details
- Prior authorization responses with approval/denial status
- Claims status responses with processing stages

#### 3. Eligibility Healthcare Connector (AUTPE-6164)
**Purpose**: Insurance eligibility verification
**Component**: `EligibilityConnector`
**Genesis Type**: `genesis:eligibility_connector`

**Capabilities**:
- Real-time benefit verification (270/271 EDI transactions)
- Coverage determination and benefit summaries
- Network provider validation and search
- Copay, deductible, and out-of-pocket calculations
- Plan comparison and recommendation

**Configuration Schema**:
```yaml
config:
  eligibility_service: "availity" | "change_healthcare" | "navinet"
  payer_list: ["aetna", "anthem", "cigna", "humana", "united_health"]
  provider_npi: "${PROVIDER_NPI}"
  api_key: "${ELIGIBILITY_API_KEY}"
  real_time_mode: true | false
  cache_duration_minutes: 15
```

**Mock Data Structure**:
- Patient eligibility responses with coverage details
- Benefit summaries with copay/deductible information
- Network provider directories
- Coverage verification status and effective dates

#### 4. Pharmacy Healthcare Connector (AUTPE-6165)
**Purpose**: Pharmacy and medication management
**Component**: `PharmacyConnector`
**Genesis Type**: `genesis:pharmacy_connector`

**Capabilities**:
- E-prescribing integration (NCPDP SCRIPT standard)
- Drug interaction checking and clinical decision support
- Formulary verification and alternative suggestions
- Prior authorization for medications (ePA)
- Medication therapy management (MTM)

**Configuration Schema**:
```yaml
config:
  pharmacy_network: "surescripts" | "ncpdp" | "relay_health"
  prescriber_npi: "${PRESCRIBER_NPI}"
  dea_number: "${DEA_NUMBER}"
  drug_database: "first_databank" | "medi_span" | "lexicomp"
  interaction_checking: true | false
  formulary_checking: true | false
```

**Mock Data Structure**:
- E-prescription responses with NDC codes
- Drug interaction alerts with severity levels
- Formulary status with tier information
- Prior authorization requirements and forms

### Genesis Component Mappings (AUTPE-6166)

**ComponentMapper Updates**:
```python
# Healthcare Connectors
self.HEALTHCARE_MAPPINGS = {
    "genesis:ehr_connector": {
        "component": "EHRConnector",
        "config": {
            "ehr_system": "epic",
            "fhir_version": "R4",
            "authentication_type": "oauth2"
        },
        "dataType": "Data",
        "category": "healthcare"
    },
    "genesis:claims_connector": {
        "component": "ClaimsConnector",
        "config": {
            "clearinghouse": "change_healthcare",
            "test_mode": True
        },
        "dataType": "Data",
        "category": "healthcare"
    },
    "genesis:eligibility_connector": {
        "component": "EligibilityConnector",
        "config": {
            "eligibility_service": "availity",
            "real_time_mode": True,
            "cache_duration_minutes": 15
        },
        "dataType": "Data",
        "category": "healthcare"
    },
    "genesis:pharmacy_connector": {
        "component": "PharmacyConnector",
        "config": {
            "pharmacy_network": "surescripts",
            "interaction_checking": True,
            "formulary_checking": True
        },
        "dataType": "Data",
        "category": "healthcare"
    }
}
```

### Healthcare UI Category (AUTPE-6161)

**Component Sidebar Organization**:
- Category Name: "Healthcare Connectors"
- Icon: Medical cross or heart symbol
- Color Theme: Healthcare blue (#0066CC)
- Components: EHR, Claims, Eligibility, Pharmacy connectors

**UI Integration Requirements**:
- Drag-and-drop functionality from healthcare category
- Component search within healthcare category
- Category state persistence across user sessions
- Responsive design for different screen sizes
- Consistent with existing Langflow UI patterns

### Security and Compliance

#### HIPAA Compliance Patterns
```python
class HIPAACompliantMixin:
    """Mixin for HIPAA-compliant data handling."""

    def validate_phi_access(self, user_context: Dict[str, Any]) -> bool:
        """Validate user authorization for PHI access."""
        pass

    def log_phi_access(self, action: str, data_elements: List[str]) -> None:
        """Log PHI access for audit trail."""
        pass

    def anonymize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove or mask PHI elements."""
        pass

    def encrypt_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypt sensitive healthcare data."""
        pass
```

#### Security Best Practices
- **Environment Variables**: Never hardcode healthcare API credentials
- **Data Encryption**: Encrypt PHI data in transit and at rest
- **Access Logging**: Comprehensive audit trails for healthcare data access
- **Data Minimization**: Only process necessary healthcare data elements
- **Timeout Handling**: Appropriate timeouts for healthcare API calls
- **Error Handling**: Secure error messages that don't expose PHI

### Healthcare Specification Patterns (AUTPE-6168)

#### EHR Data Extraction Workflow
```yaml
id: urn:agent:genesis:autonomize.ai:ehr-data-extraction:1.0.0
name: EHR Data Extraction Agent
kind: Single Agent
subDomain: healthcare-integration
agentGoal: Extract and process patient data from EHR systems

components:
  - id: input
    type: genesis:chat_input

  - id: ehr-tool
    type: genesis:ehr_connector
    config:
      ehr_system: "epic"
      fhir_version: "R4"
    provides:
    - useAs: tools
      in: agent

  - id: agent
    type: genesis:agent
    config:
      system_message: "Extract patient data from EHR following HIPAA guidelines"

  - id: output
    type: genesis:chat_output
```

#### Claims Processing Automation
```yaml
id: urn:agent:genesis:autonomize.ai:claims-processing:1.0.0
name: Claims Processing Agent
kind: Multi Agent
subDomain: revenue-cycle-management

components:
  - id: claims-tool
    type: genesis:claims_connector

  - id: eligibility-tool
    type: genesis:eligibility_connector

  - id: verification-agent
    type: genesis:crewai_agent
    config:
      role: "Eligibility Verification Specialist"

  - id: submission-agent
    type: genesis:crewai_agent
    config:
      role: "Claims Submission Specialist"
```

### Mock Template Standards

#### Healthcare Mock Data Requirements
```python
HEALTHCARE_MOCK_TEMPLATES = {
    "ehr_patient_search": {
        "name": "EHR Patient Search",
        "description": "Search for patients in EHR system",
        "input_schema": {
            "patient_id": {"type": "string", "description": "Patient identifier"},
            "search_criteria": {"type": "object", "description": "Search parameters"}
        },
        "mock_response": {
            "patients": [
                {
                    "id": "PAT-001",
                    "name": {"family": "Doe", "given": ["John", "Q"]},
                    "gender": "male",
                    "birthDate": "1975-05-15",
                    "mrn": "MRN123456789",
                    "active": True
                }
            ],
            "total_results": 1,
            "processing_time_ms": 245
        }
    },

    "claims_submission": {
        "name": "Claims Submission",
        "description": "Submit healthcare claim for processing",
        "input_schema": {
            "claim_data": {"type": "object", "description": "837 claim data"},
            "payer_id": {"type": "string", "description": "Insurance payer identifier"}
        },
        "mock_response": {
            "submission_id": "SUB-789456123",
            "status": "accepted",
            "control_number": "ICN-001122334",
            "submission_timestamp": "2025-01-16T10:30:00Z",
            "estimated_processing_days": 7
        }
    }
}
```

#### Medical Terminology Standards
- **ICD-10**: International Classification of Diseases codes
- **CPT**: Current Procedural Terminology codes
- **HCPCS**: Healthcare Common Procedure Coding System
- **LOINC**: Logical Observation Identifiers Names and Codes
- **SNOMED CT**: Systematized Nomenclature of Medicine Clinical Terms
- **RxNorm**: Normalized naming system for clinical drugs
- **NDC**: National Drug Code directory

### Implementation Timeline

#### Phase 1: Foundation (Week 1)
**AUTPE-6161**: Healthcare UI Category
- Frontend component sidebar modifications
- Healthcare category registration
- Icon and styling implementation
- Component organization structure

**AUTPE-6162**: EHR Healthcare Connector
- Base connector architecture
- FHIR R4 integration patterns
- Mock template creation
- Unit test implementation

#### Phase 2: Core Connectors (Week 2)
**AUTPE-6163**: Claims Healthcare Connector
- EDI transaction processing
- Prior authorization integration
- Claims status functionality

**AUTPE-6164**: Eligibility Healthcare Connector
- Real-time benefit verification
- Coverage determination logic
- Network provider validation

**AUTPE-6165**: Pharmacy Healthcare Connector
- E-prescribing integration
- Drug interaction checking
- Formulary verification

#### Phase 3: Integration (Week 3)
**AUTPE-6166**: Genesis Component Mappings
- ComponentMapper updates
- Type compatibility validation
- Integration testing

**AUTPE-6167**: Fix All Specifications
- Validation of existing 22 specifications
- Error fixes and updates
- Healthcare connector integration

#### Phase 4: Specifications & Documentation (Week 4)
**AUTPE-6168**: New Healthcare Specifications
- 5 comprehensive healthcare workflows
- Real-world use case demonstrations
- Validation and testing

**AUTPE-6169**: Documentation Updates
- Component catalog updates
- Pattern documentation
- Usage examples and tutorials

### Quality Assurance

#### Testing Requirements
- **Unit Tests**: 80%+ coverage for all healthcare connectors
- **Integration Tests**: End-to-end healthcare workflow testing
- **Mock Testing**: Comprehensive mock scenario coverage
- **Security Testing**: HIPAA compliance validation
- **Performance Testing**: Healthcare API timeout and load testing

#### Success Criteria
- [ ] 4 healthcare connectors fully implemented and functional
- [ ] Healthcare category properly organized in Langflow UI
- [ ] All existing specifications validate and convert successfully
- [ ] 5 new healthcare specifications created and validated
- [ ] Complete Genesis mapping support for all connectors
- [ ] Comprehensive documentation and usage examples
- [ ] HIPAA compliance patterns implemented throughout
- [ ] Full test coverage meeting quality standards

This healthcare connector implementation provides the specialized integration capabilities needed for AI Studio's production readiness in healthcare environments, ensuring HIPAA compliance and industry-standard connectivity.

---

# INTEGRATED IMPLEMENTATION PLAN: Healthcare Connectors + Architectural Enhancements

## Overview
This integrated plan combines healthcare connector implementation (AUTPE-6164-6172) with foundational architectural enhancements (AUTPE-6153-6156) to create a robust, scalable platform for healthcare AI workflows.

## Epic Integration Strategy

### Primary Epic: AUTPE-6043 "AI Studio - Readiness & Launch - 1st Release"

**Combined Approach**: Implement healthcare connectors alongside architectural improvements to maximize foundation strength and future scalability.

### Integrated Implementation Phases

#### Phase 1: Foundation & Architecture (Week 1-2)
**Foundational Enhancements** (AUTPE-6153-6156):
- **AUTPE-6153**: Runtime-Agnostic Database Schema for Component Mappings
- **AUTPE-6154**: Refactor Converter Architecture for Multi-Runtime Support
- **AUTPE-6155**: Component Configuration Schema Validation
- **AUTPE-6156**: Component Gap Analysis Tool

**Healthcare Foundation** (AUTPE-6164-6165):
- **AUTPE-6164**: Create Healthcare Connector Category in UI
- **AUTPE-6165**: Implement EHR Healthcare Connector

#### Phase 2: Healthcare Connectors Implementation (Week 2-3)
**Core Healthcare Connectors** (AUTPE-6166-6168):
- **AUTPE-6166**: Implement Claims Healthcare Connector
- **AUTPE-6167**: Implement Eligibility Healthcare Connector
- **AUTPE-6168**: Implement Pharmacy Healthcare Connector

**Enhanced Integration** (AUTPE-6169):
- **AUTPE-6169**: Update Genesis Component Mappings (enhanced with database support)

#### Phase 3: Integration & Validation (Week 3-4)
**System Integration** (AUTPE-6170-6172):
- **AUTPE-6170**: Fix All Specifications in Library
- **AUTPE-6171**: Create New Healthcare Connector Specifications
- **AUTPE-6172**: Update Documentation and Patterns

## Enhanced Healthcare Connector Architecture with Architectural Improvements

### Database-Driven Healthcare Connector Mappings (AUTPE-6153 Integration)

**Enhanced ComponentMapper with Database Support**:
```python
# Healthcare connectors stored in database with versioning
class DatabaseHealthcareMapping:
    id: int
    genesis_type: str  # "genesis:ehr_connector"
    component_name: str  # "EHRConnector"
    runtime_type: str  # "langflow", "temporal", "kafka"
    config_schema: dict  # JSON schema for validation
    version: str  # "1.0.0"
    active: bool
    healthcare_metadata: dict  # HIPAA, compliance info
    created_at: datetime

# Runtime adapter for healthcare connectors
class HealthcareRuntimeAdapter:
    genesis_type: str
    langflow_config: dict
    temporal_config: dict  # Future support
    kafka_config: dict     # Future support
    validation_rules: dict
```

### Multi-Runtime Healthcare Workflow Support (AUTPE-6154 Integration)

**Enhanced Converter Architecture for Healthcare**:
```python
# Base healthcare converter interface
class HealthcareConverterBase(ABC):
    @abstractmethod
    def convert_healthcare_workflow(self, spec: Dict) -> Dict:
        """Convert healthcare spec to target runtime."""
        pass

    @abstractmethod
    def validate_hipaa_compliance(self, spec: Dict) -> bool:
        """Validate HIPAA compliance patterns."""
        pass

# Langflow healthcare converter
class LangflowHealthcareConverter(HealthcareConverterBase):
    def convert_healthcare_workflow(self, spec: Dict) -> Dict:
        # Enhanced with healthcare-specific validation
        # HIPAA compliance checking
        # Healthcare connector optimization
        pass

# Future: Temporal healthcare converter
class TemporalHealthcareConverter(HealthcareConverterBase):
    def convert_healthcare_workflow(self, spec: Dict) -> Dict:
        # Convert to Temporal workflow for long-running healthcare processes
        pass
```

### Enhanced Configuration Schema Validation for Healthcare (AUTPE-6155 Integration)

**Healthcare-Specific Configuration Schemas**:
```python
HEALTHCARE_CONFIG_SCHEMAS = {
    "genesis:ehr_connector": {
        "type": "object",
        "properties": {
            "ehr_system": {
                "type": "string",
                "enum": ["epic", "cerner", "allscripts", "athenahealth"]
            },
            "fhir_version": {
                "type": "string",
                "enum": ["R4", "STU3", "DSTU2"]
            },
            "authentication_type": {
                "type": "string",
                "enum": ["oauth2", "basic", "api_key"]
            },
            "hipaa_compliance": {
                "type": "boolean",
                "default": True
            },
            "audit_logging": {
                "type": "boolean",
                "default": True
            }
        },
        "required": ["ehr_system", "fhir_version"],
        "healthcare_validation": {
            "phi_handling": True,
            "encryption_required": True,
            "audit_trail": True
        }
    },

    "genesis:claims_connector": {
        "type": "object",
        "properties": {
            "clearinghouse": {
                "type": "string",
                "enum": ["change_healthcare", "availity", "relay_health"]
            },
            "edi_version": {
                "type": "string",
                "enum": ["5010", "4010"]
            },
            "test_mode": {
                "type": "boolean",
                "default": True
            }
        },
        "healthcare_validation": {
            "edi_compliance": True,
            "claims_validation": True
        }
    },

    # Additional healthcare connector schemas...
}

# Enhanced validation with healthcare compliance
class HealthcareConfigValidator:
    def validate_healthcare_config(self, component_type: str, config: Dict) -> ValidationResult:
        # Standard JSON schema validation
        # Healthcare-specific compliance validation
        # HIPAA requirement checking
        # Security pattern validation
        pass
```

### Component Gap Analysis for Healthcare (AUTPE-6156 Integration)

**Healthcare-Focused Component Analysis**:
```python
class HealthcareComponentAnalyzer:
    def analyze_healthcare_gaps(self) -> HealthcareGapReport:
        """Identify components relevant to healthcare workflows."""
        gaps = {
            "high_priority_healthcare": [
                # Components with direct healthcare relevance
                "FHIRClient", "HL7Parser", "MedicalCoder",
                "DrugDatabase", "ProviderDirectory"
            ],
            "medium_priority_healthcare": [
                # Components useful for healthcare workflows
                "PDFProcessor", "DataTransformer", "Scheduler"
            ],
            "compliance_required": [
                # Components needing HIPAA compliance
                "FileProcessor", "DatabaseConnector", "APIClient"
            ]
        }
        return self._generate_healthcare_mapping_recommendations(gaps)

    def _generate_healthcare_mapping_recommendations(self, gaps: Dict) -> List[MappingRecommendation]:
        recommendations = []
        for component in gaps["high_priority_healthcare"]:
            recommendations.append(MappingRecommendation(
                component_name=component,
                proposed_genesis_type=f"genesis:{component.lower()}",
                healthcare_priority="high",
                hipaa_requirements=self._assess_hipaa_requirements(component),
                integration_complexity="medium"
            ))
        return recommendations
```

## Enhanced Implementation Timeline (4 Weeks)

### Week 1: Foundation + Healthcare UI
**Architecture Foundation**:
- **Day 1-2**: AUTPE-6153 - Database schema for component mappings
- **Day 3-4**: AUTPE-6155 - Configuration schema validation (including healthcare)
- **Day 5**: AUTPE-6164 - Healthcare connector category in UI

**Deliverables**: Database-driven mapping system, enhanced validation, healthcare UI category

### Week 2: Enhanced Architecture + EHR Connector
**Multi-Runtime Architecture**:
- **Day 1-2**: AUTPE-6154 - Refactor converter architecture
- **Day 3-5**: AUTPE-6165 - EHR Healthcare Connector (with enhanced validation)

**Deliverables**: Pluggable converter system, EHR connector with database mappings

### Week 3: Healthcare Connectors + Analysis
**Core Healthcare Implementation**:
- **Day 1-2**: AUTPE-6166 - Claims Healthcare Connector
- **Day 3**: AUTPE-6167 - Eligibility Healthcare Connector
- **Day 4**: AUTPE-6168 - Pharmacy Healthcare Connector
- **Day 5**: AUTPE-6156 - Component gap analysis tool

**Deliverables**: All 4 healthcare connectors, gap analysis tool

### Week 4: Integration + Enhancement
**System Integration**:
- **Day 1**: AUTPE-6169 - Enhanced Genesis mappings (database-driven)
- **Day 2-3**: AUTPE-6170 - Fix all specifications with enhanced validation
- **Day 4**: AUTPE-6171 - New healthcare specifications
- **Day 5**: AUTPE-6172 - Documentation updates

**Deliverables**: Complete integrated system with documentation

## Enhanced Benefits of Integrated Approach

### Technical Benefits
- **Database-Driven Mappings**: Dynamic component registration, versioning support
- **Multi-Runtime Ready**: Future-proofed for Temporal, Kafka, other runtimes
- **Enhanced Validation**: Healthcare-specific configuration validation
- **Gap Analysis**: Automated identification of missing healthcare components
- **Scalable Architecture**: Pluggable components, runtime adapters

### Healthcare-Specific Benefits
- **HIPAA Compliance**: Built-in compliance validation and patterns
- **Clinical Workflow Support**: Optimized for healthcare use cases
- **Interoperability**: FHIR, HL7, EDI standards support
- **Regulatory Readiness**: Audit logging, data encryption, PHI protection
- **Extensibility**: Easy addition of new healthcare connectors

### Long-Term Platform Benefits
- **Runtime Flexibility**: Support for multiple execution environments
- **Component Ecosystem**: Automated discovery and mapping of new components
- **Quality Assurance**: Comprehensive validation at multiple levels
- **Developer Experience**: Enhanced tooling and documentation
- **Enterprise Readiness**: Scalable, compliant, production-ready architecture

## Risk Mitigation with Integrated Approach

### Technical Risks
- **Complexity Management**: Phased implementation reduces integration complexity
- **Migration Risk**: Database fallback to hardcoded mappings ensures continuity
- **Performance Impact**: Optimized database queries and caching strategies

### Healthcare Risks
- **Compliance Risk**: Built-in HIPAA validation and compliance patterns
- **Data Security**: Enhanced encryption and audit logging from day one
- **Integration Complexity**: Standardized healthcare connector patterns

### Project Risks
- **Timeline Risk**: Parallel development of architecture and healthcare features
- **Quality Risk**: Enhanced validation catches issues early
- **Scope Creep**: Clear phase boundaries and deliverables

This integrated approach provides a robust foundation for healthcare AI workflows while future-proofing the platform for additional runtimes and use cases.

---

# ENHANCEMENT PLAN: Type Validation and Missing Mappings

## Phase 1: Enhanced Type Compatibility Validation

### 1.1 Add Type Compatibility Validation to SpecService
- **Location**: `src/backend/base/langflow/services/spec/service.py`
- **Enhancement**: Add `_validate_component_type_compatibility()` method
- **Features**:
  - Pre-validate output→input type matching for all `provides` connections
  - Use ComponentMapper's I/O mappings to get accurate type information
  - Validate tool mode consistency (`asTools: true` + `useAs: tools` + Tool output type)
  - Check multi-tool agent capabilities
  - Validate field mapping compatibility

### 1.2 Expand Type Compatibility Matrix
- **Location**: `src/backend/base/langflow/custom/genesis/spec/converter.py`
- **Enhancement**: Extend `compatible` dictionary with more type combinations
- **Add Support For**:
  - Document types (Document → Data, Data → Document)
  - Tool chain compatibility (Tool → Agent, Agent → Data → Tool)
  - Extended type conversions

## Phase 2: Runtime-Agnostic Component Mapping Architecture

### 2.1 Database Schema for Extensible Mappings
**Create runtime-agnostic component mapping system**:
```sql
-- Component mappings (runtime-independent)
CREATE TABLE component_mappings (
    id SERIAL PRIMARY KEY,
    genesis_type VARCHAR(100), -- "genesis:agent"
    base_config JSONB,
    io_mapping JSONB,
    component_category VARCHAR(50), -- "agent", "tool", "data", "prompt"
    created_at TIMESTAMP,
    active BOOLEAN DEFAULT true
);

-- Runtime adapters (separate table for extensibility)
CREATE TABLE runtime_adapters (
    id SERIAL PRIMARY KEY,
    genesis_type VARCHAR(100), -- "genesis:agent"
    runtime_type VARCHAR(50),  -- "langflow", "temporal", "kafka" (future)
    target_component VARCHAR(100), -- "Agent"
    adapter_config JSONB,
    version VARCHAR(20),
    active BOOLEAN DEFAULT true
);
```

### 2.2 Converter Architecture Refactor
**Create extensible converter system**:
- **Location**: `src/backend/base/langflow/services/runtime/`
- **Create**: `base_converter.py` - Abstract converter interface
- **Create**: `factory.py` - Runtime converter factory
- **Refactor**: Current FlowConverter → `langflow_converter.py`
- **Features**:
  - Pluggable runtime support
  - Future-ready for Temporal, Kafka, Airflow
  - Runtime capability validation

### 2.3 Missing Langflow Component Mappings
**Add to current ComponentMapper (transitional)**:
```python
# CrewAI missing mappings
"genesis:crewai_hierarchical_task": {"component": "HierarchicalTask", "config": {}},
"genesis:crewai_hierarchical_crew": {"component": "HierarchicalCrew", "config": {}},

# Data processing
"genesis:directory_loader": {"component": "Directory", "config": {}},
"genesis:file_loader": {"component": "File", "config": {}},

# External services
"genesis:tavily_search": {"component": "TavilySearch", "config": {}},
"genesis:serper_search": {"component": "SerperSearch", "config": {}},
```

## Phase 3: Comprehensive Validation Rules

### 3.1 Component Configuration Schema Validation
- **Create**: `src/backend/base/langflow/services/spec/config_schemas.py`
- **Features**:
  - Define configuration schemas for each genesis component type
  - Validate config field types, required fields, and constraints
  - MCP tool name validation

### 3.2 Advanced Edge Validation
- **Enhancement**: Add to `_validate_components_enhanced()`
- **Validation Rules**:
  - Tool mode consistency checking
  - Multi-input validation (agents accepting multiple tools)
  - Circular dependency detection (enhanced)
  - Field compatibility pre-checking

### 3.3 Type Compatibility Matrix Enhancement
- **Expand compatibility rules**:
  - Document ↔ Data conversion
  - Tool → Agent → Output chains
  - Extended type conversion patterns

## Phase 4: Missing Component Discovery

### 4.1 Component Gap Analysis Tool
- **Create**: `src/backend/base/langflow/services/spec/component_analyzer.py`
- **Features**:
  - Scan all Langflow components
  - Identify unmapped components
  - Generate proposed genesis mappings
  - Priority ranking for relevance

### 4.2 Automated Mapping Generation
- **Features**:
  - Auto-generate I/O type mappings from component inspection
  - Suggest genesis type names based on component functionality
  - Component classification

## Implementation Priority

### Week 1: Critical Validation & Current Mappings
1. Type compatibility validation in SpecService
2. Tool mode consistency validation
3. Missing Langflow component mappings (immediate need)

### Week 2: Runtime-Agnostic Architecture
4. Database schema for extensible mappings
5. Converter architecture refactor (base classes + factory)
6. Configuration schema validation

### Week 3: Enhanced Validation & Automation
7. Advanced edge validation rules
8. Component gap analysis tool
9. Automated mapping generation

## Low Priority Improvements (Future)
- Healthcare-optimized validation rules
- Domain-specific edge validation
- Advanced workflow pattern validation

## Expected Outcomes
- **100% accurate** type compatibility validation before conversion
- **Complete mapping coverage** for existing Langflow components
- **Automated detection** of missing mappings
- **Zero failed conversions** due to type mismatches

## Phase 4: Real Component Schema Validation (AUTPE-6151 Extension)

### 4.1 Component Schema Inspector
- **Create**: `src/backend/base/langflow/services/spec/component_schema_inspector.py`
- **Features**:
  - Dynamically scan all Langflow components in `/components/` directory
  - Extract actual input/output field definitions from component classes
  - Cache component schemas for performance
  - Support for custom components and their schemas

### 4.2 Enhanced ComponentMapper Integration
- **Enhancement**: Update ComponentMapper to use real component introspection
- **Features**:
  - Replace hardcoded I/O mappings with real component inspection
  - Add fallback to hardcoded mappings for backward compatibility
  - Dynamic discovery of component input/output schemas
  - Support for dynamically loaded components

### 4.3 Comprehensive Edge Connection Validation
- **Enhancement**: Add port-level validation in SpecService
- **Features**:
  - Validate actual input/output port names (e.g., "input_value", "message")
  - Check port availability and constraints
  - Validate multiple input/output scenarios
  - Component-specific connection rules
  - Connection cardinality validation (1-to-many, many-to-1)

### 4.4 Live Component Validation
- **Features**:
  - Validate against actual component input/output schemas
  - Real-time validation updates when components change
  - Support for conditional connections based on component configuration
  - Comprehensive edge rules for complex routing scenarios

---

# DEVELOPMENT WORKFLOW RULES

## Branch and Commit Guidelines

### Branch Naming Convention
- Create feature branch for each JIRA story: `feature/AUTPE-XXXX-brief-description`
- Example: `feature/AUTPE-6151-type-compatibility-validation`
- Use lowercase with hyphens for readability

### Commit Guidelines
- **NEVER** include "Claude" or "claude" keyword in commit messages
- Use present tense, imperative mood for commit messages
- Format: `Add [feature/fix]: brief description`
- Examples:
  - `Add enhanced type compatibility validation to SpecService`
  - `Fix component mapping registration for CrewAI components`
  - `Update validation rules for tool mode consistency`

### Git Workflow Process
1. **Start Story**: Create branch from main with story ID
2. **Development**: Follow reflection workflow with unit tests
3. **Complete Story**: Commit all changes to feature branch
4. **Push**: Push feature branch to remote repository
5. **Manual PR**: User will create pull request manually

### Unit Testing Requirements
- **Minimum 80% code coverage** for new code
- Write tests BEFORE implementing functionality (TDD approach)
- Use pytest framework for consistency
- Test files: `test_[module_name].py` in same directory or tests/ folder
- Mock external dependencies appropriately

### Reflection Workflow
For each implementation:
1. **Plan**: Break down story into smaller tasks
2. **Design**: Create high-level design and interfaces
3. **Test First**: Write comprehensive unit tests
4. **Implement**: Code to make tests pass
5. **Refactor**: Clean up code while keeping tests green
6. **Review**: Self-review code for quality and completeness
7. **Validate**: Run full test suite and validation checks

### Code Quality Standards
- Follow PEP 8 Python style guidelines
- Add type hints for all function parameters and returns
- Include comprehensive docstrings for classes and methods
- Handle errors gracefully with appropriate exception handling
- Log important operations for debugging and monitoring

### Implementation Completion Criteria
For each JIRA story to be considered complete:
- [ ] All acceptance criteria implemented and tested
- [ ] Unit tests written with minimum 80% coverage
- [ ] Code follows style guidelines and quality standards
- [ ] Integration tests pass (if applicable)
- [ ] Documentation updated (docstrings, comments)
- [ ] Self-review completed using reflection workflow
- [ ] Feature branch created with story ID
- [ ] All changes committed to feature branch
- [ ] Feature branch pushed to remote repository

### Story Transition Process
1. **In Progress**: Move JIRA ticket to "In Progress" when starting
2. **Development**: Implement following reflection workflow
3. **Testing**: Ensure all tests pass and coverage requirements met
4. **Review**: Complete self-review and quality checks
5. **Done**: Move JIRA ticket to "Done" when all criteria met
6. **Branch Management**: Push feature branch for manual PR creation

### Dependencies and Integration
- Coordinate changes across multiple files/modules
- Update related documentation and configuration
- Test integration points thoroughly
- Consider backward compatibility impact
- Update API documentation if endpoints change

## Quality Assurance Checklist
Before marking any story as complete:
- [ ] Functionality works as specified in acceptance criteria
- [ ] Unit tests written and passing (80%+ coverage)
- [ ] Integration tests passing (if applicable)
- [ ] Code follows established patterns and conventions
- [ ] Error handling implemented appropriately
- [ ] Logging added for important operations
- [ ] Documentation updated (code comments, docstrings)
- [ ] No hardcoded values or security vulnerabilities
- [ ] Performance impact considered and acceptable
- [ ] Feature branch created, committed, and pushed