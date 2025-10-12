"""Knowledge Loader for AI Studio Agent Builder - Loads valid components and patterns."""

import os
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
from langflow.custom.custom_component.component import Component
from langflow.inputs import MessageTextInput, BoolInput
from langflow.io import Output
from langflow.schema.data import Data
from langflow.logging import logger


class KnowledgeLoader(Component):
    """Loads and provides available genesis components, patterns, and specifications."""

    display_name = "Knowledge Loader"
    description = "Loads valid components, patterns, and specifications from the library"
    icon = "book-open"
    name = "KnowledgeLoader"
    category = "Helpers"

    # Cache for loaded knowledge
    _components_cache: Optional[Dict] = None
    _patterns_cache: Optional[Dict] = None
    _specifications_cache: Optional[List] = None

    inputs = [
        MessageTextInput(
            name="query_type",
            display_name="Query Type",
            info="Type of knowledge to load: components, patterns, specifications, or all",
            value="all",
            tool_mode=True,
        ),
        BoolInput(
            name="reload_cache",
            display_name="Reload Cache",
            info="Force reload from disk",
            value=False,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Knowledge Data", name="knowledge", method="load_knowledge"),
    ]

    def load_knowledge(self) -> Data:
        """Load requested knowledge from the library."""
        try:
            if self.reload_cache:
                self._clear_cache()

            result = {}

            if self.query_type in ["components", "all"]:
                result["components"] = self._load_components()

            if self.query_type in ["patterns", "all"]:
                result["patterns"] = self._load_patterns()

            if self.query_type in ["specifications", "all"]:
                result["specifications"] = self._load_specifications()

            return Data(data={
                "success": True,
                "knowledge": result,
                "message": f"Loaded {self.query_type} knowledge successfully"
            })

        except Exception as e:
            logger.error(f"Error loading knowledge: {e}")
            return Data(data={
                "success": False,
                "error": str(e)
            })

    def _load_components(self) -> Dict:
        """Load valid genesis components that can be deployed."""
        if self._components_cache is not None:
            return self._components_cache

        # These are the ONLY components that can be used in specifications
        # Based on actual deployed specifications in the library
        components = {
            "genesis:chat_input": {
                "name": "Chat Input",
                "category": "Data",
                "purpose": "Accept user input",
                "required_config": [],
                "connections": {
                    "provides": ["input"]
                }
            },
            "genesis:chat_output": {
                "name": "Chat Output",
                "category": "Data",
                "purpose": "Display results to user",
                "required_config": [],
                "connections": {
                    "receives": ["input"]
                }
            },
            "genesis:agent": {
                "name": "Agent",
                "category": "Agent",
                "purpose": "LLM-powered processing",
                "required_config": ["system_prompt", "temperature", "max_tokens"],
                "optional_config": ["tools", "model_name"],
                "connections": {
                    "receives": ["input", "prompt", "tools"],
                    "provides": ["input", "output"]
                }
            },
            "genesis:prompt_template": {
                "name": "Prompt Template",
                "category": "Prompt",
                "purpose": "Manage complex prompts",
                "required_config": ["template"],
                "optional_config": ["saved_prompt"],
                "connections": {
                    "provides": ["prompt"]
                }
            },
            "genesis:mcp_tool": {
                "name": "MCP Tool",
                "category": "Tool",
                "purpose": "External tool integration via MCP",
                "required_config": ["tool_name", "description"],
                "optional_config": ["mock_response"],
                "connections": {
                    "provides": ["tools"]
                },
                "note": "Requires MCP server or uses mock response"
            },
            "genesis:api_request": {
                "name": "API Request",
                "category": "Tool",
                "purpose": "Direct HTTP API calls",
                "required_config": ["method", "url_input"],
                "optional_config": ["headers", "body", "timeout"],
                "connections": {
                    "provides": ["tools", "output"]
                }
            },
            "genesis:knowledge_hub_search": {
                "name": "Knowledge Hub Search",
                "category": "Tool",
                "purpose": "Search internal knowledge base",
                "required_config": ["search_query"],
                "optional_config": ["max_results"],
                "connections": {
                    "provides": ["tools", "output"]
                }
            }
        }

        # CrewAI components for multi-agent (only if multi-agent pattern is needed)
        components.update({
            "genesis:crewai_agent": {
                "name": "CrewAI Agent",
                "category": "Agent",
                "purpose": "Specialized agent for crew",
                "required_config": ["role", "goal", "backstory"],
                "optional_config": ["tools", "delegation"],
                "connections": {
                    "receives": ["tools"],
                    "provides": ["agent"]
                }
            },
            "genesis:crewai_sequential_task": {
                "name": "Sequential Task",
                "category": "Task",
                "purpose": "Task for sequential crew",
                "required_config": ["description", "expected_output"],
                "optional_config": ["agent"],
                "connections": {
                    "receives": ["agent"],
                    "provides": ["task"]
                }
            },
            "genesis:crewai_sequential_crew": {
                "name": "Sequential Crew",
                "category": "Crew",
                "purpose": "Orchestrate sequential tasks",
                "required_config": ["tasks"],
                "optional_config": ["verbose"],
                "connections": {
                    "receives": ["tasks", "agents"],
                    "provides": ["output"]
                }
            }
        })

        self._components_cache = components
        return components

    def _load_patterns(self) -> Dict:
        """Load valid patterns that can be created."""
        if self._patterns_cache is not None:
            return self._patterns_cache

        patterns = {
            "simple_linear": {
                "name": "Simple Linear Agent",
                "complexity": "simple",
                "components_count": 3,
                "structure": "Input → Agent → Output",
                "components": ["genesis:chat_input", "genesis:agent", "genesis:chat_output"],
                "use_cases": ["Basic processing", "Classification", "Extraction"],
                "example_specs": ["document-processor", "classification-agent"]
            },
            "agent_with_prompt": {
                "name": "Agent with External Prompt",
                "complexity": "simple",
                "components_count": 4,
                "structure": "Input → Agent (← Prompt) → Output",
                "components": ["genesis:chat_input", "genesis:prompt_template", "genesis:agent", "genesis:chat_output"],
                "use_cases": ["Complex prompts", "Prompt versioning", "Reusable logic"],
                "example_specs": ["medication-extractor"]
            },
            "agent_with_tool": {
                "name": "Agent with Single Tool",
                "complexity": "medium",
                "components_count": 4,
                "structure": "Input → Agent (← Tool) → Output",
                "components": ["genesis:chat_input", "genesis:agent", "genesis:mcp_tool or genesis:api_request", "genesis:chat_output"],
                "use_cases": ["External data access", "API integration", "Tool usage"],
                "example_specs": ["insurance-verifier"]
            },
            "multi_tool_agent": {
                "name": "Multi-Tool Agent",
                "complexity": "complex",
                "components_count": "6+",
                "structure": "Input → Agent (← Multiple Tools) → Output",
                "components": ["genesis:chat_input", "genesis:agent", "multiple genesis:mcp_tool/api_request", "genesis:chat_output"],
                "use_cases": ["Multiple integrations", "Complex workflows", "Healthcare automation"],
                "example_specs": ["appointment-concierge", "prior-auth-processor"]
            }
        }

        self._patterns_cache = patterns
        return patterns

    def _load_specifications(self) -> List[Dict]:
        """Load example specifications from the library."""
        if self._specifications_cache is not None:
            return self._specifications_cache

        spec_library_path = Path(__file__).parent.parent.parent.parent / "specifications_library" / "agents"

        specifications = []

        if spec_library_path.exists():
            # Load a sample of specifications as examples
            for spec_file in spec_library_path.rglob("*.yaml")[:10]:  # Limit to 10 examples
                try:
                    with open(spec_file, 'r') as f:
                        spec = yaml.safe_load(f)
                        specifications.append({
                            "name": spec.get("name", "Unknown"),
                            "id": spec.get("id", ""),
                            "domain": spec.get("domain", ""),
                            "kind": spec.get("kind", "Single Agent"),
                            "components_count": len(spec.get("components", [])),
                            "file": str(spec_file.relative_to(spec_library_path)),
                            "description": spec.get("description", "")
                        })
                except Exception as e:
                    logger.debug(f"Error loading spec {spec_file}: {e}")

        self._specifications_cache = specifications
        return specifications

    def _clear_cache(self):
        """Clear all cached data."""
        self._components_cache = None
        self._patterns_cache = None
        self._specifications_cache = None