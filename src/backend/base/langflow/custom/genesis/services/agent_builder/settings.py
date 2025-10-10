"""
Agent Builder Service Configuration Settings
"""

import os
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentBuilderSettings(BaseSettings):
    """Agent Builder service configuration settings."""

    # AI Gateway Configuration
    AI_GATEWAY_VIRTUAL_KEY: str = Field(
        description="AI Gateway virtual key for LLM access"
    )

    # Knowledge Base Configuration
    KB_DATA_PATH: Path = Field(
        default=Path(__file__).parent / "kb_data",
        description="Path to knowledge base data directory"
    )

    # Azure Search Configuration (reuse existing)
    AZURE_SEARCH_COMPONENT_INDEX: str = Field(
        default="component-embeddings",
        description="Azure Search index for component embeddings"
    )

    AZURE_SEARCH_CAPABILITY_INDEX: str = Field(
        default="capability-embeddings",
        description="Azure Search index for capability embeddings"
    )

    AZURE_SEARCH_COMPONENT_METADATA_INDEX: str = Field(
        default="component-metadata",
        description="Azure Search index for component metadata"
    )

    AZURE_SEARCH_AGENT_INDEX: str = Field(
        default="agent-metadata",
        description="Azure Search index for agent metadata"
    )

    # LLM Configuration
    LLM_MODEL: str = Field(
        default="gpt-4",
        description="LLM model to use for task decomposition"
    )

    # Search Configuration
    MAX_COMPONENT_RESULTS: int = Field(
        default=10,
        description="Maximum component search results"
    )

    MAX_AGENT_RESULTS: int = Field(
        default=5,
        description="Maximum agent search results"
    )

    model_config = SettingsConfigDict(
        env_prefix="", case_sensitive=True, validate_assignment=True, extra="ignore"
    )

    def is_configured(self) -> bool:
        """Check if Agent Builder is properly configured."""
        return bool(
            self.AI_GATEWAY_VIRTUAL_KEY and
            self.KB_DATA_PATH.exists()
        )
