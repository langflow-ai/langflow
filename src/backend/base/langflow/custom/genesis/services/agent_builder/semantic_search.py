"""
Semantic Search Engine for Agent Builder Service

Implements semantic search with Sentence-BERT embeddings, multi-factor scoring,
and chain-aware component matching - following the original genesis-agents-cli pipeline.
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from .kb_loader import ComponentSpec, KnowledgeBaseLoader
from .settings import AgentBuilderSettings


@dataclass
class ComponentMatch:
    """Match result from semantic search"""
    component_key: str
    component_spec: ComponentSpec
    similarity_score: float
    capability_match_score: float
    data_type_match_score: float
    category_match_score: float
    overall_score: float
    reasoning: str


class SemanticSearchEngine:
    """Engine for semantic search with embeddings and multi-factor scoring"""

    def __init__(self, kb_loader: KnowledgeBaseLoader, settings: AgentBuilderSettings):
        self.logger = logging.getLogger(__name__)
        self.kb_loader = kb_loader
        self.settings = settings

        # Initialize embedding model and pre-compute component embeddings
        self.embedding_model = None
        self.component_embeddings: Dict[str, np.ndarray] = {}
        self.capability_embeddings: Dict[str, np.ndarray] = {}

        # Pre-build embeddings index (like original pipeline)
        self._build_embeddings_index()

    def _build_embeddings_index(self):
        """Build embeddings index for fast semantic search (Phase 1 optimization)"""
        try:
            self.logger.info("Building embeddings index...")

            # Initialize Sentence-BERT model
            try:
                from sentence_transformers import SentenceTransformer
                self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
                self.logger.info("Initialized Sentence-BERT model: all-MiniLM-L6-v2")
            except ImportError:
                self.logger.error("SentenceTransformers not available - semantic search disabled")
                return

            # Pre-compute embeddings for all components
            for comp_key, comp_spec in self.kb_loader.component_kb.items():
                # Combine description and capabilities for richer embedding
                text_to_embed = f"{comp_spec.description} {' '.join(comp_spec.capabilities)}"
                try:
                    embedding = self.embedding_model.encode(text_to_embed, convert_to_numpy=True)
                    self.component_embeddings[comp_key] = embedding
                except Exception as e:
                    self.logger.warning(f"Failed to embed component {comp_key}: {e}")

                # Also embed individual capabilities
                for capability in comp_spec.capabilities:
                    if capability not in self.capability_embeddings:
                        try:
                            cap_embedding = self.embedding_model.encode(capability, convert_to_numpy=True)
                            self.capability_embeddings[capability] = cap_embedding
                        except Exception as e:
                            self.logger.warning(f"Failed to embed capability {capability}: {e}")

            # Pre-compute embeddings for agents (synthetic components)
            for agent_key, agent_spec in self.kb_loader.agent_kb.items():
                synthetic_key = f"agent:{agent_key}"
                agent_text = f"{agent_spec.name} {agent_spec.description} {' '.join(agent_spec.capabilities)}"
                try:
                    agent_embedding = self.embedding_model.encode(agent_text, convert_to_numpy=True)
                    self.component_embeddings[synthetic_key] = agent_embedding
                except Exception as e:
                    self.logger.warning(f"Failed to embed agent {agent_key}: {e}")

            self.logger.info(f"Built embeddings for {len(self.component_embeddings)} components/agents")

        except Exception as e:
            self.logger.error(f"Error building embeddings index: {e}")

    async def search_components(
        self,
        subtask_query: str,
        required_capabilities: List[str],
        data_types: List[str],
        component_category: str,
        chain_context: Optional[Dict[str, Any]] = None,
        top_k: int = 5
    ) -> List[ComponentMatch]:
        """
        Search for components matching the subtask with multi-factor scoring.

        Implements the complete Phase 3 semantic search from the original pipeline:
        - Sentence-BERT semantic similarity
        - Multi-factor scoring (similarity, capability, data types, category)
        - Chain-aware adjustments
        - Healthcare domain specialization
        """
        if not self.embedding_model:
            self.logger.warning("Embedding model not available - returning empty results")
            return []

        try:
            self.logger.info(f"🔍 Searching for subtask: '{subtask_query}'")
            self.logger.info(f"   Required capabilities: {required_capabilities}")
            self.logger.info(f"   Data types: {data_types}")
            self.logger.info(f"   Component category: {component_category}")

            # Generate query embedding
            query_embedding = self.embedding_model.encode(subtask_query, convert_to_numpy=True)

            matches = []

            # Search through all components and synthetic agent components
            all_search_items = []

            # Add individual components
            for comp_key, comp_spec in self.kb_loader.component_kb.items():
                if comp_key in self.component_embeddings:
                    all_search_items.append(('component', comp_key, comp_spec))

            # Add synthetic agent representations
            for agent_key, agent_spec in self.kb_loader.agent_kb.items():
                synthetic_key = f"agent:{agent_key}"
                if synthetic_key in self.component_embeddings:
                    # Create synthetic component spec from agent
                    synthetic_spec = self._create_synthetic_component_from_agent(agent_spec)
                    if synthetic_spec:
                        all_search_items.append(('agent', synthetic_key, synthetic_spec))

            # Score each component
            for item_type, item_key, comp_spec in all_search_items:
                # Semantic similarity scoring
                similarity_score = self._calculate_similarity_score(query_embedding, item_key)

                # Multi-factor scoring
                capability_score = self._calculate_capability_match_score(required_capabilities, comp_spec.capabilities)
                data_type_score = self._calculate_data_type_match_score(data_types, comp_spec.input_data_types, comp_spec.output_data_types)
                category_score = self._calculate_category_match_score(component_category, comp_spec.category)

                # Chain context adjustments
                chain_adjustment = self._apply_chain_context_adjustment(comp_spec, chain_context or {})

                # Calculate overall score with weights (matching original pipeline)
                overall_score = (
                    similarity_score * 0.4 +      # Semantic similarity (40%)
                    capability_score * 0.6 +      # Capability matching (60%)
                    data_type_score * 0.3 +       # Data type compatibility (30%)
                    category_score * 0.1 +        # Category preference (10%)
                    chain_adjustment               # Chain context bonus/penalty
                )

                # Generate reasoning
                reasoning = self._generate_match_reasoning(similarity_score, capability_score, data_type_score, category_score)

                match = ComponentMatch(
                    component_key=item_key,
                    component_spec=comp_spec,
                    similarity_score=float(similarity_score),
                    capability_match_score=capability_score,
                    data_type_match_score=data_type_score,
                    category_match_score=category_score,
                    overall_score=float(overall_score),
                    reasoning=reasoning
                )

                matches.append(match)

            # Sort by overall score and return top results
            matches.sort(key=lambda x: x.overall_score, reverse=True)

            # Log top matches for debugging
            self.logger.info(f"Top {min(5, len(matches))} matches:")
            for i, match in enumerate(matches[:5]):
                self.logger.info(f"  {i+1}. {match.component_spec.name} (score: {match.overall_score:.3f})")

            # Filter by similarity threshold (from original pipeline)
            filtered_matches = [
                match for match in matches[:top_k * 2]  # Get more for better selection
                if match.overall_score >= 0.3  # Configurable threshold
            ]

            # Return top_k results
            final_matches = filtered_matches[:top_k]
            self.logger.info(f"Returning {len(final_matches)} matching components")

            return final_matches

        except Exception as e:
            self.logger.error(f"Error in semantic search: {e}")
            return []

    def _calculate_similarity_score(self, query_embedding: np.ndarray, component_key: str) -> float:
        """Calculate semantic similarity using cosine similarity"""
        if component_key not in self.component_embeddings:
            return 0.0

        comp_embedding = self.component_embeddings[component_key]
        similarity = cosine_similarity([query_embedding], [comp_embedding])[0][0]

        return float(similarity)

    def _calculate_capability_match_score(self, required_caps: List[str], component_caps: List[str]) -> float:
        """Calculate capability match score"""
        if not required_caps:
            return 0.5  # Neutral score if no requirements

        matches = 0
        for req_cap in required_caps:
            # Exact match
            if req_cap in component_caps:
                matches += 1
            else:
                # Semantic similarity with existing capabilities
                best_similarity = 0.0
                if req_cap in self.capability_embeddings:
                    req_embedding = self.capability_embeddings[req_cap]
                    for comp_cap in component_caps:
                        if comp_cap in self.capability_embeddings:
                            comp_embedding = self.capability_embeddings[comp_cap]
                            sim = cosine_similarity([req_embedding], [comp_embedding])[0][0]
                            best_similarity = max(best_similarity, sim)

                if best_similarity > 0.8:  # High similarity threshold
                    matches += 0.5

        return min(matches / len(required_caps), 1.0)

    def _calculate_data_type_match_score(self, required_types: List[str],
                                       input_types: List[str], output_types: List[str]) -> float:
        """Calculate data type compatibility score"""
        if not required_types:
            return 0.5  # Neutral score

        # Check if component can handle required data types
        compatible_inputs = any(req_type in input_types for req_type in required_types)
        compatible_outputs = any(req_type in output_types for req_type in required_types)

        if compatible_inputs or compatible_outputs:
            return 1.0
        else:
            # Check for compatible conversions (healthcare-specific)
            conversions = self._check_data_type_conversions(required_types, input_types + output_types)
            return min(conversions * 0.7, 0.8)  # Partial credit for conversions

    def _calculate_category_match_score(self, required_category: str, component_category: str) -> float:
        """Calculate category match score"""
        if not required_category:
            return 0.5  # Neutral score

        if required_category == component_category:
            return 1.0
        elif self._are_categories_compatible(required_category, component_category):
            return 0.7
        else:
            return 0.0

    def _apply_chain_context_adjustment(self, comp_spec: ComponentSpec, chain_context: Dict[str, Any]) -> float:
        """Apply chain-aware adjustments to component scoring"""
        adjustment = 0.0

        # Previous component outputs compatibility
        previous_outputs = chain_context.get('previous_outputs', [])
        if previous_outputs:
            compatible_inputs = any(
                prev_output in comp_spec.input_data_types
                for prev_output in previous_outputs
            )
            if compatible_inputs:
                adjustment += 0.3  # Strong boost for data type compatibility
            else:
                # Check for conversions
                conversion_possible = self._check_conversion_possible(previous_outputs, comp_spec.input_data_types)
                if conversion_possible:
                    adjustment += 0.15  # Boost for conversions
                else:
                    adjustment -= 0.2  # Penalty for incompatible types

        # Chain position awareness
        chain_position = chain_context.get('position', 'middle')
        if chain_position == 'start':
            # At start, prefer input components
            if comp_spec.category == 'data' and 'input' in comp_spec.name.lower():
                adjustment += 0.2  # Boost for input components at start
            else:
                adjustment -= 0.5  # Strong penalty for non-input at start
        elif chain_position == 'end':
            # At end, prefer output components
            if comp_spec.category == 'data' and 'output' in comp_spec.name.lower():
                adjustment += 0.2  # Boost for output components at end
            else:
                adjustment -= 0.5  # Strong penalty for non-output at end

        # Avoid redundant capabilities in chain
        chain_capabilities = set(chain_context.get('chain_capabilities', []))
        component_caps = set(comp_spec.capabilities)
        overlap = len(chain_capabilities.intersection(component_caps))
        if overlap > 0:
            adjustment -= 0.1 * overlap  # Penalty for redundancy

        # Healthcare domain boost
        healthcare_caps = {'medical_processing', 'clinical_data_input', 'patient_data_processing',
                          'clinical_validation', 'medical_data_extraction', 'clinical_summarization'}
        component_healthcare_caps = healthcare_caps.intersection(component_caps)
        if component_healthcare_caps:
            adjustment += 0.1 * len(component_healthcare_caps)

        return adjustment

    def _check_data_type_conversions(self, required_types: List[str], available_types: List[str]) -> float:
        """Check for data type conversions"""
        conversions = {
            'text': ['json', 'structured_data', 'clinical_text'],
            'json': ['text', 'structured_data'],
            'structured_data': ['json', 'text'],
            'clinical_text': ['text', 'json', 'structured_data']
        }

        conversion_count = 0
        for req_type in required_types:
            if req_type in available_types:
                conversion_count += 1
            else:
                possible_conversions = conversions.get(req_type, [])
                if any(conv_type in available_types for conv_type in possible_conversions):
                    conversion_count += 0.5

        return conversion_count / len(required_types) if required_types else 0.0

    def _check_conversion_possible(self, available_outputs: List[str], required_inputs: List[str]) -> bool:
        """Check if data type conversion is possible"""
        conversions = {
            'text': ['json', 'structured_data', 'clinical_text'],
            'json': ['text', 'structured_data'],
            'structured_data': ['json', 'text'],
            'clinical_text': ['text', 'json', 'structured_data']
        }

        for available in available_outputs:
            possible_conversions = conversions.get(available, [])
            if any(req in possible_conversions for req in required_inputs):
                return True
        return False

    def _are_categories_compatible(self, required: str, available: str) -> bool:
        """Check if component categories are compatible"""
        compatibility_map = {
            'input': ['input', 'data'],
            'output': ['output', 'data'],
            'processing': ['processing', 'agent', 'tool', 'model'],
            'data': ['input', 'output', 'data']
        }
        return available in compatibility_map.get(required, [])

    def _generate_match_reasoning(self, similarity: float, capability: float,
                                data_type: float, category: float) -> str:
        """Generate human-readable reasoning for match"""
        reasons = []

        if similarity > 0.8:
            reasons.append("High semantic similarity")
        elif similarity > 0.6:
            reasons.append("Good semantic match")

        if capability == 1.0:
            reasons.append("Perfect capability match")
        elif capability > 0.7:
            reasons.append("Strong capability alignment")

        if data_type == 1.0:
            reasons.append("Data type compatible")
        elif data_type > 0.5:
            reasons.append("Data type partially compatible")

        if category == 1.0:
            reasons.append("Category match")

        return "; ".join(reasons) if reasons else "General match"

    def _create_synthetic_component_from_agent(self, agent_spec: Any) -> Optional[ComponentSpec]:
        """Create a synthetic component spec from an agent for search purposes"""
        try:
            # Infer capabilities from agent metadata
            agent_text = f"{agent_spec.name} {agent_spec.description} {agent_spec.agent_goal}"
            agent_capabilities = self._infer_agent_capabilities(agent_text, agent_spec)

            # Infer I/O types based on agent type and capabilities
            input_types = self._infer_agent_input_types(agent_spec, agent_capabilities)
            output_types = self._infer_agent_output_types(agent_spec, agent_capabilities)

            # Create synthetic component spec
            accepts_from = ["genesis:*", "agent:*"]

            synthetic_spec = ComponentSpec(
                component_id=agent_spec.agent_id,
                component_type=f"agent:{agent_spec.agent_id}",
                name=agent_spec.name,
                description=agent_spec.description,
                purpose=agent_spec.agent_goal,
                category="processing",
                input_data_types=input_types,
                output_data_types=output_types,
                capabilities=agent_capabilities,
                sends_output_to=[],
                accepts_input_from=accepts_from
            )

            return synthetic_spec

        except Exception as e:
            self.logger.warning(f"Failed to create synthetic component from agent {agent_spec.agent_id}: {e}")
            return None

    def _infer_agent_capabilities(self, agent_text: str, agent_spec: Any) -> List[str]:
        """Infer capabilities for agents based on their metadata"""
        capabilities = []
        text_lower = agent_text.lower()

        # Healthcare-specific agent capability inference
        if 'summary' in text_lower or 'summarization' in text_lower:
            capabilities.extend(['clinical_summarization', 'medical_content_analysis', 'content_generation'])
        if 'extraction' in text_lower or 'extract' in text_lower:
            capabilities.extend(['medical_data_extraction', 'clinical_data_processing'])
        if 'validation' in text_lower or 'validate' in text_lower:
            capabilities.extend(['clinical_validation', 'medical_verification'])
        if 'check' in text_lower or 'eligibility' in text_lower:
            capabilities.extend(['patient_eligibility_check', 'insurance_coverage_check'])
        if 'episode' in text_lower or 'update' in text_lower:
            capabilities.extend(['care_episode_management', 'treatment_tracking'])
        if 'benefit' in text_lower or 'coverage' in text_lower:
            capabilities.extend(['benefit_determination', 'coverage_analysis'])
        if 'medication' in text_lower or 'pharmacy' in text_lower:
            capabilities.extend(['medication_analysis', 'pharmacy_review'])
        if 'guideline' in text_lower:
            capabilities.extend(['clinical_guideline_check', 'medical_compliance'])

        # Add general healthcare processing if it's a healthcare agent
        if any(word in text_lower for word in ['medical', 'clinical', 'healthcare', 'patient']):
            capabilities.append('healthcare_processing')

        return list(set(capabilities))

    def _infer_agent_input_types(self, agent_spec: Any, capabilities: List[str]) -> List[str]:
        """Infer input data types for agents"""
        input_types = ['text', 'json']  # Base types

        if any(cap in capabilities for cap in [
            'clinical_summarization', 'medical_data_extraction', 'clinical_validation',
            'medical_content_analysis', 'clinical_data_processing', 'healthcare_processing'
        ]):
            input_types.extend(['structured_data'])

        return list(set(input_types))

    def _infer_agent_output_types(self, agent_spec: Any, capabilities: List[str]) -> List[str]:
        """Infer output data types for agents"""
        output_types = ['text', 'json']  # Base types

        if any(cap in capabilities for cap in ['clinical_summarization', 'medical_content_analysis']):
            output_types.extend(['structured_data', 'clinical_report'])

        if any(cap in capabilities for cap in ['medical_data_extraction', 'clinical_validation']):
            output_types.extend(['structured_data', 'agent_response'])

        if any(cap in capabilities for cap in ['content_generation', 'clinical_workflow']):
            output_types.extend(['structured_data'])

        return list(set(output_types))
