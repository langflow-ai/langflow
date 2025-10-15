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