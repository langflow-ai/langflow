"""Component Mapper for Genesis to Langflow components."""

from typing import Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class ComponentMapper:
    """Maps Genesis specification types to AI Studio (Langflow) components."""

    def __init__(self):
        """Initialize component mapper with mappings."""
        self._init_mappings()

    def _init_mappings(self):
        """Initialize all component mappings."""
        # AutonomizeModel variants - all clinical models unified
        self.AUTONOMIZE_MODELS = {
            "genesis:autonomize_model": {
                "component": "AutonomizeModel",
                "config": {"selected_model": "Clinical LLM"}  # Default model
            },
            "genesis:rxnorm": {
                "component": "AutonomizeModel",
                "config": {"selected_model": "RxNorm Code"}
            },
            "genesis:icd10": {
                "component": "AutonomizeModel",
                "config": {"selected_model": "ICD-10 Code"}
            },
            "genesis:cpt_code": {
                "component": "AutonomizeModel",
                "config": {"selected_model": "CPT Code"}
            },
            "genesis:cpt": {  # Alias
                "component": "AutonomizeModel",
                "config": {"selected_model": "CPT Code"}
            },
            "genesis:clinical_llm": {
                "component": "AutonomizeModel",
                "config": {"selected_model": "Clinical LLM"}
            },
            "genesis:clinical_note_classifier": {
                "component": "AutonomizeModel",
                "config": {"selected_model": "Clinical Note Classifier"}
            },
            "genesis:combined_entity_linking": {
                "component": "AutonomizeModel",
                "config": {"selected_model": "Combined Entity Linking"}
            }
        }

        # MCP components
        self.MCP_MAPPINGS = {
            "genesis:mcp_tool": {
                "component": "MCPTools",
                "config": {
                    # For backward compatibility with existing tool_name-only configurations
                    # Provide a default command that enables STDIO mode detection
                    "command": "echo '{\"tools\": [], \"capabilities\": {}}'",  # Default JSON response for compatibility
                    "args": [],
                    "env": {},
                    "url": "",
                    "headers": {},
                    "timeout_seconds": 30,
                    "sse_read_timeout_seconds": 30
                },
                "dataType": "MCPTools"
            },
            "genesis:mcp_sse_tool": {
                "component": "MCPTools",
                "config": {
                    "connection_mode": "SSE",
                    "url": "",
                    "headers": {},
                    "timeout_seconds": 30,
                    "sse_read_timeout_seconds": 30
                },
                "dataType": "MCPTools"
            },
            "genesis:mcp_stdio_tool": {
                "component": "MCPTools",
                "config": {
                    "connection_mode": "Stdio",
                    "command": "",
                    "args": [],
                    "env": {}
                },
                "dataType": "MCPTools"
            },
            "genesis:mcp_client": {
                "component": "MCPClient",
                "config": {}
            },
            "genesis:mcp_server": {
                "component": "MCPServer",
                "config": {}
            }
        }

        # Standard component mappings
        self.STANDARD_MAPPINGS = {
            # Agents
            "genesis:agent": {"component": "Agent", "config": {}},
            "genesis:autonomize_agent": {"component": "AutonomizeAgent", "config": {}},

            # Input/Output
            "genesis:chat_input": {"component": "ChatInput", "config": {}},
            "genesis:chat_output": {"component": "ChatOutput", "config": {}},
            "genesis:json_input": {"component": "JSONInput", "config": {}},
            "genesis:json_output": {"component": "ParseData", "config": {}},
            "genesis:file_input": {"component": "FileInput", "config": {}},

            # Prompts
            "genesis:prompt": {"component": "Prompt", "config": {}},
            "genesis:prompt_template": {"component": "GenesisPromptComponent", "config": {}, "dataType": "Prompt"},
            "genesis:genesis_prompt": {"component": "GenesisPromptComponent", "config": {}, "dataType": "Prompt"},

            # Memory
            "genesis:memory": {"component": "Memory", "config": {}},
            "genesis:conversation_memory": {"component": "ConversationChain", "config": {}},
            "genesis:conversation_chain": {"component": "ConversationChain", "config": {}},

            # Tools - Infrastructure components (keep) + MCP fallbacks for domain-specific ones
            "genesis:knowledge_hub_search": {"component": "KnowledgeHubSearch", "config": {}, "dataType": "KnowledgeHubSearch"},
            "genesis:calculator": {"component": "Calculator", "config": {}},

            # Domain-specific tools -> MCP Tools Component (simplified approach)
            "genesis:encoder_pro": {"component": "MCPTools", "config": {"tool_name": "encoder_pro", "description": "Medical coding and validation tool"}, "dataType": "MCPTools"},
            "genesis:pa_lookup": {"component": "MCPTools", "config": {"tool_name": "pa_lookup", "description": "Prior authorization lookup tool"}, "dataType": "MCPTools"},
            "genesis:eligibility_component": {"component": "MCPTools", "config": {"tool_name": "eligibility_check", "description": "Member eligibility validation tool"}, "dataType": "MCPTools"},
            "genesis:qnext_auth_history": {"component": "MCPTools", "config": {"tool_name": "qnext_auth_history", "description": "QNext authorization history tool"}, "dataType": "MCPTools"},
            "genesis:api_component": {"component": "MCPTools", "config": {"tool_name": "api_component", "description": "Generic API integration tool"}, "dataType": "MCPTools"},
            # Azure Document Intelligence (Form Recognizer) component
            "genesis:form_recognizer": {"component": "AzureDocumentIntelligenceComponent", "config": {}, "dataType": "AzureDocumentIntelligenceComponent"},
            "genesis:document_intelligence": {"component": "AzureDocumentIntelligenceComponent", "config": {}, "dataType": "AzureDocumentIntelligenceComponent"},

            # Data processing tools
            "genesis:data_transformer": {"component": "MCPTools", "config": {"tool_name": "data_transformer", "description": "Data transformation and standardization tool"}, "dataType": "MCPTools"},

            # Vector stores
            "genesis:vector_store": {"component": "QdrantVectorStore", "config": {}},
            "genesis:qdrant": {"component": "QdrantVectorStore", "config": {}},
            "genesis:faiss": {"component": "FAISS", "config": {}},

            # LLMs
            "genesis:openai": {"component": "OpenAIModel", "config": {}},
            "genesis:azure_openai": {"component": "AzureOpenAIModel", "config": {}},
            "genesis:anthropic": {"component": "AnthropicModel", "config": {}},

            # CrewAI
            "genesis:sequential_crew": {"component": "CrewAIAgent", "config": {}},
            "genesis:hierarchical_crew": {"component": "HierarchicalCrew", "config": {}}
        }

    def map_component(self, spec_type: str) -> Dict[str, Any]:
        """
        Map a Genesis specification type to Langflow component.

        Args:
            spec_type: Component type from specification (e.g., "genesis:rxnorm")

        Returns:
            Dictionary with component name and configuration
        """
        # Check AutonomizeModel mappings first
        if spec_type in self.AUTONOMIZE_MODELS:
            return self.AUTONOMIZE_MODELS[spec_type].copy()

        # Check MCP mappings
        if spec_type in self.MCP_MAPPINGS:
            return self.MCP_MAPPINGS[spec_type].copy()

        # Check standard mappings
        if spec_type in self.STANDARD_MAPPINGS:
            return self.STANDARD_MAPPINGS[spec_type].copy()

        # Try to handle unknown types intelligently
        return self._handle_unknown_type(spec_type)

    def _handle_unknown_type(self, spec_type: str) -> Dict[str, Any]:
        """Handle unknown component types with intelligent fallbacks."""
        # Remove genesis: prefix if present
        base_type = spec_type.replace("genesis:", "") if spec_type.startswith("genesis:") else spec_type

        # Pattern-based fallbacks
        if "model" in base_type.lower() or "llm" in base_type.lower():
            # Check if it's a clinical model
            if any(term in base_type.lower() for term in ["clinical", "rxnorm", "icd", "cpt", "medical"]):
                logger.warning(f"Unknown clinical model type '{spec_type}', using AutonomizeModel")
                return {"component": "AutonomizeModel", "config": {}}
            else:
                logger.warning(f"Unknown LLM type '{spec_type}', using OpenAIModel")
                return {"component": "OpenAIModel", "config": {}}

        elif "agent" in base_type.lower():
            logger.warning(f"Unknown agent type '{spec_type}', using Agent")
            return {"component": "Agent", "config": {}}

        elif "tool" in base_type.lower() or "component" in base_type.lower():
            logger.warning(f"Unknown tool/component type '{spec_type}', using MCPTools as fallback")
            return {"component": "MCPTools", "config": {}}

        elif "memory" in base_type.lower():
            logger.warning(f"Unknown memory type '{spec_type}', using Memory")
            return {"component": "Memory", "config": {}}

        elif "prompt" in base_type.lower():
            logger.warning(f"Unknown prompt type '{spec_type}', using Prompt")
            return {"component": "Prompt", "config": {}}

        elif "input" in base_type.lower():
            logger.warning(f"Unknown input type '{spec_type}', using ChatInput")
            return {"component": "ChatInput", "config": {}}

        elif "output" in base_type.lower():
            logger.warning(f"Unknown output type '{spec_type}', using ChatOutput")
            return {"component": "ChatOutput", "config": {}}

        else:
            # Default to MCPTools for complete unknowns - better than CustomComponent
            logger.warning(f"Completely unknown type '{spec_type}', using MCPTools as fallback")
            return {"component": "MCPTools", "config": {}}

    def get_component_io_mapping(self, component_type: str) -> Dict[str, Any]:
        """
        Get input/output field mappings for a component type.

        Returns dictionary with:
        - input_field: The field name for inputs
        - output_field: The field name for outputs
        - output_types: Expected output types
        """
        io_mappings = {
            "AutonomizeModel": {
                "input_field": "search_query",  # AutonomizeModel uses search_query
                "output_field": "prediction",   # Outputs prediction
                "output_types": ["Data"]
            },
            "ChatInput": {
                "input_field": None,
                "output_field": "message",
                "output_types": ["Message"]
            },
            "ChatOutput": {
                "input_field": "input_value",
                "output_field": "message",
                "output_types": ["Message"]
            },
            "Agent": {
                "input_field": "input_value",
                "output_field": "response",  # Most agents use response
                "output_types": ["Message"]
            },
            "AutonomizeAgent": {
                "input_field": "input_value",
                "output_field": "response",
                "output_types": ["Message"]
            },
            "Prompt": {
                "input_field": "template",
                "output_field": "prompt",
                "output_types": ["Message"]
            },
            "GenesisPromptComponent": {
                "input_field": "template",
                "output_field": "prompt",
                "output_types": ["Message"]
            },
            "MCPTools": {
                "input_field": None,
                "output_field": "response",
                "output_types": ["DataFrame"]
            },
            "CustomComponent": {
                "input_field": "input_value",
                "output_field": "output",
                "output_types": ["Any"]
            },
            "Memory": {
                "input_field": "input_value",
                "output_field": "memory",
                "output_types": ["Message"]
            },
            "OpenAIModel": {
                "input_field": "input_value",
                "output_field": "text_output",
                "output_types": ["Message"]
            },
            "AzureOpenAIModel": {
                "input_field": "input_value",
                "output_field": "text_output",
                "output_types": ["Message"]
            },
            "KnowledgeHubSearch": {
                "input_field": "search_query",
                "output_field": "query_results",
                "output_types": ["Data"]
            },
            "EncoderProTool": {
                "input_field": "default_service_code",
                "output_field": "component_as_tool",
                "output_types": ["Tool"]
            },
            "GenesisPromptComponent": {
                "input_field": "template",
                "output_field": "prompt",
                "output_types": ["Message"]
            }
        }

        return io_mappings.get(component_type, {
            "input_field": "input_value",
            "output_field": "output",
            "output_types": ["Any"]
        })

    def is_tool_component(self, spec_type: str) -> bool:
        """Check if a component type should be used as a tool."""
        # MCP components are always tools
        if spec_type in self.MCP_MAPPINGS:
            return True

        # Check if it's a known tool type
        tool_types = [
            "genesis:knowledge_hub_search",
            "genesis:pa_lookup",
            "genesis:eligibility_component",
            "genesis:encoder_pro",
            "genesis:calculator",
            "genesis:api_component",
            "genesis:mcp_tool",
            "genesis:mcp_sse_tool",
            "genesis:mcp_stdio_tool"
        ]

        return spec_type in tool_types