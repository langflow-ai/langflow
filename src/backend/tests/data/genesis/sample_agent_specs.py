"""Sample agent specifications for testing."""

# Simple agent specification
SIMPLE_AGENT_SPEC = {
    "id": "simple-agent",
    "name": "Simple Test Agent",
    "description": "A simple agent for testing",
    "components": [
        {
            "id": "chat-input",
            "name": "Chat Input",
            "kind": "Input",
            "type": "genesis:chat_input"
        },
        {
            "id": "agent-main",
            "name": "Main Agent",
            "kind": "Agent",
            "type": "genesis:agent"
        },
        {
            "id": "chat-output",
            "name": "Chat Output",
            "kind": "Output",
            "type": "genesis:chat_output"
        }
    ]
}

# Agent with tools and connections
AGENT_WITH_TOOLS_SPEC = {
    "id": "clinical-agent",
    "name": "Clinical Diagnosis Agent",
    "description": "An agent for clinical diagnosis with medical tools",
    "domain": "Healthcare",
    "subDomain": "Diagnostics",
    "version": "1.2.0",
    "environment": "production",
    "agentGoal": "Assist healthcare professionals with clinical diagnosis",
    "components": [
        {
            "id": "chat-input",
            "name": "Patient Input",
            "kind": "Input",
            "type": "genesis:chat_input",
            "description": "Input for patient symptoms and medical history"
        },
        {
            "id": "medical-knowledge",
            "name": "Medical Knowledge Search",
            "kind": "Knowledge",
            "type": "genesis:knowledge_hub_search",
            "config": {
                "search_type": "semantic",
                "top_k": 10
            },
            "provides": [
                {
                    "useAs": "context",
                    "in": "clinical-agent"
                }
            ]
        },
        {
            "id": "icd10-tool",
            "name": "ICD-10 Code Lookup",
            "kind": "Tool",
            "type": "genesis:icd10",
            "asTools": True,
            "config": {
                "selected_model": "ICD-10 Code"
            },
            "provides": [
                {
                    "useAs": "tools",
                    "in": "clinical-agent"
                }
            ]
        },
        {
            "id": "rxnorm-tool",
            "name": "Drug Code Lookup",
            "kind": "Tool",
            "type": "genesis:rxnorm",
            "asTools": True,
            "config": {
                "selected_model": "RxNorm Code"
            },
            "provides": [
                {
                    "useAs": "tools",
                    "in": "clinical-agent"
                }
            ]
        },
        {
            "id": "clinical-agent",
            "name": "Clinical Diagnosis Agent",
            "kind": "Agent",
            "type": "genesis:agent",
            "config": {
                "model_provider": "OpenAI",
                "model": "gpt-4",
                "temperature": 0.3,
                "system_prompt": "You are an expert clinical assistant. Use the available tools to help with diagnosis."
            }
        },
        {
            "id": "diagnosis-output",
            "name": "Diagnosis Output",
            "kind": "Output",
            "type": "genesis:chat_output",
            "description": "Clinical diagnosis and recommendations"
        }
    ],
    "variables": [
        {
            "name": "openai_api_key",
            "type": "string",
            "required": True,
            "description": "OpenAI API key for the language model"
        },
        {
            "name": "knowledge_hub_endpoint",
            "type": "string",
            "required": False,
            "default": "http://localhost:3002",
            "description": "Endpoint for the knowledge hub service"
        },
        {
            "name": "max_diagnosis_count",
            "type": "integer",
            "required": False,
            "default": 5,
            "description": "Maximum number of differential diagnoses to consider"
        }
    ],
    "kpis": [
        {
            "name": "Diagnostic Accuracy",
            "category": "Quality",
            "valueType": "percentage",
            "target": 95,
            "unit": "%",
            "description": "Percentage of correct primary diagnoses"
        },
        {
            "name": "Response Time",
            "category": "Performance",
            "valueType": "number",
            "target": 30,
            "unit": "seconds",
            "description": "Average time to provide diagnosis"
        }
    ],
    "security": {
        "visibility": "Internal",
        "confidentiality": "High",
        "gdprSensitive": True
    },
    "reusability": {
        "asTools": False,
        "standalone": True,
        "dependencies": [
            {"type": "service", "name": "knowledge_hub"},
            {"type": "api", "name": "openai"}
        ]
    }
}

# MCP-based agent specification
MCP_AGENT_SPEC = {
    "id": "mcp-agent",
    "name": "MCP Integration Agent",
    "description": "Agent demonstrating MCP (Model Context Protocol) integration",
    "domain": "Integration",
    "version": "1.0.0",
    "components": [
        {
            "id": "mcp-client",
            "name": "MCP Client",
            "kind": "Client",
            "type": "genesis:mcp_client",
            "config": {
                "server_name": "file_operations",
                "transport": "stdio"
            }
        },
        {
            "id": "file-tool",
            "name": "File Operations Tool",
            "kind": "Tool",
            "type": "genesis:mcp_tool",
            "asTools": True,
            "config": {
                "tool_name": "read_file",
                "client_id": "mcp-client"
            },
            "provides": [
                {
                    "useAs": "tools",
                    "in": "mcp-agent-main"
                }
            ]
        },
        {
            "id": "system-prompt",
            "name": "System Instructions",
            "kind": "Prompt",
            "type": "genesis:prompt",
            "config": {
                "template": "You are a helpful assistant that can read and analyze files. Use the file operations tool when needed."
            },
            "provides": [
                {
                    "useAs": "system_prompt",
                    "in": "mcp-agent-main"
                }
            ]
        },
        {
            "id": "mcp-agent-main",
            "name": "MCP Agent",
            "kind": "Agent",
            "type": "genesis:agent",
            "config": {
                "model_provider": "Anthropic",
                "model": "claude-3-sonnet",
                "temperature": 0.7
            }
        }
    ],
    "variables": [
        {
            "name": "anthropic_api_key",
            "type": "string",
            "required": True,
            "description": "Anthropic API key"
        },
        {
            "name": "mcp_server_path",
            "type": "string",
            "required": False,
            "default": "/usr/local/bin/file-server",
            "description": "Path to MCP server executable"
        }
    ]
}

# Complex multi-model agent specification
MULTI_MODEL_AGENT_SPEC = {
    "id": "multi-model-agent",
    "name": "Multi-Model Healthcare Agent",
    "description": "Complex agent using multiple AI models for comprehensive healthcare analysis",
    "domain": "Healthcare",
    "subDomain": "Multi-Modal Analysis",
    "version": "2.0.0",
    "agentGoal": "Provide comprehensive healthcare analysis using multiple specialized models",
    "components": [
        {
            "id": "patient-input",
            "name": "Patient Data Input",
            "kind": "Input",
            "type": "genesis:chat_input"
        },
        {
            "id": "clinical-classifier",
            "name": "Clinical Note Classifier",
            "kind": "Model",
            "type": "genesis:clinical_note_classifier",
            "config": {
                "selected_model": "Clinical Note Classifier",
                "confidence_threshold": 0.8
            }
        },
        {
            "id": "entity-linker",
            "name": "Medical Entity Linker",
            "kind": "Model",
            "type": "genesis:combined_entity_linking",
            "config": {
                "selected_model": "Combined Entity Linking",
                "link_confidence": 0.7
            }
        },
        {
            "id": "clinical-llm",
            "name": "Clinical Language Model",
            "kind": "Model",
            "type": "genesis:clinical_llm",
            "config": {
                "selected_model": "Clinical LLM",
                "temperature": 0.2,
                "max_tokens": 1000
            }
        },
        {
            "id": "knowledge-search",
            "name": "Medical Knowledge Search",
            "kind": "Knowledge",
            "type": "genesis:knowledge_hub_search",
            "config": {
                "search_type": "hybrid",
                "top_k": 15
            }
        },
        {
            "id": "orchestrator-agent",
            "name": "Healthcare Orchestrator",
            "kind": "Agent",
            "type": "genesis:agent",
            "config": {
                "model_provider": "Azure OpenAI",
                "model": "gpt-4",
                "temperature": 0.3,
                "system_prompt": "You are a healthcare orchestrator that coordinates multiple AI models for comprehensive patient analysis."
            }
        },
        {
            "id": "analysis-output",
            "name": "Comprehensive Analysis Output",
            "kind": "Output",
            "type": "genesis:chat_output"
        }
    ],
    "variables": [
        {
            "name": "azure_openai_endpoint",
            "type": "string",
            "required": True,
            "description": "Azure OpenAI endpoint URL"
        },
        {
            "name": "azure_openai_key",
            "type": "string",
            "required": True,
            "description": "Azure OpenAI API key"
        },
        {
            "name": "autonomize_api_key",
            "type": "string",
            "required": True,
            "description": "Autonomize API key for clinical models"
        },
        {
            "name": "knowledge_hub_ids",
            "type": "array",
            "required": False,
            "default": ["medical-kb", "drug-interactions", "clinical-guidelines"],
            "description": "List of knowledge hub IDs to search"
        }
    ],
    "kpis": [
        {
            "name": "Clinical Accuracy",
            "category": "Quality",
            "valueType": "percentage",
            "target": 98,
            "unit": "%"
        },
        {
            "name": "Processing Time",
            "category": "Performance",
            "valueType": "number",
            "target": 45,
            "unit": "seconds"
        },
        {
            "name": "Entity Linking Precision",
            "category": "Quality",
            "valueType": "percentage",
            "target": 92,
            "unit": "%"
        }
    ]
}

# Invalid agent specification for error testing
INVALID_AGENT_SPEC = {
    "name": "Invalid Agent",
    # Missing required 'id' field
    "description": "An invalid agent specification for testing error handling",
    "components": [
        {
            # Missing required 'id' and 'type' fields
            "name": "Incomplete Component",
            "kind": "Agent"
        }
    ]
}

# Agent with variable templates for resolver testing
VARIABLE_TEMPLATE_SPEC = {
    "id": "template-agent",
    "name": "Template Test Agent",
    "description": "Agent for testing variable template resolution",
    "components": [
        {
            "id": "configured-agent",
            "name": "Configured Agent",
            "kind": "Agent",
            "type": "genesis:agent",
            "config": {
                "api_key": "{{api_key}}",
                "model": "{{model_name}}",
                "temperature": "{{temperature}}",
                "endpoint": "https://{{host}}:{{port}}/{{path}}",
                "timeout": "{{timeout_seconds}}",
                "enabled": "{{is_enabled}}",
                "connection": {
                    "host": "{{db_host}}",
                    "port": "{{db_port}}",
                    "credentials": {
                        "username": "{{db_user}}",
                        "password": "{{db_password}}"
                    }
                }
            }
        }
    ],
    "variables": [
        {
            "name": "api_key",
            "type": "string",
            "required": True,
            "description": "API key for external service"
        },
        {
            "name": "model_name",
            "type": "string",
            "required": False,
            "default": "gpt-3.5-turbo",
            "description": "Model name to use"
        },
        {
            "name": "temperature",
            "type": "float",
            "required": False,
            "default": 0.7,
            "description": "Model temperature"
        },
        {
            "name": "host",
            "type": "string",
            "required": False,
            "default": "api.example.com",
            "description": "API host"
        },
        {
            "name": "port",
            "type": "integer",
            "required": False,
            "default": 443,
            "description": "API port"
        },
        {
            "name": "path",
            "type": "string",
            "required": False,
            "default": "v1/chat",
            "description": "API path"
        },
        {
            "name": "timeout_seconds",
            "type": "integer",
            "required": False,
            "default": 30,
            "description": "Request timeout in seconds"
        },
        {
            "name": "is_enabled",
            "type": "boolean",
            "required": False,
            "default": True,
            "description": "Whether the service is enabled"
        },
        {
            "name": "db_host",
            "type": "string",
            "required": True,
            "description": "Database host"
        },
        {
            "name": "db_port",
            "type": "integer",
            "required": False,
            "default": 5432,
            "description": "Database port"
        },
        {
            "name": "db_user",
            "type": "string",
            "required": True,
            "description": "Database username"
        },
        {
            "name": "db_password",
            "type": "string",
            "required": True,
            "description": "Database password"
        }
    ]
}

# Sample runtime variables for testing
SAMPLE_RUNTIME_VARIABLES = {
    "api_key": "sk-test123456789",
    "model_name": "gpt-4",
    "temperature": 0.3,
    "host": "custom-api.example.com",
    "port": 8080,
    "timeout_seconds": 60,
    "is_enabled": False,
    "db_host": "localhost",
    "db_port": 3306,
    "db_user": "admin",
    "db_password": "secure_password_123"
}

# Expected resolved configuration after variable substitution
EXPECTED_RESOLVED_CONFIG = {
    "api_key": "sk-test123456789",
    "model": "gpt-4",
    "temperature": 0.3,
    "endpoint": "https://custom-api.example.com:8080/v1/chat",
    "timeout": 60,
    "enabled": False,
    "connection": {
        "host": "localhost",
        "port": 3306,
        "credentials": {
            "username": "admin",
            "password": "secure_password_123"
        }
    }
}