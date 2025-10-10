"""
Agent Builder Service - Main Orchestrator

Provides streaming agent generation using Genesis pipeline with Azure Search integration.
"""

import asyncio
import logging
from typing import AsyncGenerator, Dict, Any
from datetime import datetime

from langflow.services.base import Service
from langflow.api.v1.schemas import StreamData

from .settings import AgentBuilderSettings
from .kb_loader import KnowledgeBaseLoader
from .llm_service import LLMService
from .task_decomposition import TaskDecompositionEngine, TaskAnalysis
from .semantic_search import SemanticSearchEngine, ComponentMatch
from .component_assembly import ComponentAssemblyEngine, AssemblyResult
from .yaml_generation import YAMLGenerationEngine


class AgentBuilderService(Service):
    """Main Agent Builder service with streaming orchestration"""

    name = "agent_builder_service"

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)

        # Initialize settings
        self.settings = AgentBuilderSettings()

        # Initialize components (lazy loading)
        self._kb_loader = None
        self._llm_service = None
        self._task_engine = None
        self._search_engine = None
        self._assembly_engine = None
        self._yaml_engine = None

        self._ready = False

    def set_ready(self) -> None:
        """Set the service as ready"""
        if not self.settings.is_configured():
            raise ValueError("Agent Builder settings are not properly configured")
        self._ready = True

    @property
    def ready(self) -> bool:
        """Check if the service is ready"""
        return self._ready

    def _get_kb_loader(self) -> KnowledgeBaseLoader:
        """Get or create KB loader"""
        if self._kb_loader is None:
            self._kb_loader = KnowledgeBaseLoader(self.settings)
        return self._kb_loader

    def _get_llm_service(self) -> LLMService:
        """Get or create LLM service"""
        if self._llm_service is None:
            self._llm_service = LLMService(self.settings)
        return self._llm_service

    def _get_task_engine(self) -> TaskDecompositionEngine:
        """Get or create task decomposition engine"""
        if self._task_engine is None:
            kb_loader = self._get_kb_loader()
            llm_service = self._get_llm_service()
            self._task_engine = TaskDecompositionEngine(kb_loader, llm_service)
        return self._task_engine

    def _get_search_engine(self) -> SemanticSearchEngine:
        """Get or create semantic search engine"""
        if self._search_engine is None:
            kb_loader = self._get_kb_loader()
            self._search_engine = SemanticSearchEngine(kb_loader, self.settings)
        return self._search_engine

    def _get_assembly_engine(self) -> ComponentAssemblyEngine:
        """Get or create component assembly engine"""
        if self._assembly_engine is None:
            kb_loader = self._get_kb_loader()
            self._assembly_engine = ComponentAssemblyEngine(kb_loader)
        return self._assembly_engine

    def _get_yaml_engine(self) -> YAMLGenerationEngine:
        """Get or create YAML generation engine"""
        if self._yaml_engine is None:
            self._yaml_engine = YAMLGenerationEngine()
        return self._yaml_engine

    async def build_streaming(self, user_request: str) -> AsyncGenerator[StreamData, None]:
        """
        Build an agent with streaming progress updates

        Args:
            user_request: Natural language request for agent creation

        Yields:
            StreamData events for each phase of agent building
        """
        try:
            self.logger.info(f"Starting agent build for: {user_request[:100]}...")

            # Phase 1: Task Decomposition
            yield StreamData(event="thinking", data={
                "phase": "task_decomposition",
                "message": f"Analyzing request: '{user_request[:50]}...'",
                "progress": "20%"
            })

            task_engine = self._get_task_engine()
            task_analysis = await task_engine.decompose_task(user_request)

            yield StreamData(event="thinking", data={
                "phase": "task_decomposition",
                "message": f"Identified {task_analysis.primary_task} task in {task_analysis.domain} domain",
                "details": {
                    "primary_task": task_analysis.primary_task,
                    "domain": task_analysis.domain,
                    "subtasks": len(task_analysis.subtasks),
                    "complexity": task_analysis.complexity_score
                },
                "progress": "30%"
            })

            await asyncio.sleep(0.5)  # Streaming delay

            # Phase 2: Semantic Component Search
            yield StreamData(event="thinking", data={
                "phase": "component_search",
                "message": f"Searching knowledge base for {task_analysis.primary_task} components...",
                "progress": "40%"
            })

            search_engine = self._get_search_engine()
            component_matches = []

            # Search for each subtask
            for i, subtask in enumerate(task_analysis.subtasks):
                yield StreamData(event="thinking", data={
                    "phase": "component_search",
                    "message": f"Searching for subtask {i+1}/{len(task_analysis.subtasks)}: {subtask.name}",
                    "progress": f"{40 + (i * 10)}%"
                })

                # Search for components matching this subtask
                matches = await search_engine.search_components(
                    subtask_query=subtask.description,
                    required_capabilities=subtask.required_capabilities,
                    data_types=subtask.data_types,
                    component_category=subtask.component_category,
                    top_k=3
                )

                if matches:
                    # Take the best match for this subtask
                    best_match = matches[0]
                    component_matches.append(best_match)

                    yield StreamData(event="thinking", data={
                        "phase": "component_search",
                        "message": f"Found: {best_match.component_spec.name}",
                        "details": {
                            "component": best_match.component_spec.name,
                            "capabilities": best_match.component_spec.capabilities[:3],
                            "score": round(best_match.overall_score, 2)
                        }
                    })

                await asyncio.sleep(0.2)

            yield StreamData(event="thinking", data={
                "phase": "component_search",
                "message": f"Found {len(component_matches)} components for agent assembly",
                "progress": "70%"
            })

            await asyncio.sleep(0.3)

            # Phase 3: Component Assembly & Validation
            yield StreamData(event="thinking", data={
                "phase": "chain_validation",
                "message": "Validating component compatibility and healthcare compliance...",
                "progress": "80%"
            })

            assembly_engine = self._get_assembly_engine()
            assembly_result = assembly_engine.assemble_chain(component_matches)

            yield StreamData(event="thinking", data={
                "phase": "chain_validation",
                "message": f"Assembly {'successful' if assembly_result.validation_passed else 'completed with warnings'}",
                "details": {
                    "compatibility_score": round(assembly_result.compatibility_score, 2),
                    "healthcare_compliant": assembly_result.healthcare_compliant,
                    "components": len(assembly_result.components)
                },
                "progress": "90%"
            })

            await asyncio.sleep(0.4)

            # Phase 4: YAML Generation
            yield StreamData(event="thinking", data={
                "phase": "yaml_generation",
                "message": "Generating production-ready agent YAML...",
                "progress": "95%"
            })

            yaml_engine = self._get_yaml_engine()
            yaml_content = yaml_engine.generate_agent_yaml(
                task_analysis, assembly_result, user_request
            )

            await asyncio.sleep(0.3)

            # Phase 5: Complete
            yield StreamData(event="complete", data={
                "workflow": {
                    "yaml_config": yaml_content,
                    "metadata": {
                        "generated_at": datetime.now().isoformat(),
                        "optimization_score": round(assembly_result.compatibility_score, 2),
                        "component_count": len(assembly_result.components),
                        "domain": task_analysis.domain,
                        "primary_task": task_analysis.primary_task
                    },
                    "components": [
                        {
                            "name": comp.component_spec.name,
                            "type": comp.component_spec.component_type,
                            "capabilities": comp.component_spec.capabilities
                        }
                        for comp in assembly_result.components
                    ]
                },
                "agents_count": 1,  # Single generated agent
                "reasoning": f"Generated {task_analysis.domain} agent for {task_analysis.primary_task} "
                           f"using {len(assembly_result.components)} optimized components"
            })

            self.logger.info("Agent build completed successfully")

        except Exception as e:
            self.logger.exception(f"Error in agent builder streaming: {e}")
            yield StreamData(
                event="error",
                data={
                    "error": str(e),
                    "message": "Failed to build agent. Please try again."
                }
            )
