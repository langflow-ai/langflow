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
        """Load valid genesis components dynamically from the mapper."""
        if self._components_cache is not None:
            return self._components_cache

        try:
            # Import the mapper to get the actual valid components
            from langflow.custom.genesis.spec.mapper import ComponentMapper

            mapper = ComponentMapper()
            components = {}

            # Combine all mappings from the mapper (single source of truth)
            all_mappings = {
                **mapper.STANDARD_MAPPINGS,
                **mapper.MCP_MAPPINGS,
                **mapper.AUTONOMIZE_MODELS
            }

            # Build component info from actual mappings
            for spec_type, mapping in all_mappings.items():
                component_name = mapping.get("component", "Unknown")
                config = mapping.get("config", {})

                components[spec_type] = {
                    "name": component_name,
                    "category": self._get_category(spec_type),
                    "purpose": self._get_purpose(spec_type, component_name),
                    "langflow_component": component_name,
                    "config": config,
                    "dataType": mapping.get("dataType", None)
                }

            self._components_cache = components
            return components

        except ImportError as e:
            logger.error(f"Could not import ComponentMapper: {e}")
            # Fallback to a minimal set if import fails
            return {
                "genesis:chat_input": {"name": "ChatInput", "category": "Input"},
                "genesis:chat_output": {"name": "ChatOutput", "category": "Output"},
                "genesis:agent": {"name": "Agent", "category": "Agent"},
                "genesis:language_model": {"name": "LanguageModelComponent", "category": "Model"}
            }

    def _get_category(self, spec_type: str) -> str:
        """Determine category based on component type."""
        if "input" in spec_type:
            return "Input"
        elif "output" in spec_type:
            return "Output"
        elif "agent" in spec_type:
            return "Agent"
        elif "model" in spec_type or "llm" in spec_type:
            return "Model"
        elif "prompt" in spec_type:
            return "Prompt"
        elif "tool" in spec_type or "mcp" in spec_type:
            return "Tool"
        elif "crew" in spec_type:
            return "Crew"
        elif "task" in spec_type:
            return "Task"
        elif "memory" in spec_type:
            return "Memory"
        elif "api" in spec_type or "request" in spec_type:
            return "Integration"
        else:
            return "Component"

    def _get_purpose(self, spec_type: str, component_name: str) -> str:
        """Generate purpose description based on component type."""
        purposes = {
            "genesis:chat_input": "Accept user input",
            "genesis:chat_output": "Display results to user",
            "genesis:agent": "LLM-powered processing with tools",
            "genesis:language_model": "Simple LLM without tool capabilities",
            "genesis:prompt_template": "Manage complex prompts",
            "genesis:mcp_tool": "External tool integration via MCP",
            "genesis:api_request": "Direct HTTP API calls",
            "genesis:knowledge_hub_search": "Search internal knowledge base",
            "genesis:crewai_agent": "Specialized agent for crew",
            "genesis:crewai_sequential_task": "Task for sequential crew",
            "genesis:crewai_sequential_crew": "Orchestrate sequential tasks",
            "genesis:crewai_hierarchical_crew": "Manager-worker crew pattern",
            "genesis:memory": "Maintain conversation context",
            "genesis:autonomize_model": "Clinical AI model",
            "genesis:rxnorm": "RxNorm medication coding",
            "genesis:icd10": "ICD-10 diagnosis coding",
            "genesis:cpt_code": "CPT procedure coding"
        }

        return purposes.get(spec_type, f"Process with {component_name}")

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