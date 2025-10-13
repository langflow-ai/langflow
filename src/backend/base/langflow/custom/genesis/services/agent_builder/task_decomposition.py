"""
Task Decomposition Engine for Agent Builder

Breaks down user requests into implementable subtasks with healthcare focus.
Adapted from Genesis TaskDecompositionEngine for service context.
"""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from .llm_service import LLMService
from .kb_loader import KnowledgeBaseLoader


@dataclass
class Subtask:
    """Individual subtask specification"""
    subtask_id: str
    name: str
    description: str
    required_capabilities: List[str]
    data_types: List[str]
    component_category: str
    priority: int  # 1-5, higher = more critical


@dataclass
class TaskAnalysis:
    """Complete task analysis result"""
    original_request: str
    primary_task: str
    domain: str
    input_requirements: List[str]
    output_expectations: List[str]
    specialized_capabilities: List[str]
    subtasks: List[Subtask]
    complexity_score: int
    confidence_score: float
    analysis_timestamp: str


class TaskDecompositionEngine:
    """Engine for decomposing user requests into implementable subtasks"""

    def __init__(self, kb_loader: KnowledgeBaseLoader, llm_service: LLMService):
        self.logger = logging.getLogger(__name__)
        self.kb_loader = kb_loader
        self.llm_service = llm_service

        # Initialize task patterns for rule-based decomposition
        self._init_task_patterns()

    def _init_task_patterns(self):
        """Initialize patterns for different task types"""
        self.task_patterns = {
            'summarization': {
                'keywords': ['summarize', 'summary', 'summarization', 'abstract', 'condense'],
                'capabilities': ['text_processing', 'summarization'],
                'data_types': ['text', 'document'],
                'subtasks': ['input_processing', 'content_analysis', 'summarization', 'output_formatting']
            },
            'extraction': {
                'keywords': ['extract', 'extraction', 'parse', 'identify', 'find'],
                'capabilities': ['data_extraction', 'pattern_matching'],
                'data_types': ['text', 'structured_data'],
                'subtasks': ['input_processing', 'extraction', 'validation', 'output_formatting']
            },
            'classification': {
                'keywords': ['classify', 'classification', 'categorize', 'sort', 'group'],
                'capabilities': ['classification', 'categorization'],
                'data_types': ['text', 'unstructured_data'],
                'subtasks': ['input_processing', 'classification', 'validation', 'output_formatting']
            },
            'analysis': {
                'keywords': ['analyze', 'analysis', 'evaluate', 'assess', 'review'],
                'capabilities': ['analysis', 'evaluation'],
                'data_types': ['text', 'structured_data'],
                'subtasks': ['input_processing', 'analysis', 'insights', 'output_formatting']
            }
        }

    async def decompose_task(self, user_request: str) -> TaskAnalysis:
        """
        Decompose user request into structured subtasks

        Args:
            user_request: Natural language request

        Returns:
            Complete task analysis with subtasks
        """
        try:
            self.logger.info(f"Decomposing task: {user_request[:100]}...")

            # Get LLM-powered task analysis
            llm_analysis = await self.llm_service.analyze_healthcare_task(user_request)

            # Generate subtasks based on analysis
            subtasks = self._generate_subtasks(llm_analysis, user_request)

            # Calculate complexity
            complexity_score = self._calculate_complexity(subtasks)

            task_analysis = TaskAnalysis(
                original_request=user_request,
                primary_task=llm_analysis.get("primary_task", "general_processing"),
                domain=llm_analysis.get("domain", "healthcare"),
                input_requirements=llm_analysis.get("input_requirements", ["text"]),
                output_expectations=llm_analysis.get("output_expectations", ["text"]),
                specialized_capabilities=llm_analysis.get("specialized_capabilities", []),
                subtasks=subtasks,
                complexity_score=complexity_score,
                confidence_score=llm_analysis.get("confidence_score", 0.8),
                analysis_timestamp=datetime.now().isoformat()
            )

            self.logger.info(f"Task decomposed into {len(subtasks)} subtasks")
            return task_analysis

        except Exception as e:
            self.logger.error(f"Error decomposing task: {e}")
            # Return basic fallback
            return self._create_fallback_analysis(user_request)

    def _generate_subtasks(self, llm_analysis: Dict[str, Any], user_request: str) -> List[Subtask]:
        """Generate subtasks based on LLM analysis"""
        primary_task = llm_analysis.get("primary_task", "general_processing")

        # Get pattern for primary task
        pattern = self.task_patterns.get(primary_task, self.task_patterns['analysis'])

        subtasks = []
        for i, subtask_name in enumerate(pattern['subtasks']):
            subtask = Subtask(
                subtask_id=f"subtask_{i+1}",
                name=subtask_name.replace('_', ' ').title(),
                description=self._generate_subtask_description(subtask_name, user_request),
                required_capabilities=pattern['capabilities'],
                data_types=pattern['data_types'],
                component_category=self._map_subtask_to_category(subtask_name),
                priority=5 - i  # Higher priority for earlier subtasks
            )
            subtasks.append(subtask)

        return subtasks

    def _generate_subtask_description(self, subtask_name: str, user_request: str) -> str:
        """Generate human-readable description for subtask"""
        descriptions = {
            'input_processing': f"Handle and validate input data for: {user_request[:50]}...",
            'content_analysis': f"Analyze and understand content structure for: {user_request[:50]}...",
            'summarization': f"Generate concise summary of processed content",
            'extraction': f"Extract key information and entities from content",
            'classification': f"Classify and categorize processed information",
            'analysis': f"Perform detailed analysis on processed data",
            'validation': f"Validate extracted information and results",
            'output_formatting': f"Format and present final results"
        }
        return descriptions.get(subtask_name, f"Process {subtask_name} for the given request")

    def _map_subtask_to_category(self, subtask_name: str) -> str:
        """Map subtask to component category"""
        category_map = {
            'input_processing': 'input',
            'content_analysis': 'processing',
            'summarization': 'processing',
            'extraction': 'processing',
            'classification': 'processing',
            'analysis': 'processing',
            'validation': 'processing',
            'output_formatting': 'output'
        }
        return category_map.get(subtask_name, 'processing')

    def _calculate_complexity(self, subtasks: List[Subtask]) -> int:
        """Calculate task complexity score"""
        base_complexity = len(subtasks)
        capability_complexity = len(set(cap for subtask in subtasks for cap in subtask.required_capabilities))
        return min(5, base_complexity + capability_complexity // 2)

    def _create_fallback_analysis(self, user_request: str) -> TaskAnalysis:
        """Create fallback task analysis when LLM fails"""
        # Basic subtask generation
        basic_subtasks = [
            Subtask(
                subtask_id="input_1",
                name="Input Processing",
                description=f"Handle input data for: {user_request[:50]}...",
                required_capabilities=["data_input"],
                data_types=["text"],
                component_category="input",
                priority=5
            ),
            Subtask(
                subtask_id="processing_1",
                name="Content Processing",
                description="Process and analyze content",
                required_capabilities=["content_processing"],
                data_types=["text"],
                component_category="processing",
                priority=4
            ),
            Subtask(
                subtask_id="output_1",
                name="Output Generation",
                description="Generate final output",
                required_capabilities=["content_generation"],
                data_types=["text"],
                component_category="output",
                priority=3
            )
        ]

        return TaskAnalysis(
            original_request=user_request,
            primary_task="general_processing",
            domain="healthcare",
            input_requirements=["text"],
            output_expectations=["text"],
            specialized_capabilities=["healthcare_processing"],
            subtasks=basic_subtasks,
            complexity_score=3,
            confidence_score=0.5,
            analysis_timestamp=datetime.now().isoformat()
        )
