"""Knowledge Base Service for loading and searching agent YAML files."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class AgentMetadata:
    """Lightweight agent metadata for searching."""

    def __init__(self, data: dict[str, Any], file_path: str):
        self.id = data.get("id", "")
        self.name = data.get("name", "")
        self.description = data.get("description", "")
        self.tags = data.get("tags", [])
        self.domain = data.get("domain", "")
        self.subdomain = data.get("subDomain", "")
        self.agent_goal = data.get("agentGoal", "")
        self.kind = data.get("kind", "")
        self.file_path = file_path
        self.full_data = data  # Keep for later loading

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "tags": self.tags,
            "domain": self.domain,
            "subdomain": self.subdomain,
            "goal": self.agent_goal,
            "kind": self.kind,
            "file_path": self.file_path,
        }

    def get_searchable_text(self) -> str:
        """Get all searchable text for keyword matching."""
        return " ".join(
            [
                self.name.lower(),
                self.description.lower(),
                self.agent_goal.lower(),
                " ".join(self.tags).lower(),
                self.domain.lower(),
                self.subdomain.lower(),
            ]
        )


class KnowledgeBaseService:
    """Service for loading and searching agent knowledge base."""

    def __init__(self, knowledge_base_path: str | Path | None = None):
        """Initialize the knowledge base service.

        Args:
            knowledge_base_path: Path to knowledge base directory. Defaults to project root/knowledge_base
        """
        if knowledge_base_path is None:
            # Default to project root/knowledge_base
            project_root = Path(__file__).parents[6]  # Navigate up to project root
            knowledge_base_path = project_root / "knowledge_base"
        else:
            knowledge_base_path = Path(knowledge_base_path)

        self.knowledge_base_path = knowledge_base_path
        self.agents: list[AgentMetadata] = []
        self._loaded = False

    def load_knowledge_base(self) -> None:
        """Load all YAML files from knowledge base directory."""
        if self._loaded:
            logger.debug("Knowledge base already loaded")
            return

        if not self.knowledge_base_path.exists():
            logger.warning(f"Knowledge base path does not exist: {self.knowledge_base_path}")
            return

        logger.info(f"Loading knowledge base from: {self.knowledge_base_path}")

        yaml_files = list(self.knowledge_base_path.glob("*.yaml")) + list(self.knowledge_base_path.glob("*.yml"))

        for yaml_file in yaml_files:
            try:
                with open(yaml_file) as f:
                    data = yaml.safe_load(f)
                    if data and isinstance(data, dict):
                        agent = AgentMetadata(data, str(yaml_file))
                        self.agents.append(agent)
                        logger.debug(f"Loaded agent: {agent.name}")
            except Exception as e:
                logger.exception(f"Error loading {yaml_file}: {e}")

        self._loaded = True
        logger.info(f"Loaded {len(self.agents)} agents from knowledge base")

    def search_agents(self, query: str, top_k: int = 5) -> list[AgentMetadata]:
        """Search agents using simple keyword matching.

        Args:
            query: User query string
            top_k: Number of top results to return

        Returns:
            List of top matching agents
        """
        if not self._loaded:
            self.load_knowledge_base()

        if not query or not self.agents:
            return []

        # Extract keywords from query
        query_words = set(query.lower().split())

        # Score each agent
        scores: list[tuple[AgentMetadata, int]] = []
        for agent in self.agents:
            searchable_text = agent.get_searchable_text()
            searchable_words = set(searchable_text.split())

            # Count word overlaps
            overlap = len(query_words & searchable_words)

            # Bonus for exact phrase matches
            if query.lower() in searchable_text:
                overlap += 5

            scores.append((agent, overlap))

        # Sort by score and return top K
        sorted_agents = sorted(scores, key=lambda x: x[1], reverse=True)
        top_agents = [agent for agent, score in sorted_agents[:top_k] if score > 0]

        logger.info(f"Found {len(top_agents)} matching agents for query: '{query}'")
        return top_agents

    def get_agent_by_id(self, agent_id: str) -> AgentMetadata | None:
        """Get agent by ID.

        Args:
            agent_id: Agent ID

        Returns:
            Agent metadata or None if not found
        """
        if not self._loaded:
            self.load_knowledge_base()

        for agent in self.agents:
            if agent.id == agent_id:
                return agent
        return None

    def get_all_agents(self) -> list[AgentMetadata]:
        """Get all loaded agents.

        Returns:
            List of all agents
        """
        if not self._loaded:
            self.load_knowledge_base()

        return self.agents


# Global instance
_knowledge_base_service: KnowledgeBaseService | None = None


def get_knowledge_base_service() -> KnowledgeBaseService:
    """Get or create the global knowledge base service instance.

    Returns:
        Knowledge base service instance
    """
    global _knowledge_base_service
    if _knowledge_base_service is None:
        _knowledge_base_service = KnowledgeBaseService()
        _knowledge_base_service.load_knowledge_base()
    return _knowledge_base_service
