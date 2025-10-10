"""
Semantic Search Engine for Agent Builder Service

Integrates Azure Search with local knowledge base for component discovery.
"""

import logging
from typing import List
from dataclasses import dataclass

from .kb_loader import ComponentSpec, KnowledgeBaseLoader
from .settings import AgentBuilderSettings
from ..deps import get_azure_search_service


@dataclass
class ComponentMatch:
    """Match result from semantic search"""
    component_spec: ComponentSpec
    overall_score: float


class SemanticSearchEngine:
    """Engine for semantic search using Azure Search + local KB"""

    def __init__(self, kb_loader: KnowledgeBaseLoader, settings: AgentBuilderSettings):
        self.logger = logging.getLogger(__name__)
        self.kb_loader = kb_loader
        self.settings = settings

    async def search_components(
        self,
        subtask_query: str,
        required_capabilities: List[str],
        data_types: List[str],
        component_category: str,
        top_k: int = 5
    ) -> List[ComponentMatch]:
        """
        Search for components matching the given criteria.

        Uses Azure Search for semantic matching, then enriches with local KB data.
        """
        try:
            # Get Azure Search service
            azure_search = get_azure_search_service()

            # Build search query from capabilities
            if required_capabilities:
                # Search by capabilities using Azure Search
                search_results = await azure_search.search_capability_embeddings(
                    query=subtask_query,
                    capabilities=required_capabilities,
                    top=top_k
                )

                matches = []
                for result in search_results:
                    # Get component details from local KB
                    component_key = result.get('component_key')
                    if component_key and component_key in self.kb_loader.component_kb:
                        component_spec = self.kb_loader.component_kb[component_key]
                        score = result.get('@search.score', 0.5)

                        matches.append(ComponentMatch(
                            component_spec=component_spec,
                            overall_score=float(score)
                        ))

                return matches

            else:
                # Fallback: search component embeddings directly
                search_results = await azure_search.search_component_embeddings(
                    query=subtask_query,
                    top=top_k
                )

                matches = []
                for result in search_results:
                    component_key = result.get('component_key')
                    if component_key and component_key in self.kb_loader.component_kb:
                        component_spec = self.kb_loader.component_kb[component_key]
                        score = result.get('@search.score', 0.5)

                        matches.append(ComponentMatch(
                            component_spec=component_spec,
                            overall_score=float(score)
                        ))

                return matches

        except Exception as e:
            self.logger.error(f"Error in semantic search: {e}")
            # Return empty list on error - service should continue
            return []
