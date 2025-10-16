"""
Comprehensive JSON Schema definitions for Genesis specification validation.

This module provides comprehensive schema validation for Genesis agent specifications,
ensuring structural integrity, field validation, and semantic consistency.
"""

from typing import Dict, Any, List, Optional
import re

# Base component schema for all Genesis components
COMPONENT_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {
            "type": "string",
            "pattern": r"^[a-zA-Z][a-zA-Z0-9_-]*$",
            "minLength": 2,
            "maxLength": 50,
            "description": "Unique component identifier"
        },
        "name": {
            "type": "string",
            "minLength": 1,
            "maxLength": 100,
            "description": "Human-readable component name"
        },
        "kind": {
            "type": "string",
            "enum": ["Data", "Tool", "Prompt", "Agent", "Model", "Memory"],
            "description": "Component classification for positioning"
        },
        "type": {
            "type": "string",
            "pattern": r"^genesis:[a-z][a-z0-9_]*$",
            "description": "Genesis component type (e.g., genesis:agent)"
        },
        "description": {
            "type": ["string", "null"],
            "maxLength": 500,
            "description": "Optional component description"
        },
        "config": {
            "type": ["object", "null"],
            "description": "Component-specific configuration"
        },
        "provides": {
            "type": ["array", "null"],
            "items": {
                "type": "object",
                "properties": {
                    "useAs": {
                        "type": "string",
                        "enum": [
                            "input", "output", "tools", "tool", "system_prompt",
                            "prompt", "memory", "llm", "query", "text", "data",
                            "message", "response", "json", "csv", "file"
                        ],
                        "description": "How the output should be used by target component"
                    },
                    "in": {
                        "type": "string",
                        "pattern": r"^[a-zA-Z][a-zA-Z0-9_-]*$",
                        "description": "ID of the target component"
                    },
                    "description": {
                        "type": ["string", "null"],
                        "maxLength": 200,
                        "description": "Optional connection description"
                    },
                    "fromOutput": {
                        "type": ["string", "null"],
                        "description": "Specific output field to use"
                    }
                },
                "required": ["useAs", "in"],
                "additionalProperties": False
            },
            "maxItems": 10,
            "description": "Output connections to other components"
        },
        "asTools": {
            "type": ["boolean", "null"],
            "description": "Whether component can be used as a tool"
        },
        "modelEndpoint": {
            "type": ["string", "null"],
            "description": "Model endpoint for AI components"
        }
    },
    "required": ["id", "name", "type"],
    "additionalProperties": False
}

# Variable schema
VARIABLE_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "pattern": r"^[a-zA-Z][a-zA-Z0-9_]*$",
            "minLength": 1,
            "maxLength": 50
        },
        "type": {
            "type": "string",
            "enum": ["string", "number", "boolean", "array", "object"],
            "default": "string"
        },
        "required": {
            "type": "boolean",
            "default": False
        },
        "default": {
            "description": "Default value for the variable"
        },
        "description": {
            "type": ["string", "null"],
            "maxLength": 200
        }
    },
    "required": ["name"],
    "additionalProperties": False
}

# KPI schema
KPI_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "minLength": 1,
            "maxLength": 100
        },
        "category": {
            "type": "string",
            "enum": [
                "performance", "quality", "business", "technical",
                "user_experience", "cost", "efficiency", "compliance"
            ]
        },
        "valueType": {
            "type": "string",
            "enum": ["number", "percentage", "count", "duration", "boolean"]
        },
        "target": {
            "description": "Target value for the KPI"
        },
        "unit": {
            "type": ["string", "null"],
            "maxLength": 20
        },
        "description": {
            "type": ["string", "null"],
            "maxLength": 300
        }
    },
    "required": ["name", "category", "valueType", "target"],
    "additionalProperties": False
}

# Security info schema
SECURITY_INFO_SCHEMA = {
    "type": "object",
    "properties": {
        "visibility": {
            "type": "string",
            "enum": ["Private", "Internal", "Public"],
            "default": "Private"
        },
        "confidentiality": {
            "type": "string",
            "enum": ["Low", "Medium", "High", "Critical"],
            "default": "High"
        },
        "gdprSensitive": {
            "type": "boolean",
            "default": False
        },
        "hipaaCompliant": {
            "type": ["boolean", "null"],
            "description": "Whether the specification handles HIPAA-regulated data"
        },
        "dataClassification": {
            "type": ["string", "null"],
            "enum": ["public", "internal", "confidential", "restricted", "phi", "pii"],
            "description": "Data classification level"
        }
    },
    "additionalProperties": False
}

# Reusability info schema
REUSABILITY_INFO_SCHEMA = {
    "type": "object",
    "properties": {
        "asTools": {
            "type": "boolean",
            "default": False
        },
        "standalone": {
            "type": "boolean",
            "default": True
        },
        "provides": {
            "type": ["object", "null"]
        },
        "dependencies": {
            "type": ["array", "null"],
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "name": {"type": "string"}
                },
                "required": ["type", "name"]
            }
        }
    },
    "additionalProperties": False
}

# Main specification schema
GENESIS_SPEC_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Genesis Agent Specification",
    "description": "Complete schema for Genesis agent specifications",
    "type": "object",
    "properties": {
        # Core identification
        "id": {
            "type": "string",
            "pattern": r"^urn:agent:genesis:[a-z0-9.-]+:[a-z0-9_-]+:[0-9]+\.[0-9]+\.[0-9]+$",
            "description": "URN format: urn:agent:genesis:domain:name:version"
        },
        "name": {
            "type": "string",
            "minLength": 3,
            "maxLength": 100,
            "pattern": r"^[A-Za-z][A-Za-z0-9\s_-]*$",
            "description": "Clear descriptive name"
        },
        "fullyQualifiedName": {
            "type": ["string", "null"],
            "pattern": r"^genesis\.autonomize\.ai\.[a-z0-9._-]+$",
            "description": "Fully qualified name in genesis namespace"
        },
        "description": {
            "type": "string",
            "minLength": 10,
            "maxLength": 1000,
            "description": "Detailed description of agent purpose and functionality"
        },
        "domain": {
            "type": ["string", "null"],
            "enum": ["autonomize.ai", "healthcare", "finance", "education", "retail"],
            "description": "Domain classification"
        },
        "subDomain": {
            "type": ["string", "null"],
            "maxLength": 50,
            "description": "Sub-domain classification"
        },
        "version": {
            "type": ["string", "null"],
            "pattern": r"^[0-9]+\.[0-9]+\.[0-9]+$",
            "default": "1.0.0",
            "description": "Semantic version"
        },
        "environment": {
            "type": ["string", "null"],
            "enum": ["development", "staging", "production"],
            "default": "production"
        },
        "agentOwner": {
            "type": ["string", "null"],
            "format": "email",
            "description": "Owner email address"
        },
        "agentOwnerDisplayName": {
            "type": ["string", "null"],
            "maxLength": 100,
            "description": "Owner display name"
        },
        "email": {
            "type": ["string", "null"],
            "format": "email",
            "description": "Contact email"
        },
        "status": {
            "type": ["string", "null"],
            "enum": ["ACTIVE", "INACTIVE", "DEPRECATED", "DEVELOPMENT"],
            "default": "ACTIVE"
        },

        # Core configuration
        "kind": {
            "type": "string",
            "enum": ["Single Agent", "Multi Agent", "Orchestrator"],
            "description": "Agent architecture type"
        },
        "agentGoal": {
            "type": "string",
            "minLength": 10,
            "maxLength": 500,
            "description": "Clear statement of agent's primary objective"
        },
        "targetUser": {
            "type": ["string", "null"],
            "enum": ["internal", "external", "customer", "admin", "developer"],
            "default": "internal"
        },
        "valueGeneration": {
            "type": ["string", "null"],
            "enum": [
                "ProcessAutomation", "InsightGeneration", "DecisionSupport",
                "CustomerService", "DataAnalysis", "ContentGeneration"
            ],
            "default": "ProcessAutomation"
        },
        "interactionMode": {
            "type": ["string", "null"],
            "enum": ["RequestResponse", "Streaming", "Batch", "Interactive"],
            "default": "RequestResponse"
        },
        "runMode": {
            "type": ["string", "null"],
            "enum": ["RealTime", "Scheduled", "Triggered", "OnDemand"],
            "default": "RealTime"
        },
        "agencyLevel": {
            "type": ["string", "null"],
            "enum": [
                "ReflexiveAgent", "ModelBasedReflexAgent", "GoalBasedAgent",
                "UtilityBasedAgent", "LearningAgent", "ModelDrivenWorkflow",
                "KnowledgeDrivenWorkflow"
            ],
            "default": "ModelDrivenWorkflow"
        },
        "toolsUse": {
            "type": ["boolean", "null"],
            "default": False
        },
        "learningCapability": {
            "type": ["string", "null"],
            "enum": ["None", "Supervised", "Unsupervised", "Reinforcement", "Transfer"],
            "default": "None"
        },

        # Components - support both list and dict formats
        "components": {
            "oneOf": [
                {
                    "type": "array",
                    "items": COMPONENT_SCHEMA,
                    "minItems": 2,
                    "maxItems": 50
                },
                {
                    "type": "object",
                    "patternProperties": {
                        r"^[a-zA-Z][a-zA-Z0-9_-]*$": {
                            "allOf": [
                                COMPONENT_SCHEMA,
                                {
                                    "properties": {
                                        "id": False  # ID not needed in dict format as it's the key
                                    }
                                }
                            ]
                        }
                    },
                    "additionalProperties": False,
                    "minProperties": 2,
                    "maxProperties": 50
                }
            ],
            "description": "Component definitions (list or dictionary format)"
        },

        # Optional sections
        "variables": {
            "type": ["array", "null"],
            "items": VARIABLE_SCHEMA,
            "maxItems": 20
        },
        "tags": {
            "type": ["array", "null"],
            "items": {
                "type": "string",
                "minLength": 2,
                "maxLength": 30,
                "pattern": r"^[a-zA-Z0-9_-]+$"
            },
            "maxItems": 10,
            "uniqueItems": True
        },
        "kpis": {
            "type": ["array", "null"],
            "items": KPI_SCHEMA,
            "maxItems": 10
        },
        "securityInfo": {
            "type": ["object", "null"],
            "allOf": [SECURITY_INFO_SCHEMA]
        },
        "outputs": {
            "type": ["array", "null"],
            "items": {
                "type": "string",
                "minLength": 2,
                "maxLength": 50
            },
            "maxItems": 10
        },
        "reusability": {
            "type": ["object", "null"],
            "allOf": [REUSABILITY_INFO_SCHEMA]
        },
        "sampleInput": {
            "type": ["object", "null"],
            "description": "Sample input data structure"
        },
        "promptConfiguration": {
            "type": ["object", "null"],
            "description": "Prompt-specific configuration"
        }
    },
    "required": [
        "id", "name", "description", "kind", "agentGoal", "components"
    ],
    "additionalProperties": False
}

# Component-specific configuration schemas
COMPONENT_CONFIG_SCHEMAS = {
    "genesis:agent": {
        "type": "object",
        "properties": {
            "provider": {
                "type": "string",
                "enum": ["openai", "azure_openai", "anthropic", "cohere"]
            },
            "model": {"type": "string"},
            "temperature": {"type": "number", "minimum": 0, "maximum": 2},
            "max_tokens": {"type": "integer", "minimum": 1, "maximum": 32768},
            "system_prompt": {"type": "string", "maxLength": 5000},
            "streaming": {"type": "boolean"},
            "top_p": {"type": "number", "minimum": 0, "maximum": 1},
            "frequency_penalty": {"type": "number", "minimum": -2, "maximum": 2},
            "presence_penalty": {"type": "number", "minimum": -2, "maximum": 2}
        },
        "additionalProperties": True  # Allow additional provider-specific configs
    },
    "genesis:mcp_tool": {
        "type": "object",
        "properties": {
            "tool_name": {
                "type": "string",
                "minLength": 1,
                "maxLength": 100,
                "pattern": r"^[a-z][a-z0-9_]*$"
            },
            "description": {"type": "string", "maxLength": 500},
            "command": {"type": "string"},
            "args": {"type": "array", "items": {"type": "string"}},
            "env": {"type": "object"},
            "url": {"type": "string", "format": "uri"},
            "headers": {"type": "object"},
            "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 300}
        },
        "required": ["tool_name"],
        "additionalProperties": False
    },
    "genesis:api_request": {
        "type": "object",
        "properties": {
            "method": {
                "type": "string",
                "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"]
            },
            "url": {"type": "string", "format": "uri"},
            "headers": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string"},
                        "value": {"type": "string"}
                    },
                    "required": ["key", "value"]
                }
            },
            "body": {"type": "object"},
            "timeout": {"type": "integer", "minimum": 1, "maximum": 300}
        },
        "required": ["method", "url"],
        "additionalProperties": False
    },
    "genesis:knowledge_hub_search": {
        "type": "object",
        "properties": {
            "collections": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "array", "items": {"type": "string"}}
                ]
            },
            "max_results": {"type": "integer", "minimum": 1, "maximum": 100},
            "similarity_threshold": {"type": "number", "minimum": 0, "maximum": 1}
        },
        "additionalProperties": False
    },
    "genesis:crewai_agent": {
        "type": "object",
        "properties": {
            "role": {"type": "string", "minLength": 5, "maxLength": 100},
            "goal": {"type": "string", "minLength": 10, "maxLength": 500},
            "backstory": {"type": "string", "minLength": 10, "maxLength": 1000},
            "verbose": {"type": "boolean", "default": False},
            "allow_delegation": {"type": "boolean", "default": False},
            "max_iter": {"type": "integer", "minimum": 1, "maximum": 100},
            "memory": {"type": "boolean", "default": False}
        },
        "required": ["role", "goal", "backstory"],
        "additionalProperties": False
    },
    "genesis:crewai_sequential_task": {
        "type": "object",
        "properties": {
            "description": {"type": "string", "minLength": 10, "maxLength": 1000},
            "expected_output": {"type": "string", "minLength": 10, "maxLength": 500},
            "agent_id": {"type": "string", "pattern": r"^[a-zA-Z][a-zA-Z0-9_-]*$"},
            "context": {"type": "array", "items": {"type": "string"}},
            "output_file": {"type": "string"},
            "callback": {"type": "string"}
        },
        "required": ["description", "expected_output", "agent_id"],
        "additionalProperties": False
    },
    "genesis:crewai_sequential_crew": {
        "type": "object",
        "properties": {
            "agents": {
                "type": "array",
                "items": {"type": "string", "pattern": r"^[a-zA-Z][a-zA-Z0-9_-]*$"},
                "minItems": 2,
                "maxItems": 10
            },
            "tasks": {
                "type": "array",
                "items": {"type": "string", "pattern": r"^[a-zA-Z][a-zA-Z0-9_-]*$"},
                "minItems": 1,
                "maxItems": 20
            },
            "verbose": {"type": "boolean", "default": False},
            "memory": {"type": "boolean", "default": False},
            "planning": {"type": "boolean", "default": False}
        },
        "required": ["agents", "tasks"],
        "additionalProperties": False
    }
}

# CrewAI workflow validation patterns
CREWAI_WORKFLOW_PATTERNS = {
    "sequential": {
        "required_components": ["genesis:crewai_agent", "genesis:crewai_sequential_task", "genesis:crewai_sequential_crew"],
        "min_agents": 2,
        "max_agents": 10,
        "task_to_agent_ratio": {"min": 1, "max": 5},  # 1-5 tasks per agent
        "crew_requirements": {
            "must_reference_all_agents": True,
            "must_reference_all_tasks": True
        }
    },
    "hierarchical": {
        "required_components": ["genesis:crewai_agent", "genesis:crewai_hierarchical_crew"],
        "min_agents": 3,  # Manager + 2 workers minimum
        "max_agents": 20,
        "manager_required": True,
        "crew_requirements": {
            "must_have_manager": True,
            "must_reference_all_agents": True
        }
    }
}

def get_component_config_schema(component_type: str) -> Optional[Dict[str, Any]]:
    """
    Get the configuration schema for a specific component type.

    Args:
        component_type: Genesis component type (e.g., 'genesis:agent')

    Returns:
        JSON schema for component configuration or None if not found
    """
    return COMPONENT_CONFIG_SCHEMAS.get(component_type)

def get_validation_patterns_for_workflow(kind: str) -> Optional[Dict[str, Any]]:
    """
    Get validation patterns for specific workflow types.

    Args:
        kind: Workflow kind ('Single Agent', 'Multi Agent', etc.)

    Returns:
        Validation patterns or None
    """
    if kind == "Multi Agent":
        # Try to detect CrewAI pattern from components
        return CREWAI_WORKFLOW_PATTERNS
    return None

def validate_urn_format(urn: str) -> bool:
    """
    Validate URN format: urn:agent:genesis:domain:name:version

    Args:
        urn: URN string to validate

    Returns:
        True if valid, False otherwise
    """
    pattern = r"^urn:agent:genesis:[a-z0-9.-]+:[a-z0-9_-]+:[0-9]+\.[0-9]+\.[0-9]+$"
    return bool(re.match(pattern, urn))

def validate_email_format(email: str) -> bool:
    """
    Validate email format.

    Args:
        email: Email address to validate

    Returns:
        True if valid, False otherwise
    """
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))