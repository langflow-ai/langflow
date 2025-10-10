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
            # Generate embeddings for the text query
            query_vector = await self._generate_embeddings(subtask_query)

            # Get Azure Search service
            azure_search = get_azure_search_service()

            # Use the combined search method that handles both semantic and capability matching
            search_results = await azure_search.search_components(
                query_text=subtask_query,
                query_vector=query_vector,
                capabilities=required_capabilities if required_capabilities else None,
                top_k=top_k
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

        except Exception as e:
            self.logger.error(f"Error in semantic search: {e}")
            # Return empty list on error - service should continue
            return []

    async def _generate_embeddings(self, text: str) -> List[float]:
        """
        Generate embeddings for text using SentenceTransformers.

        Uses the same model as the original genesis-agents-cli for compatibility.
        """
        try:
            from sentence_transformers import SentenceTransformer

            # Use the same model as original genesis-agents-cli (384 dimensions)
            model = SentenceTransformer('all-MiniLM-L6-v2')
            embeddings = model.encode(text, normalize_embeddings=True)

            return embeddings.tolist()

        except ImportError:
            self.logger.error("SentenceTransformers not available for embedding generation")
            # Return zero vector as fallback
            return [0.0] * 384  # all-MiniLM-L6-v2 dimension
        except Exception as e:
            self.logger.error(f"Error generating embeddings: {e}")
            # Return zero vector as fallback
            return [0.0] * 384
