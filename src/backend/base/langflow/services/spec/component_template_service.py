"""Component Template Service for real Langflow component integration."""

import logging
from typing import Dict, Any, Optional
from langflow.interface.components import import_langflow_components
from langflow.custom.utils import create_component_template
from langflow.template.frontend_node.base import FrontendNode

logger = logging.getLogger(__name__)


class ComponentTemplateService:
    """Service for retrieving real Langflow component templates."""

    def __init__(self):
        """Initialize the service."""
        self._component_cache: Dict[str, Any] = {}
        self._components_loaded = False

    async def load_components(self):
        """Load all Langflow components into cache."""
        if self._components_loaded:
            return

        try:
            # Load all built-in Langflow components
            components_dict = await import_langflow_components()

            # Flatten the nested structure into a simple name -> template mapping
            for category, category_components in components_dict.get("components", {}).items():
                for comp_name, comp_template in category_components.items():
                    self._component_cache[comp_name] = comp_template

            self._components_loaded = True
            logger.info(f"Loaded {len(self._component_cache)} component templates")

        except Exception as e:
            logger.error(f"Failed to load component templates: {e}")
            # Set basic fallback templates for essential components
            self._set_fallback_templates()

    def _set_fallback_templates(self):
        """Set basic fallback templates for essential components."""
        self._component_cache = {
            "ChatInput": {
                "template": {
                    "input_value": {
                        "input_types": [],
                        "type": "str",
                        "display_name": "Text",
                        "info": "Message to be passed as input."
                    }
                },
                "outputs": [
                    {
                        "types": ["Message"],
                        "selected": "Message",
                        "name": "message",
                        "display_name": "Message",
                        "method": "text_response"
                    }
                ],
                "base_classes": ["ChatInput"],
                "description": "Get chat inputs from the Playground.",
                "display_name": "Chat Input"
            },
            "ChatOutput": {
                "template": {
                    "input_value": {
                        "input_types": ["Message", "Text"],
                        "type": "str",
                        "display_name": "Text",
                        "info": "Message to be passed as output."
                    },
                    "sender": {
                        "type": "str",
                        "display_name": "Sender Type",
                        "options": ["Machine", "User"],
                        "value": "Machine"
                    },
                    "sender_name": {
                        "type": "str",
                        "display_name": "Sender Name",
                        "value": "AI"
                    }
                },
                "outputs": [
                    {
                        "types": ["Message"],
                        "selected": "Message",
                        "name": "message",
                        "display_name": "Message",
                        "method": "message_response"
                    }
                ],
                "base_classes": ["ChatOutput"],
                "description": "Display a chat message in the Playground.",
                "display_name": "Chat Output"
            },
            "Agent": {
                "template": {
                    "input_value": {
                        "input_types": ["Message"],
                        "type": "str",
                        "display_name": "Input",
                        "info": "Input for the agent."
                    },
                    "system_prompt": {
                        "input_types": ["Message"],
                        "type": "str",
                        "display_name": "System Prompt",
                        "info": "System prompt for the agent."
                    },
                    "tools": {
                        "input_types": ["Tool"],
                        "type": "list",
                        "display_name": "Tools",
                        "info": "Tools available to the agent."
                    }
                },
                "outputs": [
                    {
                        "types": ["Message"],
                        "selected": "Message",
                        "name": "response",
                        "display_name": "Response",
                        "method": "build_agent"
                    }
                ],
                "base_classes": ["Agent"],
                "description": "Agent component for conversational AI.",
                "display_name": "Agent"
            },
            "AutonomizeModel": {
                "template": {
                    "search_query": {
                        "input_types": ["Message", "Text"],
                        "type": "str",
                        "display_name": "Search Query",
                        "info": "Query for the AutonomizeModel."
                    },
                    "selected_model": {
                        "type": "str",
                        "display_name": "Selected Model",
                        "options": [
                            "RxNorm Code",
                            "ICD-10 Code",
                            "CPT Code",
                            "Clinical LLM",
                            "Clinical Note Classifier",
                            "Combined Entity Linking"
                        ],
                        "value": "Clinical LLM"
                    }
                },
                "outputs": [
                    {
                        "types": ["Data"],
                        "selected": "Data",
                        "name": "prediction",
                        "display_name": "Prediction",
                        "method": "predict"
                    }
                ],
                "base_classes": ["AutonomizeModel"],
                "description": "Unified clinical AI model component.",
                "display_name": "Autonomize Model"
            },
            "Calculator": {
                "template": {
                    "input_value": {
                        "input_types": ["Text"],
                        "type": "str",
                        "display_name": "Expression",
                        "info": "Mathematical expression to calculate."
                    }
                },
                "outputs": [
                    {
                        "types": ["Text"],
                        "selected": "Text",
                        "name": "output",
                        "display_name": "Result",
                        "method": "calculate"
                    }
                ],
                "base_classes": ["Calculator"],
                "description": "Calculator tool for mathematical operations.",
                "display_name": "Calculator"
            },
            "MCPTool": {
                "template": {},
                "outputs": [
                    {
                        "types": ["Tool"],
                        "selected": "Tool",
                        "name": "component_as_tool",
                        "display_name": "Tool",
                        "method": "build_tool"
                    }
                ],
                "base_classes": ["MCPTool"],
                "description": "Model Context Protocol tool component.",
                "display_name": "MCP Tool"
            },
            "GenesisPromptComponent": {
                "template": {
                    "template": {
                        "input_types": ["Message", "Text"],
                        "type": "str",
                        "display_name": "Template",
                        "info": "Prompt template with variables."
                    },
                    "saved_prompt": {
                        "type": "str",
                        "display_name": "Saved Prompt",
                        "info": "Name of saved prompt to load."
                    }
                },
                "outputs": [
                    {
                        "types": ["Message"],
                        "selected": "Message",
                        "name": "prompt",
                        "display_name": "Prompt",
                        "method": "build_prompt"
                    }
                ],
                "base_classes": ["GenesisPromptComponent"],
                "description": "Genesis prompt template component.",
                "display_name": "Genesis Prompt"
            },
            "KnowledgeHubSearchComponent": {
                "template": {
                    "search_query": {
                        "input_types": ["Message", "Text"],
                        "type": "str",
                        "display_name": "Search Query",
                        "info": "Query to search in knowledge hub."
                    },
                    "collections": {
                        "type": "list",
                        "display_name": "Collections",
                        "info": "Knowledge hub collections to search."
                    },
                    "search_type": {
                        "type": "str",
                        "display_name": "Search Type",
                        "options": ["similarity", "keyword", "hybrid"],
                        "value": "similarity"
                    },
                    "top_k": {
                        "type": "int",
                        "display_name": "Top K Results",
                        "value": 10
                    }
                },
                "outputs": [
                    {
                        "types": ["Data"],
                        "selected": "Data",
                        "name": "query_results",
                        "display_name": "Search Results",
                        "method": "search"
                    },
                    {
                        "types": ["Tool"],
                        "selected": "Tool",
                        "name": "component_as_tool",
                        "display_name": "Search Tool",
                        "method": "to_toolkit",
                        "tool_mode": True
                    }
                ],
                "base_classes": ["KnowledgeHubSearchComponent"],
                "description": "Search component for knowledge hub documents.",
                "display_name": "Knowledge Hub Search"
            },
            "EncoderProTool": {
                "template": {
                    "default_service_code": {
                        "input_types": ["Text"],
                        "type": "str",
                        "display_name": "Service Code",
                        "info": "Default service code for encoding."
                    },
                    "include_descriptions": {
                        "type": "bool",
                        "display_name": "Include Descriptions",
                        "value": True
                    },
                    "validate_codes": {
                        "type": "bool",
                        "display_name": "Validate Codes",
                        "value": True
                    }
                },
                "outputs": [
                    {
                        "types": ["Data"],
                        "selected": "Data",
                        "name": "encoded_result",
                        "display_name": "Encoded Result",
                        "method": "encode"
                    },
                    {
                        "types": ["Tool"],
                        "selected": "Tool",
                        "name": "component_as_tool",
                        "display_name": "Encoder Tool",
                        "method": "to_toolkit",
                        "tool_mode": True
                    }
                ],
                "base_classes": ["EncoderProTool"],
                "description": "Service code encoding and validation tool.",
                "display_name": "Encoder Pro"
            },
            "CustomComponent": {
                "template": {
                    "input_value": {
                        "input_types": ["Any"],
                        "type": "str",
                        "display_name": "Input",
                        "info": "Input for the custom component."
                    }
                },
                "outputs": [
                    {
                        "types": ["Any"],
                        "selected": "Any",
                        "name": "output",
                        "display_name": "Output",
                        "method": "build"
                    }
                ],
                "base_classes": ["CustomComponent"],
                "description": "Custom component for specialized functionality.",
                "display_name": "Custom Component"
            }
        }

    async def get_component_template(self, component_name: str) -> Optional[Dict[str, Any]]:
        """Get template for a specific component.

        Args:
            component_name: Name of the component (e.g., "ChatInput", "Agent")

        Returns:
            Component template dictionary or None if not found
        """
        # Ensure components are loaded
        await self.load_components()

        # Try exact match first
        if component_name in self._component_cache:
            return self._component_cache[component_name]

        # Try case-insensitive match
        for cached_name, template in self._component_cache.items():
            if cached_name.lower() == component_name.lower():
                return template

        # Log missing component for debugging
        logger.warning(f"Component template not found: {component_name}")
        logger.debug(f"Available components: {list(self._component_cache.keys())[:10]}...")

        return None

    def get_available_components(self) -> Dict[str, Any]:
        """Get all available component names and their basic info."""
        if not self._components_loaded:
            # Return basic component info without full loading
            return {
                "ChatInput": {
                    "type": "inputs",
                    "description": "Get chat inputs from the Playground",
                    "inputs": [],
                    "outputs": ["message"]
                },
                "ChatOutput": {
                    "type": "outputs",
                    "description": "Display a chat message in the Playground",
                    "inputs": ["input_value"],
                    "outputs": ["message"]
                },
                "Agent": {
                    "type": "agents",
                    "description": "Agent component for conversational AI",
                    "inputs": ["input_value", "system_message", "tools"],
                    "outputs": ["response"]
                },
                "AutonomizeModel": {
                    "type": "models",
                    "description": "Unified clinical AI model component",
                    "inputs": ["search_query"],
                    "outputs": ["prediction"],
                    "options": {
                        "selected_model": [
                            "RxNorm Code",
                            "ICD-10 Code",
                            "CPT Code",
                            "Clinical LLM",
                            "Clinical Note Classifier",
                            "Combined Entity Linking"
                        ]
                    }
                },
                "Calculator": {
                    "type": "tools",
                    "description": "Calculator tool for mathematical operations",
                    "inputs": ["input_value"],
                    "outputs": ["output"]
                },
                "MCPTool": {
                    "type": "tools",
                    "description": "Model Context Protocol tool component",
                    "inputs": [],
                    "outputs": ["component_as_tool"]
                },
                "GenesisPromptComponent": {
                    "type": "prompts",
                    "description": "Genesis prompt template component",
                    "inputs": ["template", "saved_prompt"],
                    "outputs": ["prompt"]
                },
                "KnowledgeHubSearchComponent": {
                    "type": "tools",
                    "description": "Search component for knowledge hub documents",
                    "inputs": ["search_query", "collections", "search_type", "top_k"],
                    "outputs": ["query_results", "component_as_tool"]
                },
                "EncoderProTool": {
                    "type": "tools",
                    "description": "Service code encoding and validation tool",
                    "inputs": ["default_service_code", "include_descriptions", "validate_codes"],
                    "outputs": ["encoded_result", "component_as_tool"]
                }
            }

        # Extract basic info from loaded templates
        components_info = {}
        for name, template in self._component_cache.items():
            # Extract inputs from template
            template_dict = template.get("template", {})
            inputs = list(template_dict.keys())

            # Extract outputs
            outputs = []
            for output in template.get("outputs", []):
                if isinstance(output, dict) and "name" in output:
                    outputs.append(output["name"])

            # Try to determine component type from base classes
            base_classes = template.get("base_classes", [])
            comp_type = "unknown"
            if any("Input" in cls for cls in base_classes):
                comp_type = "inputs"
            elif any("Output" in cls for cls in base_classes):
                comp_type = "outputs"
            elif any("Agent" in cls for cls in base_classes):
                comp_type = "agents"
            elif any("Model" in cls for cls in base_classes):
                comp_type = "models"
            elif any("Tool" in cls for cls in base_classes):
                comp_type = "tools"

            components_info[name] = {
                "type": comp_type,
                "description": template.get("description", ""),
                "inputs": inputs,
                "outputs": outputs
            }

        return components_info


# Global instance
component_template_service = ComponentTemplateService()