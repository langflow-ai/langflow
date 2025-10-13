"""
Knowledge Base Loader for Agent Builder Service

Loads and manages agent and component knowledge base data.
Adapted from Genesis KnowledgeBaseLoader for service context.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from .settings import AgentBuilderSettings


@dataclass
class ComponentSpec:
    """Component specification with I/O details"""
    component_id: str
    component_type: str
    name: str
    description: str
    purpose: str
    category: str
    input_data_types: List[str]
    output_data_types: List[str]
    capabilities: List[str]
    sends_output_to: List[str]
    accepts_input_from: List[str]


@dataclass
class AgentSpec:
    """Agent specification with components and capabilities"""
    agent_id: str
    name: str
    description: str
    agent_goal: str
    capabilities: List[str]
    components: List[ComponentSpec]
    domain: str
    complexity_score: int


class KnowledgeBaseLoader:
    """Loads and manages all knowledge base data"""

    def __init__(self, settings: AgentBuilderSettings):
        self.logger = logging.getLogger(__name__)
        self.settings = settings

        # Knowledge base data
        self.agent_kb: Dict[str, AgentSpec] = {}
        self.component_kb: Dict[str, ComponentSpec] = {}
        self.tools_kb: Dict[str, Dict[str, Any]] = {}
        self.models_kb: Dict[str, Dict[str, Any]] = {}

        # Load all knowledge bases
        self._load_all_knowledge_bases()

    def _load_all_knowledge_bases(self):
        """Load all knowledge base files"""
        try:
            kb_path = self.settings.KB_DATA_PATH

            # Load agent knowledge base
            agent_kb_path = kb_path / "agent_kb.json"
            if agent_kb_path.exists():
                with open(agent_kb_path, 'r') as f:
                    agent_data = json.load(f)
                    self._process_agent_kb(agent_data)
                self.logger.info(f"Loaded {len(self.agent_kb)} agents")
            else:
                self.logger.warning(f"Agent KB not found: {agent_kb_path}")

            # Load component knowledge base
            component_kb_path = kb_path / "component_kb.json"
            if component_kb_path.exists():
                with open(component_kb_path, 'r') as f:
                    component_data = json.load(f)
                    self._process_component_kb(component_data)
                self.logger.info(f"Loaded {len(self.component_kb)} components")
            else:
                self.logger.warning(f"Component KB not found: {component_kb_path}")

            # Load tools knowledge base
            tools_kb_path = kb_path / "tools_kb.json"
            if tools_kb_path.exists():
                with open(tools_kb_path, 'r') as f:
                    self.tools_kb = json.load(f)
                self.logger.info(f"Loaded {len(self.tools_kb)} tools")

            # Load models knowledge base
            models_kb_path = kb_path / "models_kb.json"
            if models_kb_path.exists():
                with open(models_kb_path, 'r') as f:
                    self.models_kb = json.load(f)
                self.logger.info(f"Loaded {len(self.models_kb)} models")

        except Exception as e:
            self.logger.error(f"Error loading knowledge bases: {e}")
            raise

    def _process_agent_kb(self, agent_data: Dict[str, Any]):
        """Process agent knowledge base data"""
        for agent_id, agent_info in agent_data.items():
            components = []
            for comp_data in agent_info.get("components", []):
                component = ComponentSpec(
                    component_id=comp_data.get("component_id", ""),
                    component_type=comp_data.get("component_type", ""),
                    name=comp_data.get("name", ""),
                    description=comp_data.get("description", ""),
                    purpose=comp_data.get("purpose", ""),
                    category=comp_data.get("category", ""),
                    input_data_types=comp_data.get("input_data_types", []),
                    output_data_types=comp_data.get("output_data_types", []),
                    capabilities=comp_data.get("capabilities", []),
                    sends_output_to=comp_data.get("sends_output_to", []),
                    accepts_input_from=comp_data.get("accepts_input_from", [])
                )
                components.append(component)

            agent = AgentSpec(
                agent_id=agent_id,
                name=agent_info.get("name", ""),
                description=agent_info.get("description", ""),
                agent_goal=agent_info.get("agent_goal", ""),
                capabilities=agent_info.get("capabilities", []),
                components=components,
                domain=agent_info.get("domain", ""),
                complexity_score=agent_info.get("complexity_score", 1)
            )
            self.agent_kb[agent_id] = agent

    def _process_component_kb(self, component_data: Dict[str, Any]):
        """Process component knowledge base data"""
        for comp_id, comp_info in component_data.items():
            component = ComponentSpec(
                component_id=comp_id,
                component_type=comp_info.get("component_type", ""),
                name=comp_info.get("name", ""),
                description=comp_info.get("description", ""),
                purpose=comp_info.get("purpose", ""),
                category=comp_info.get("category", ""),
                input_data_types=comp_info.get("input_data_types", []),
                output_data_types=comp_info.get("output_data_types", []),
                capabilities=comp_info.get("capabilities", []),
                sends_output_to=comp_info.get("sends_output_to", []),
                accepts_input_from=comp_info.get("accepts_input_from", [])
            )
            self.component_kb[comp_id] = component
