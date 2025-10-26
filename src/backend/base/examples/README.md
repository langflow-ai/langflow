# Dynamic Agent Specification Framework Examples

This directory contains comprehensive examples demonstrating the capabilities of the enhanced Dynamic Agent Specification Framework.

## Example Files

### 1. `simple-agent.yaml` - Basic Single Agent
- **Purpose**: Demonstrates basic agent setup with tool integration
- **Components**: 1 Agent + 3 Tools
- **Features**:
  - Simple Agent → AgentComponent mapping
  - Tool connectivity via `provides` declarations
  - Basic configuration patterns

### 2. `crewai-workflow.yaml` - Multi-Agent Coordination
- **Purpose**: Shows complex multi-agent workflows using CrewAI
- **Components**: 3 CrewAI Agents + 4 Tools + 1 Crew Orchestrator
- **Features**:
  - CrewAIAgent → CrewAIAgentComponent mapping
  - Agent-to-agent coordination
  - Sequential workflow execution
  - Advanced tool sharing

### 3. `healthcare-agent.yaml` - HIPAA-Compliant Healthcare
- **Purpose**: Healthcare-specific workflow with compliance requirements
- **Components**: 1 Agent + 6 Healthcare Connectors + Security
- **Features**:
  - Healthcare connector integration
  - HIPAA compliance validation
  - PHI protection and encryption
  - Audit logging capabilities

### 4. `advanced-multi-agent.yaml` - Enterprise Automation
- **Purpose**: Complex enterprise workflow with hierarchical coordination
- **Components**: 4 Agents + 8 Tools + Orchestration
- **Features**:
  - Mixed agent types (Agent + CrewAI)
  - Hierarchical coordination patterns
  - Shared memory and state management
  - Advanced monitoring and observability

## Framework Features Demonstrated

### Dynamic Component Resolution
All examples leverage the enhanced framework's ability to:
- Automatically resolve component types using the `/all` endpoint
- Fallback from database mappings to dynamic discovery
- Support both built-in and custom components

### Agent Type Support
- **Simple Agents**: Standard `Agent` type → `AgentComponent`
- **CrewAI Agents**: `CrewAIAgent` type → `CrewAIAgentComponent`
- **Tool Integration**: Automatic tool connectivity via `provides` declarations

### Healthcare Compliance
The framework includes built-in support for:
- HIPAA-compliant component detection
- Healthcare connector integration
- Compliance validation and reporting

### Tool Capabilities Detection
Dynamic detection of:
- `accepts_tools`: Components that can use tools
- `provides_tools`: Components that can be used as tools
- Automatic edge generation based on capabilities

## Usage

### CLI Validation
```bash
# Validate a specification
ai-studio workflow validate examples/simple-agent.yaml

# Validate with local-only mode
ai-studio workflow validate examples/healthcare-agent.yaml --local

# Create workflow from specification
ai-studio workflow create examples/crewai-workflow.yaml
```

### Programmatic Usage
```python
from langflow.custom.specification_framework.core.specification_processor import SpecificationProcessor
from langflow.custom.specification_framework.models.processing_context import ProcessingContext

# Initialize processor
processor = SpecificationProcessor()

# Load and process specification
with open('examples/simple-agent.yaml') as f:
    spec_dict = yaml.safe_load(f)

context = ProcessingContext(
    spec_name="Simple Agent Example",
    source_path="examples/simple-agent.yaml",
    target_format="langflow"
)

result = await processor.process_specification(spec_dict, context)
```

## Configuration Patterns

### Basic Agent Configuration
```yaml
- type: Agent
  config:
    model_provider: OpenAI
    model: gpt-4
    instructions: "Your agent instructions here"
    temperature: 0.7
```

### Tool Integration
```yaml
- type: WebSearch
  id: search_tool
  provides:
    - useAs: tools
      in: main_agent
```

### CrewAI Agent Configuration
```yaml
- type: CrewAIAgent
  config:
    role: "Data Analyst"
    goal: "Analyze market data"
    backstory: "You are an expert analyst..."
    model_provider: OpenAI
    model: gpt-4
```

### Healthcare Compliance
```yaml
- type: EHRConnector
  config:
    compliance_level: "hipaa"
    encryption: "aes-256"
    audit_logging: true
```

## Performance Targets

The framework targets:
- **Processing Time**: < 2 seconds for conversion
- **Automation**: 80%+ automatic edge generation
- **Healthcare Compliance**: 100% for healthcare workflows
- **Component Discovery**: 100% success rate with dynamic fallback

## Validation Features

Each example includes validation metadata:
```yaml
validation:
  target_automation: 80
  healthcare_compliant: false
  expected_components: 4
  expected_edges: 3
```

This enables automated testing and quality assurance for generated workflows.