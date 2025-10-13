"""
LLM Service for Agent Builder

Integrates with AI Gateway for healthcare-focused LLM operations.
Adapted for async streaming context.
"""

import logging
from typing import Dict, Any, Optional
import asyncio

from langflow.custom.genesis.services.ai_gateway.service import AIGatewayService

from .settings import AgentBuilderSettings


class LLMService:
    """Healthcare-focused LLM service using AI Gateway"""

    def __init__(self, settings: AgentBuilderSettings):
        self.logger = logging.getLogger(__name__)
        self.settings = settings

        # AI Gateway service will be initialized when needed
        self._ai_gateway = None

    async def _get_ai_gateway(self) -> AIGatewayService:
        """Get or create AI Gateway service instance"""
        if self._ai_gateway is None:
            # Import here to avoid circular imports
            from langflow.custom.genesis.services.deps import get_ai_gateway_service
            self._ai_gateway = get_ai_gateway_service()
        return self._ai_gateway

    async def analyze_healthcare_task(self, user_request: str) -> Dict[str, Any]:
        """
        Analyze healthcare task using LLM for task decomposition

        Args:
            user_request: Natural language healthcare request

        Returns:
            Task analysis with primary_task, domain, input/output requirements
        """
        try:
            ai_gateway = await self._get_ai_gateway()

            prompt = f"""
Analyze this healthcare request for creating an AI agent: "{user_request}"

Consider healthcare context:
- Clinical workflows (patient intake, assessment, diagnosis, treatment, follow-up)
- Regulatory requirements (HIPAA, patient privacy, clinical safety)
- Medical data types (PHI, clinical notes, lab results, imaging reports)
- Interoperability standards (FHIR, HL7, CDA)
- Patient safety and clinical decision support

Identify the core elements:
1. PRIMARY_TASK: What is the main functionality needed?
2. DOMAIN: Is this healthcare, technical, general, or specialized?
3. INPUT_REQUIREMENTS: What type of data does the agent need to process?
4. OUTPUT_EXPECTATIONS: What should the agent produce?
5. SPECIALIZED_CAPABILITIES: Any specific processing requirements?

Provide a structured analysis with concrete requirements.
"""

            # Use asyncio.to_thread to make the sync AI Gateway call async
            response = await asyncio.to_thread(
                ai_gateway.chat_completion,
                model_name=self.settings.LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                api_key=self.settings.AI_GATEWAY_VIRTUAL_KEY
            )

            # Parse the response (simplified parsing)
            return self._parse_task_analysis(response)

        except Exception as e:
            self.logger.error(f"Error in healthcare task analysis: {e}")
            # Return basic fallback analysis
            return {
                "primary_task": "general_processing",
                "domain": "healthcare",
                "input_requirements": ["text"],
                "output_expectations": ["text"],
                "specialized_capabilities": ["healthcare_processing"],
                "confidence_score": 0.5
            }

    def _parse_task_analysis(self, response) -> Dict[str, Any]:
        """
        Parse LLM response into structured task analysis

        Args:
            response: Raw LLM response (string or dict from AI Gateway)

        Returns:
            Structured task analysis
        """
        try:
            # Handle AI Gateway dict response
            if isinstance(response, dict):
                # Extract content from AI Gateway response format
                content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
                response_text = content
            else:
                # Handle string response (fallback)
                response_text = response

            # Parse the extracted text
            analysis = {
                "primary_task": self._extract_primary_task(response_text),
                "domain": "healthcare",  # Default for healthcare context
                "input_requirements": self._extract_input_requirements(response_text),
                "output_expectations": self._extract_output_expectations(response_text),
                "specialized_capabilities": self._extract_capabilities(response_text),
                "confidence_score": 0.8
            }
            return analysis

        except Exception as e:
            self.logger.error(f"Error parsing task analysis: {e}")
            return self._get_fallback_analysis()

    def _extract_primary_task(self, response: str) -> str:
        """Extract primary task from LLM response"""
        response_lower = response.lower()
        if "summariz" in response_lower:
            return "summarization"
        elif "extract" in response_lower:
            return "extraction"
        elif "classif" in response_lower:
            return "classification"
        elif "analyz" in response_lower:
            return "analysis"
        else:
            return "general_processing"

    def _extract_input_requirements(self, response: str) -> list:
        """Extract input requirements from response"""
        requirements = []
        response_lower = response.lower()

        if "text" in response_lower or "document" in response_lower:
            requirements.append("text")
        if "json" in response_lower or "structured" in response_lower:
            requirements.append("json")
        if "clinical" in response_lower or "medical" in response_lower:
            requirements.append("clinical_data")

        return requirements or ["text"]  # Default

    def _extract_output_expectations(self, response: str) -> list:
        """Extract output expectations from response"""
        expectations = []
        response_lower = response.lower()

        if "summary" in response_lower:
            expectations.append("summary")
        if "report" in response_lower:
            expectations.append("clinical_report")
        if "json" in response_lower:
            expectations.append("structured_data")

        return expectations or ["text"]  # Default

    def _extract_capabilities(self, response: str) -> list:
        """Extract specialized capabilities from response"""
        capabilities = ["healthcare_processing"]  # Base capability
        response_lower = response.lower()

        if "summariz" in response_lower:
            capabilities.append("clinical_summarization")
        if "extract" in response_lower:
            capabilities.append("medical_data_extraction")
        if "nlp" in response_lower or "natural language" in response_lower:
            capabilities.append("medical_nlp")

        return capabilities

    def _get_fallback_analysis(self) -> Dict[str, Any]:
        """Get fallback task analysis when parsing fails"""
        return {
            "primary_task": "general_processing",
            "domain": "healthcare",
            "input_requirements": ["text"],
            "output_expectations": ["text"],
            "specialized_capabilities": ["healthcare_processing"],
            "confidence_score": 0.3
        }
