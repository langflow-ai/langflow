# Creating Genesis Agent Specifications

Step-by-step guide for creating effective Genesis Agent specifications.

## Overview

This guide walks you through creating agent specifications from scratch, helping you choose the right components, patterns, and configurations for your use case.

## Table of Contents

1. [Before You Start](#before-you-start)
2. [Choosing Your Pattern](#choosing-your-pattern)
3. [Step-by-Step Creation](#step-by-step-creation)
4. [Configuration Best Practices](#configuration-best-practices)
5. [Validation and Testing](#validation-and-testing)
6. [Common Pitfalls](#common-pitfalls)
7. [Examples Walkthrough](#examples-walkthrough)

## Before You Start

### Prerequisites
- Basic understanding of YAML syntax
- Clear definition of your agent's purpose
- Understanding of your input/output requirements
- Knowledge of any external tools needed

### Planning Questions
Answer these questions before writing your specification:

1. **Purpose**: What exactly should your agent do?
2. **Input**: What data will users provide?
3. **Output**: What should the agent return?
4. **External Data**: Do you need to access external APIs or databases?
5. **Complexity**: Is this a simple task or complex workflow?
6. **Audience**: Who will use this agent?
7. **Environment**: Development, testing, or production?

## Choosing Your Pattern

Use this decision tree to select the appropriate pattern:

```
Start Here: What's your agent's complexity?

Simple Task (classification, extraction, basic processing)
└─ Do you need external data?
   ├─ No → Pattern 1: Simple Linear Agent
   └─ Yes → Pattern 3: Agent with Single Tool

Complex Task (multi-step workflow, decision making)
└─ How many external tools/APIs?
   ├─ One → Pattern 3: Agent with Single Tool
   ├─ Multiple → Pattern 4: Multi-Tool Agent
   └─ None → Pattern 1: Simple Linear Agent

Any Pattern + Considerations:
├─ Complex prompt? → Add Pattern 2: External Prompt
├─ Production use? → Add Pattern 5: Enterprise metadata
└─ Prompt reuse? → Add Pattern 2: External Prompt
```

### Pattern Quick Reference
- **Pattern 1**: Input → Agent → Output (3 components)
- **Pattern 2**: Input → Agent + Prompt Template → Output (4 components)
- **Pattern 3**: Input → Agent + Tool → Output (4-5 components)
- **Pattern 4**: Input → Agent + Multiple Tools → Output (6+ components)
- **Pattern 5**: Any pattern + Enterprise metadata

## Step-by-Step Creation

### Step 1: Create the Basic Structure

Start with the required root-level fields:

```yaml
name: "Your Agent Name"
description: "Brief description of what your agent does"
version: "1.0.0"
agentGoal: "Detailed description of the agent's primary objective"

components:
  # Components will go here
```

### Step 2: Add Input Component

Every agent needs an input component:

```yaml
components:
  - id: input
    type: genesis:chat_input
    name: "User Input"
    description: "Description of what users should input"
    provides:
      - in: main-agent  # Will connect to your main agent
        useAs: input
        description: "Send user input to agent"
```

### Step 3: Add Main Agent Component

Add your processing agent:

```yaml
  - id: main-agent
    type: genesis:agent
    name: "Your Agent Name"
    description: "Main processing logic"
    config:
      system_prompt: |
        You are a [type of specialist] agent.

        Your role is to:
        1. [First responsibility]
        2. [Second responsibility]
        3. [Third responsibility]

        Guidelines:
        - [Important guideline 1]
        - [Important guideline 2]

        Output format: [Specify expected output structure]
      temperature: 0.1  # Use 0.1 for consistent, 0.7 for creative
      max_tokens: 2000   # Adjust based on expected output length
    provides:
      - in: output
        useAs: input
        description: "Send results to output"
```

### Step 4: Add Output Component

Add the output component:

```yaml
  - id: output
    type: genesis:chat_output
    name: "Results"
    description: "Display agent results"
    config:
      should_store_message: true  # Optional: store for history
```

### Step 5: Add Tools (If Needed)

If your agent needs external data, add tool components:

#### For External APIs (MCP Tools)
```yaml
  - id: tool-name
    type: genesis:mcp_tool
    name: "Tool Display Name"
    description: "What this tool does"
    asTools: true
    config:
      tool_name: actual_tool_identifier
      description: "Tool description for the agent"
      # Tool-specific configuration parameters
    provides:
      - useAs: tools
        in: main-agent
        description: "Provide [capability] to agent"
```

#### For Knowledge Base Search
```yaml
  - id: knowledge-search
    type: genesis:knowledge_hub_search
    name: "Knowledge Search"
    description: "Search internal knowledge base"
    asTools: true
    provides:
      - useAs: tools
        in: main-agent
        description: "Provide knowledge search capability"
```

### Step 6: Add Prompt Template (If Needed)

For complex or reusable prompts:

```yaml
  - id: agent-prompt
    type: genesis:prompt
    name: "Agent Instructions"
    description: "Detailed prompt template"
    config:
      saved_prompt: your_prompt_id_v1  # Optional reference
      template: |
        [Your detailed prompt here]

        This can be multiple paragraphs with complex instructions.
    provides:
      - useAs: system_prompt
        in: main-agent
        description: "Provide system prompt to agent"
```

If using a prompt template, remove the `system_prompt` from your agent config.

### Step 7: Add Enterprise Metadata (If Needed)

For production agents, add comprehensive metadata:

```yaml
# Add after the basic fields, before components
id: urn:agent:genesis:your_domain:agent_name:1
fullyQualifiedName: genesis.your_domain.agent_name
domain: your.domain
subDomain: your-team
agentOwner: your-team@company.com
agentOwnerDisplayName: Your Team Name
email: your-team@company.com
status: ACTIVE

# Classification
kind: Single Agent
targetUser: internal
valueGeneration: ProcessAutomation
interactionMode: RequestResponse
runMode: RealTime
agencyLevel: KnowledgeDrivenWorkflow
toolsUse: true  # Set to true if using tools
learningCapability: None

# Tags for discovery
tags:
  - your-domain
  - use-case
  - classification

# Variables for configuration
variables:
  - name: temperature
    type: float
    required: false
    default: 0.1
    description: Model temperature setting

# Expected outputs
outputs:
  - primary_result
  - secondary_data

# Performance indicators
kpis:
  - name: Response Accuracy
    category: Quality
    valueType: percentage
    target: 95
    unit: '%'
    description: Accuracy of agent responses

# Security classification
securityInfo:
  visibility: Private
  confidentiality: Medium
  gdprSensitive: false
```

## Configuration Best Practices

### Agent Configuration

#### Temperature Settings
- **0.1**: Highly deterministic (classification, extraction, structured data)
- **0.3**: Mostly consistent with slight variation (analysis, summarization)
- **0.7**: Creative but controlled (content generation, brainstorming)
- **0.9**: Highly creative (creative writing, ideation)

#### Token Limits
- **500-1000**: Short responses (classification, yes/no answers)
- **1000-2000**: Medium responses (analysis, explanations)
- **2000-4000**: Long responses (detailed reports, comprehensive analysis)
- **4000+**: Very long outputs (documentation, extensive analysis)

#### Other Settings
```yaml
config:
  temperature: 0.1
  max_tokens: 2000
  max_iterations: 5      # For agents with tools
  handle_parsing_errors: true  # Robust error handling
  verbose: false         # Set true for debugging
```

### Prompt Writing Best Practices

#### Structure Your Prompts
```yaml
system_prompt: |
  You are a [role] specialist for [domain].

  Your primary responsibilities:
  1. [Responsibility 1]
  2. [Responsibility 2]
  3. [Responsibility 3]

  Guidelines:
  - [Guideline 1]
  - [Guideline 2]

  Input format: [Expected input structure]
  Output format: [Required output structure]

  Additional instructions:
  [Any special handling, edge cases, etc.]
```

#### Key Elements
1. **Role Definition**: Clearly state what the agent is
2. **Responsibilities**: List primary tasks
3. **Guidelines**: Important rules and constraints
4. **Format Specifications**: Input/output structure
5. **Examples**: Show desired behavior (if space allows)

### Tool Configuration

#### MCP Tool Best Practices
```yaml
config:
  tool_name: descriptive_tool_name
  description: "Clear description of what this tool does and when to use it"
  # Include relevant parameters
  timeout: 30000        # milliseconds
  retry_count: 3        # number of retries
  # Tool-specific parameters
```

#### Tool Descriptions
- Be specific about when the agent should use each tool
- Include parameter requirements
- Mention expected return format
- Note any limitations or constraints

## Validation and Testing

### Pre-Deployment Checklist

#### Structure Validation
- [ ] All required fields present (`name`, `description`, `version`, `agentGoal`, `components`)
- [ ] Component IDs are unique
- [ ] All `provides[].in` references exist
- [ ] `useAs` values are valid (`input`, `tools`, `system_prompt`)
- [ ] Component types are valid genesis types

#### Logical Validation
- [ ] Input component connects to an agent
- [ ] Agent connects to output component
- [ ] Tool components (if any) connect to agents
- [ ] Prompt templates (if any) connect to agents
- [ ] No circular dependencies in connections

#### Content Validation
- [ ] System prompts are clear and specific
- [ ] Tool configurations are complete
- [ ] Temperature and token settings are appropriate
- [ ] Component descriptions are helpful

### Testing Your Specification

#### 1. YAML Syntax Check
```bash
# Check YAML syntax
yaml-lint your-spec.yaml
```

#### 2. Genesis CLI Validation
```bash
# Validate with Genesis CLI (if available)
genesis validate your-spec.yaml
```

#### 3. Manual Review
- Read through the entire spec
- Verify logical flow: input → processing → output
- Check that prompts match intended behavior
- Ensure tool configurations are correct

#### 4. Test with Sample Data
- Define realistic test inputs
- Predict expected outputs
- Validate tool requirements are met

## Common Pitfalls

### 1. Unclear Agent Goals
**Problem**: Vague or generic agent goals
**Solution**: Be specific about what the agent should accomplish

❌ Bad:
```yaml
agentGoal: Help users with their requests
```

✅ Good:
```yaml
agentGoal: Extract structured patient demographics, provider information, and service details from healthcare documents using OCR and NLP
```

### 2. Missing Connections
**Problem**: Components not properly connected
**Solution**: Ensure all components have appropriate `provides` connections

❌ Bad:
```yaml
components:
  - id: input
    type: genesis:chat_input
    # Missing provides!
  - id: agent
    type: genesis:agent
```

✅ Good:
```yaml
components:
  - id: input
    type: genesis:chat_input
    provides:
      - in: agent
        useAs: input
        description: "Send input to agent"
```

### 3. Inappropriate Temperature Settings
**Problem**: Using wrong temperature for task type
**Solution**: Match temperature to task requirements

❌ Bad (for classification):
```yaml
config:
  temperature: 0.9  # Too creative for classification
```

✅ Good (for classification):
```yaml
config:
  temperature: 0.1  # Deterministic for consistent classification
```

### 4. Overly Complex Initial Designs
**Problem**: Starting with multi-tool enterprise agents
**Solution**: Begin simple, add complexity gradually

❌ Bad: Starting with 8 components and 5 tools
✅ Good: Start with 3 components, add tools as needed

### 5. Poor Tool Descriptions
**Problem**: Agents don't know when to use tools
**Solution**: Provide clear, specific tool descriptions

❌ Bad:
```yaml
config:
  tool_name: data_tool
  description: "Gets data"
```

✅ Good:
```yaml
config:
  tool_name: claims_history_api
  description: "Retrieve patient claims history for the last 12 months. Use when you need past medical services, costs, or utilization data. Requires patient ID and date range."
```

### 6. Inconsistent ID Naming
**Problem**: Random or unclear component IDs
**Solution**: Use descriptive, consistent naming

❌ Bad: `comp1`, `thing2`, `x`
✅ Good: `patient-input`, `classification-agent`, `results-output`

## Examples Walkthrough

### Example 1: Simple Document Classifier

**Requirement**: Classify healthcare documents into categories

**Pattern Choice**: Simple Linear Agent (3 components)

**Step-by-step**:

1. **Plan**: Input document → Classify → Output category
2. **Choose Pattern**: Simple Linear (no external tools needed)
3. **Create Structure**:

```yaml
name: Document Classifier
description: Classify healthcare documents into categories
version: "1.0.0"
agentGoal: Classify healthcare documents into Radiology, DME, Pharmacy, or MSK categories

components:
  - id: document-input
    type: genesis:chat_input
    name: Document Input
    description: OCR text from document to classify
    provides:
      - in: classifier-agent
        useAs: input
        description: Send document text to classifier

  - id: classifier-agent
    type: genesis:agent
    name: Classification Agent
    description: Classifies documents by type
    config:
      system_prompt: |
        You are a healthcare document classifier.

        Classify the provided document into one of these categories:
        - Radiology: MRI, CT, PET scans, X-rays, ultrasounds
        - DME: Durable Medical Equipment (wheelchairs, CPAP, oxygen)
        - Pharmacy: Medications, prescriptions, drug requests
        - MSK: Musculoskeletal (PT, OT, chiropractic, surgeries)

        Output format:
        {
          "category": "primary_category",
          "confidence": 0.95,
          "reasoning": "Brief explanation"
        }
      temperature: 0.1
      max_tokens: 500
    provides:
      - in: classification-output
        useAs: input
        description: Send classification results

  - id: classification-output
    type: genesis:chat_output
    name: Classification Results
    description: Display document classification
```

### Example 2: Agent with Knowledge Search

**Requirement**: Retrieve clinical guidelines based on procedure codes

**Pattern Choice**: Agent with Single Tool + External Prompt

**Key Decisions**:
- Need knowledge base access → Add knowledge hub search
- Complex prompt → Use prompt template
- Single tool → Single Tool pattern

```yaml
name: Guideline Retrieval Agent
description: Retrieve clinical guidelines based on procedure codes
version: "1.0.0"
agentGoal: Find applicable clinical guidelines (LCDs, NCDs) for given procedure codes

components:
  - id: input
    type: genesis:chat_input
    name: Procedure Input
    description: Procedure codes and diagnosis information
    provides:
      - in: main-agent
        useAs: input
        description: Send request to agent

  - id: agent-prompt
    type: genesis:prompt
    name: Retrieval Instructions
    description: Specialized prompt for guideline retrieval
    config:
      template: |
        You are a clinical guideline specialist.

        Your role:
        1. Analyze provided procedure and diagnosis codes
        2. Search for applicable clinical guidelines
        3. Identify relevant LCDs (Local Coverage Determinations)
        4. Find relevant NCDs (National Coverage Determinations)

        Use the Knowledge Hub Search tool to find relevant guidelines.

        Output should include:
        - Applicable guidelines found
        - Relevance to provided codes
        - Coverage requirements
        - Medical necessity criteria
    provides:
      - useAs: system_prompt
        in: main-agent
        description: Provide retrieval instructions

  - id: knowledge-search
    type: genesis:knowledge_hub_search
    name: Guideline Search
    description: Search clinical guidelines database
    asTools: true
    provides:
      - useAs: tools
        in: main-agent
        description: Provide guideline search capability

  - id: main-agent
    type: genesis:agent
    name: Guideline Retrieval Agent
    description: Retrieves applicable clinical guidelines
    config:
      temperature: 0.1
      max_tokens: 2000
    provides:
      - in: output
        useAs: input
        description: Send results

  - id: output
    type: genesis:chat_output
    name: Guidelines
    description: Display retrieved guidelines
```

## Next Steps

1. **Start Simple**: Begin with a Simple Linear Agent
2. **Test Early**: Validate your specification before adding complexity
3. **Iterate**: Add components and features incrementally
4. **Document**: Include clear descriptions for team members
5. **Monitor**: Add KPIs for production agents
6. **Maintain**: Keep specifications updated as requirements change

For more advanced topics, see:
- [Pattern Catalog](../patterns/pattern-catalog.md) - Detailed pattern examples
- [Component Reference](../components/component-catalog.md) - Complete component documentation
- [Conversion Guide](conversion-guide.md) - How specs become flows