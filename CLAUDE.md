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

3. External Tools via MCP:
   - If tool is external API or connector, use genesis:mcp_tool
   - Document what MCP tool is needed
   - Define tool configuration
   - Specify API requirements

4. Component Mapping Gaps:
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

1. Check for Validation Module:
   - Search in: /Users/jagveersingh/Developer/studio/ai-studio/src/backend/base/langflow/
   - Look for spec validation module or function
   - Common locations:
     - spec/validator.py
     - spec/validation.py
     - utils/spec_validator.py
     - validation/spec.py

2. If Validation Function EXISTS:
   - Import and use the validation function
   - Run validation: validate_spec(spec_data)
   - Check for validation errors
   - Fix any errors found
   - Re-validate until passes
   - Report validation results

3. If Validation Function DOES NOT EXIST:
   - Create validation function in appropriate module
   - Location: /Users/jagveersingh/Developer/studio/ai-studio/src/backend/base/langflow/spec/validator.py
   - Implement comprehensive validation:

def validate_specification(spec_dict):
    """
    Validate agent specification against schema rules.
    Returns (is_valid, errors_list)
    """
    errors = []
    
    # Validate metadata
    - Check id format (URN pattern)
    - Check required fields exist
    - Validate email format
    - Check valid status value
    
    # Validate kind and characteristics
    - Check valid kind value
    - Check valid agencyLevel
    - Validate other enum fields
    
    # Validate components
    - Check all component types are known
    - Validate component structure
    - Check required component fields
    - Validate configuration against component schema
    
    # Validate relationships
    - Check provides.useAs values
    - Verify provides.in references exist
    - Check for circular dependencies
    - Validate edge creation logic
    
    # Validate tags and categorization
    - Check tags are valid strings
    - Verify domain/subDomain values
    
    return len(errors) == 0, errors

   - Create validation schema/rules
   - Add detailed error messages
   - Test with existing specs
   - Document validation function

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

Case 5: Validation Function Missing

If no validation function exists:

ACTION REQUIRED - CREATE VALIDATOR

Create: /Users/jagveersingh/Developer/studio/ai-studio/src/backend/base/langflow/spec/validator.py

Implement:
- validate_specification(spec_dict) function
- Comprehensive validation rules
- Clear error messages
- Schema compliance checking
- Component type validation
- Relationship validation

Test with existing specifications before using.

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

Ready to create specifications from requirements.

Provide requirements one at a time.