"""Test fixtures for Genesis module testing."""

import pytest
from unittest.mock import Mock, AsyncMock
from langflow.custom.genesis.services.knowledge.service import KnowledgeService
from langflow.custom.genesis.services.knowledge.settings import KnowledgeSettings
from .sample_agent_specs import (
    SIMPLE_AGENT_SPEC,
    AGENT_WITH_TOOLS_SPEC,
    MCP_AGENT_SPEC,
    MULTI_MODEL_AGENT_SPEC,
    VARIABLE_TEMPLATE_SPEC,
    SAMPLE_RUNTIME_VARIABLES
)


@pytest.fixture
def simple_agent_spec():
    """Simple agent specification for basic testing."""
    return SIMPLE_AGENT_SPEC


@pytest.fixture
def complex_agent_spec():
    """Complex agent specification with tools and connections."""
    return AGENT_WITH_TOOLS_SPEC


@pytest.fixture
def mcp_agent_spec():
    """MCP-based agent specification."""
    return MCP_AGENT_SPEC


@pytest.fixture
def multi_model_agent_spec():
    """Multi-model agent specification."""
    return MULTI_MODEL_AGENT_SPEC


@pytest.fixture
def variable_template_spec():
    """Agent specification with variable templates."""
    return VARIABLE_TEMPLATE_SPEC


@pytest.fixture
def sample_runtime_variables():
    """Sample runtime variables for testing."""
    return SAMPLE_RUNTIME_VARIABLES


@pytest.fixture
def mock_knowledge_settings():
    """Mock KnowledgeSettings with valid configuration."""
    settings = Mock(spec=KnowledgeSettings)
    settings.ENDPOINT_URL = "http://localhost:3002"
    settings.GENESIS_CLIENT_ID = "test-client-123"
    settings.TIMEOUT = 120
    settings.USER_AGENT = "genesis_studio_test"
    settings.is_configured.return_value = True
    return settings


@pytest.fixture
def mock_knowledge_service():
    """Mock Genesis Knowledge Service."""
    service = Mock(spec=KnowledgeService)
    service.name = "knowledge_service"
    service.ready = True

    # Mock knowledge hubs data
    service.get_knowledge_hubs = AsyncMock(return_value=[
        {"id": "medical-kb", "name": "Medical Knowledge Base"},
        {"id": "drug-db", "name": "Drug Database"},
        {"id": "clinical-guidelines", "name": "Clinical Guidelines"},
        {"id": "research-papers", "name": "Research Papers"}
    ])

    # Mock query results
    service.query_vector_store = AsyncMock(return_value=[
        {
            "metadata": {
                "content": "Hypertension is a chronic medical condition characterized by elevated blood pressure.",
                "source": "medical_textbook.pdf",
                "page": 145,
                "score": 0.95,
                "category": "cardiovascular"
            }
        },
        {
            "metadata": {
                "content": "ACE inhibitors are commonly prescribed for treating high blood pressure.",
                "source": "pharmacology_guide.pdf",
                "page": 67,
                "score": 0.89,
                "category": "medications"
            }
        },
        {
            "metadata": {
                "content": "Regular exercise and dietary modifications can help manage hypertension.",
                "source": "lifestyle_medicine.pdf",
                "page": 23,
                "score": 0.87,
                "category": "lifestyle"
            }
        }
    ])

    # Mock document retrieval
    service.get_knowledge_hub_documents = AsyncMock(return_value=[
        {
            "id": "doc1",
            "name": "hypertension_guidelines.pdf",
            "type": "pdf",
            "uuid": "doc-uuid-123",
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-06-01T00:00:00Z",
            "folder": None
        },
        {
            "id": "doc2",
            "name": "clinical_notes/patient_case_studies.txt",
            "type": "txt",
            "uuid": "doc-uuid-456",
            "created_at": "2023-02-01T00:00:00Z",
            "updated_at": "2023-06-15T00:00:00Z",
            "folder": "clinical_notes"
        }
    ])

    # Mock signed URL generation
    service.get_document_signed_url = AsyncMock(
        return_value="https://s3.amazonaws.com/bucket/file.pdf?signature=test123"
    )

    return service


@pytest.fixture
def mock_component_template_service():
    """Mock component template service."""
    service = Mock()

    # Default component templates
    templates = {
        "AgentComponent": {
            "template": {
                "input_value": {"type": "str", "required": False},
                "tools": {"type": "Tool", "list": True, "required": False},
                "system_prompt": {"type": "Message", "required": False},
                "model_provider": {"type": "str", "options": ["OpenAI", "Anthropic", "Azure OpenAI"]},
                "model": {"type": "str"},
                "temperature": {"type": "float", "default": 0.7}
            },
            "outputs": [{"name": "response", "type": "Message"}]
        },
        "ChatInput": {
            "template": {
                "message": {"type": "str", "required": False}
            },
            "outputs": [{"name": "message", "type": "Message"}]
        },
        "ChatOutput": {
            "template": {
                "input_value": {"type": "Message", "required": True}
            },
            "outputs": []
        },
        "AutonomizeModel": {
            "template": {
                "search_query": {"type": "str", "required": True},
                "selected_model": {"type": "str", "options": [
                    "Clinical LLM", "RxNorm Code", "ICD-10 Code", "CPT Code",
                    "Clinical Note Classifier", "Combined Entity Linking"
                ]}
            },
            "outputs": [{"name": "prediction", "type": "Data"}]
        },
        "KnowledgeHubSearchComponent": {
            "template": {
                "search_query": {"type": "str", "required": True},
                "selected_hubs": {"type": "str", "list": True, "required": False},
                "search_type": {"type": "str", "options": ["similarity", "semantic", "keyword", "hybrid"]},
                "top_k": {"type": "int", "default": 10}
            },
            "outputs": [{"name": "query_results", "type": "Data"}]
        },
        "MCPTool": {
            "template": {
                "tool_name": {"type": "str", "required": True},
                "client_id": {"type": "str", "required": True},
                "parameters": {"type": "dict", "required": False}
            },
            "outputs": [{"name": "component_as_tool", "type": "Tool"}]
        },
        "MCPClient": {
            "template": {
                "server_name": {"type": "str", "required": True},
                "transport": {"type": "str", "options": ["stdio", "tcp", "http"]},
                "tools": {"type": "Tool", "list": True, "required": False}
            },
            "outputs": [{"name": "client", "type": "MCPClient"}]
        },
        "PromptTemplate": {
            "template": {
                "template": {"type": "str", "required": True},
                "variables": {"type": "dict", "required": False}
            },
            "outputs": [{"name": "prompt", "type": "Message"}]
        },
        "CalculatorTool": {
            "template": {
                "expression": {"type": "str", "required": True}
            },
            "outputs": [{"name": "tool_output", "type": "Tool"}]
        }
    }

    def get_template(component_name):
        return templates.get(component_name, {
            "template": {"input": {"type": "str"}},
            "outputs": [{"name": "output", "type": "Data"}]
        })

    service.get_component_template.side_effect = get_template
    return service


@pytest.fixture
def mock_flow_converter_dependencies(mock_component_template_service):
    """Mock all dependencies for FlowConverter."""
    from unittest.mock import patch

    with patch('langflow.services.spec.component_template_service.component_template_service', mock_component_template_service):
        yield mock_component_template_service


@pytest.fixture
def sample_flow_json():
    """Sample Langflow JSON structure for testing."""
    return {
        "id": "test-flow-123",
        "name": "Test Flow",
        "description": "A test flow for validation",
        "data": {
            "nodes": [
                {
                    "id": "chat-input-1",
                    "type": "genericNode",
                    "position": {"x": 100, "y": 100},
                    "measured": {"width": 320, "height": 200},
                    "data": {
                        "type": "ChatInput",
                        "node": {
                            "template": {
                                "message": {"type": "str", "value": ""}
                            },
                            "outputs": [{"name": "message", "type": "Message"}]
                        }
                    }
                },
                {
                    "id": "agent-main-1",
                    "type": "genericNode",
                    "position": {"x": 500, "y": 100},
                    "measured": {"width": 400, "height": 300},
                    "data": {
                        "type": "AgentComponent",
                        "node": {
                            "template": {
                                "input_value": {"type": "str"},
                                "tools": {"type": "Tool", "list": True},
                                "system_prompt": {"type": "Message"},
                                "model_provider": {"type": "str", "value": "OpenAI"},
                                "model": {"type": "str", "value": "gpt-3.5-turbo"}
                            },
                            "outputs": [{"name": "response", "type": "Message"}]
                        }
                    }
                }
            ],
            "edges": [
                {
                    "id": "xy-edge__chat-input-1{œnameœ:œmessageœ,œtypeœ:œMessageœ}-agent-main-1{œnameœ:œinput_valueœ,œtypeœ:œstrœ}",
                    "source": "chat-input-1",
                    "target": "agent-main-1",
                    "sourceHandle": "{œnameœ:œmessageœ,œtypeœ:œMessageœ}",
                    "targetHandle": "{œnameœ:œinput_valueœ,œtypeœ:œstrœ}",
                    "data": {
                        "sourceHandle": {
                            "name": "message",
                            "type": "Message"
                        },
                        "targetHandle": {
                            "fieldName": "input_value",
                            "type": "str"
                        }
                    }
                }
            ]
        },
        "created_at": "2023-01-01T00:00:00Z",
        "updated_at": "2023-01-01T00:00:00Z",
        "metadata": {
            "version": "1.0.0",
            "generator": "genesis_spec_converter"
        }
    }


@pytest.fixture
def knowledge_hub_query_results():
    """Sample knowledge hub query results."""
    return [
        {
            "metadata": {
                "content": "Diabetes mellitus is a group of metabolic disorders characterized by high blood sugar levels.",
                "source": "endocrinology_textbook.pdf",
                "page": 234,
                "score": 0.96,
                "category": "endocrine",
                "keywords": ["diabetes", "blood sugar", "metabolism"]
            }
        },
        {
            "metadata": {
                "content": "Metformin is the first-line medication for type 2 diabetes management.",
                "source": "diabetes_treatment_guidelines.pdf",
                "page": 45,
                "score": 0.92,
                "category": "treatment",
                "keywords": ["metformin", "type 2 diabetes", "medication"]
            }
        },
        {
            "metadata": {
                "content": "Regular monitoring of HbA1c levels is essential for diabetes management.",
                "source": "clinical_monitoring_protocols.pdf",
                "page": 78,
                "score": 0.88,
                "category": "monitoring",
                "keywords": ["HbA1c", "monitoring", "diabetes management"]
            }
        }
    ]


@pytest.fixture
def error_scenarios():
    """Common error scenarios for testing."""
    return {
        "invalid_spec": {
            "name": "Invalid Spec",
            # Missing required fields
        },
        "service_unavailable": {
            "error": "Service temporarily unavailable",
            "code": 503
        },
        "unauthorized": {
            "error": "Unauthorized access",
            "code": 401
        },
        "not_found": {
            "error": "Resource not found",
            "code": 404
        },
        "network_timeout": {
            "error": "Network request timeout",
            "code": 408
        }
    }


@pytest.fixture
def performance_test_data():
    """Data for performance testing."""
    return {
        "large_spec": {
            "id": "large-agent",
            "name": "Large Agent",
            "description": "Agent with many components for performance testing",
            "components": [
                {
                    "id": f"component-{i}",
                    "name": f"Component {i}",
                    "kind": "Tool",
                    "type": "genesis:calculator",
                    "asTools": True,
                    "provides": [{"useAs": "tools", "in": "main-agent"}]
                }
                for i in range(50)  # 50 components
            ] + [
                {
                    "id": "main-agent",
                    "name": "Main Agent",
                    "kind": "Agent",
                    "type": "genesis:agent"
                }
            ]
        },
        "large_query_results": [
            {
                "metadata": {
                    "content": f"Content chunk {i} with relevant medical information about various conditions and treatments.",
                    "source": f"medical_reference_{i}.pdf",
                    "page": i % 100 + 1,
                    "score": 0.9 - (i * 0.01),
                    "category": ["cardiology", "neurology", "oncology", "endocrinology"][i % 4]
                }
            }
            for i in range(100)  # 100 results
        ]
    }