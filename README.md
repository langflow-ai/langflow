<!-- markdownlint-disable MD030 -->

![Autonomize AI Studio](./docs/static/img/autonomize-ai-studio-logo.svg)

# Autonomize AI Studio

[![GitHub star chart](https://img.shields.io/github/stars/autonomizeai/ai-studio?style=flat-square)](https://star-history.com/#autonomizeai/ai-studio)
[![License](https://img.shields.io/badge/license-Proprietary%20%2B%20MIT-blue)](./LICENSE)
[![Twitter](https://img.shields.io/twitter/url/https/twitter.com/autonomizeai.svg?style=social&label=Follow%20%40AutonomizeAI)](https://twitter.com/autonomizeai)

**Autonomize AI Studio** is the next-generation platform for building, deploying, and managing AI-powered agents through an intuitive conversational interface. Built on top of proven open-source foundations, AI Studio transforms the agent creation experience with natural language interactions, advanced healthcare-specific components, and enterprise-grade security.

## 🚀 Vision: Conversational Agent Creation

AI Studio revolutionizes how developers and domain experts create AI agents by introducing:

- **🗣️ Conversational UI**: Describe your agent in natural language - "Create a clinical diagnosis agent that uses ICD-10 codes and medical knowledge"
- **🤖 Intelligent Agent Builder**: AI-powered assistant that understands your requirements and generates complete agent specifications
- **🏥 Healthcare-First Design**: Built-in compliance, medical terminology, and clinical workflows
- **📋 YAML Specification System**: Behind-the-scenes agent specs that are human-readable and version-controllable
- **🔄 Visual Flow Editor**: Optional visual interface for fine-tuning generated agents

## ✨ Key Features

### Conversational Agent Development
- **Natural Language Agent Creation**: "Build an agent that extracts medical codes from clinical notes"
- **Intelligent Suggestions**: AI recommends components, connections, and configurations
- **Real-time Validation**: Instant feedback on agent design and compliance requirements
- **Template Library**: Healthcare-specific agent templates for common use cases

### Healthcare-Specific Components
- **Clinical Models Integration**: Unified AutonomizeModel component supporting RxNorm, ICD-10, CPT codes
- **Medical Knowledge Search**: HIPAA-compliant knowledge hub integration
- **Entity Linking**: Advanced medical entity recognition and standardization
- **Compliance Built-In**: GDPR, HIPAA, and other healthcare regulations supported out-of-the-box

### Enterprise-Ready Platform
- **MCP (Model Context Protocol)**: Native support for tool discovery and integration
- **API-First Architecture**: RESTful APIs for all agent operations
- **Scalable Deployment**: Docker, Kubernetes, and cloud-native deployment options
- **Advanced Security**: Role-based access control, audit trails, and data encryption

### Developer Experience
- **Genesis Specification Format**: YAML-based agent definitions with variable templating
- **Live Testing Environment**: Interactive playground for immediate agent validation
- **Version Control**: Full GitOps workflow support for agent specifications
- **Extensible Components**: Python-based component system for custom functionality

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Conversational  │    │   Agent Builder  │    │  Visual Flow    │
│      UI         │◄──►│      AI          │◄──►│    Editor       │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌──────────────────┐
                    │ Genesis Spec     │
                    │ Converter        │
                    └──────────────────┘
                                 │
                    ┌──────────────────┐
                    │ AI Studio        │
                    │ Runtime Engine   │
                    └──────────────────┘
```

## ⚡️ Quick Start

### Prerequisites
- [Python 3.10 to 3.13](https://www.python.org/downloads/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (recommended) or pip

### Installation

1. **Clone the repository:**
```bash
git clone https://github.com/autonomizeai/ai-studio.git
cd ai-studio
```

2. **Install dependencies:**
```bash
uv pip install -e ".[dev]"
```

3. **Start AI Studio:**
```bash
uv run langflow run --port 7860
```

4. **Open the Conversational UI:**
Navigate to `http://127.0.0.1:7860` and start creating agents with natural language!

### Creating Your First Agent

1. **Open the Agent Builder**: Click "Create New Agent" in the AI Studio interface
2. **Describe Your Agent**: "Create a medical diagnosis agent that processes clinical notes and extracts ICD-10 codes"
3. **Review Generated Spec**: The AI will generate a complete YAML specification
4. **Test and Deploy**: Use the interactive playground to validate your agent

## 🚀 Production Deployment

### Recommended Architecture (Redis + Celery)

For production environments, we strongly recommend enabling Redis and Celery to handle background tasks and caching efficiently. This architecture ensures:
- **Scalability**: Heavy tasks are offloaded to background workers.
- **Reliability**: Redis acts as a robust message broker and cache.
- **Performance**: Asynchronous processing prevents the API from blocking.

**Configuration:**

1.  **Redis**: Deploy a Redis instance (e.g., via AWS ElastiCache or a Docker container).
2.  **Celery Workers**: Run one or more Celery worker processes.
3.  **Environment Variables**:
    ```bash
    LANGFLOW_CACHE_TYPE=redis
    LANGFLOW_CELERY_ENABLED=true
    LANGFLOW_REDIS_HOST=your-redis-host
    LANGFLOW_REDIS_PORT=6379
    ```

**Running Workers:**
```bash
celery -A langflow.worker worker --loglevel=info -c 4
```

### Kubernetes / Helm

AI Studio is deployed using Helm charts maintained in the **[platform-charts](https://github.com/autonomizeai/platform-charts)** repository, following GitOps best practices.

### Quick Deploy

```bash
# Clone platform-charts repository
git clone https://github.com/autonomizeai/platform-charts.git
cd platform-charts

# Deploy full Genesis platform (recommended)
helm install genesis-platform ./charts/genesis-platform \
  --values ./charts/genesis-platform/values-dev.yaml \
  --namespace genesis-dev \
  --create-namespace

# Or deploy AI Studio standalone
helm install ai-studio ./charts/ai-studio \
  --values ./charts/ai-studio/values-dev.yaml \
  --namespace ai-studio-dev \
  --create-namespace
```

### GitOps Workflow

Production deployments are automated via ArgoCD:

1. **Code Changes** → AI Studio CI pipelines build and push images
2. **Chart Updates** → CI automatically updates image tags in platform-charts
3. **Auto Deploy** → ArgoCD detects changes and deploys to Kubernetes

For detailed deployment instructions, see the [platform-charts documentation](https://github.com/autonomizeai/platform-charts).

## 🏥 Healthcare Use Cases

### Clinical Diagnosis Assistant
```yaml
# Generated automatically from: "Create a diagnosis agent with ICD-10 coding"
id: clinical-diagnosis-agent
name: Clinical Diagnosis Assistant
agentGoal: Extract and classify medical conditions from clinical notes using ICD-10 standards
components:
  - id: clinical-input
    type: genesis:chat_input
  - id: entity-extractor
    type: genesis:combined_entity_linking
  - id: icd10-classifier
    type: genesis:icd10
  - id: medical-knowledge
    type: genesis:knowledge_hub_search
```

### Drug Interaction Checker
```yaml
# Generated from: "Build an agent that checks drug interactions using RxNorm codes"
id: drug-interaction-agent
name: Drug Interaction Checker
agentGoal: Analyze medication lists for potential interactions and contraindications
components:
  - id: medication-input
    type: genesis:chat_input
  - id: rxnorm-lookup
    type: genesis:rxnorm
  - id: interaction-analyzer
    type: genesis:clinical_llm
```

## 🔧 Development

### Project Structure
```
ai-studio-service/
├── src/backend/                    # AI Studio backend service
│   ├── base/langflow/             # Core platform (based on Langflow)
│   ├── custom/genesis/            # Autonomize-specific components
│   └── tests/                     # Comprehensive test suite
├── src/frontend/                  # Conversational UI (React/TypeScript)
├── docs/                         # Documentation and guides
└── examples/                     # Agent templates and examples
```

### Key Components

- **Genesis Specification System**: YAML-based agent definitions
- **Conversational UI**: Natural language agent creation interface
- **Component Mapper**: Maps Genesis types to platform components
- **Variable Resolver**: Template variable substitution system
- **Knowledge Service**: HIPAA-compliant medical knowledge integration

### Running Tests
```bash
# Run comprehensive test suite
cd src/backend
uv run pytest tests/ -v

# Run specific test modules
uv run pytest tests/unit/custom/genesis/ -v
```

## 📚 Documentation

- [Agent Builder Guide](./docs/agent-builder-guide.md) - Create agents with conversational UI
- [Genesis Specification Format](./docs/genesis-spec-format.md) - YAML agent definition reference
- [Healthcare Components](./docs/healthcare-components.md) - Medical AI component library
- [Deployment Guide](https://github.com/autonomizeai/platform-charts) - Production deployment with Helm charts
- [API Reference](./docs/api-reference.md) - REST API documentation

## 🔒 Security & Compliance

Autonomize AI Studio is built with healthcare-grade security:

- **HIPAA Compliance**: All data handling meets HIPAA requirements
- **GDPR Support**: Privacy controls and data protection mechanisms
- **Role-Based Access**: Granular permissions and audit trails
- **Data Encryption**: End-to-end encryption for all sensitive data
- **SOC 2 Ready**: Security controls for enterprise deployment

## 🌟 What Makes AI Studio Different

### From Langflow to AI Studio

While built on Langflow's solid foundation, AI Studio introduces:

1. **Conversational Interface**: Replace complex visual flows with natural language
2. **Healthcare Focus**: Medical AI components and compliance built-in
3. **Agent-First Design**: Optimized for building AI agents, not just workflows
4. **Enterprise Security**: Healthcare-grade security and compliance
5. **Intelligent Assistance**: AI helps you build better agents faster

### Why Choose AI Studio

- **🎯 Purpose-Built**: Designed specifically for healthcare AI agents
- **🚀 Faster Development**: Create agents in minutes, not hours
- **🔧 Enterprise Ready**: Production-grade security and scalability
- **🤝 Intuitive**: No coding required - describe what you want in plain English
- **📈 Extensible**: Full Python extensibility when you need custom components

## 🤝 Contributing

We welcome contributions from the healthcare AI community! Please see our [Contributing Guide](./CONTRIBUTING.md) for details on:

- Code contribution guidelines
- Healthcare compliance requirements
- Component development standards
- Testing and documentation expectations

## 📄 License

This project uses a dual licensing approach:

- **Proprietary Components**: Autonomize AI's custom features are proprietary
- **Open Source Components**: Based on Langflow (MIT License)

See [LICENSE](./LICENSE) for complete details.

## 🙏 Acknowledgments

AI Studio is built on the excellent foundation provided by the Langflow open source project. We extend our gratitude to the Langflow community and contributors.

---

**Ready to revolutionize your AI agent development?** [Get started with AI Studio](https://ai-studio.autonomize.ai) today!

For enterprise inquiries: [enterprise@autonomize.ai](mailto:enterprise@autonomize.ai)