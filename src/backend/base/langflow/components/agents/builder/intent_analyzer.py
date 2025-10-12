"""Intent Analyzer Component

Analyzes user messages to understand agent building intent and extract requirements.
Uses LLM-based classification to identify what type of agent the user wants to build.
"""

import json
from typing import Any, Dict, List

from langflow.base.langchain_utilities.model import LCModelComponent
from langflow.custom.custom_component.component import Component
from langflow.field_typing import Data, Text
from langflow.inputs.inputs import MessageTextInput, DictInput, DropdownInput, IntInput
from langflow.schema.data import Data as DataType
from langflow.schema.message import Message
from langflow.template.field.base import Output


class IntentAnalyzerComponent(Component):
    display_name = "Intent Analyzer"
    description = "Analyzes user messages to understand agent building intent and extract requirements"
    documentation = "Specialized component for understanding user intent in agent building conversations"
    icon = "brain"
    name = "IntentAnalyzer"

    inputs = [
        MessageTextInput(
            name="user_message",
            display_name="User Message",
            info="The user's message describing their agent requirements",
            required=True,
        ),
        DictInput(
            name="conversation_history",
            display_name="Conversation History",
            info="Previous messages in the conversation for context",
            required=False,
        ),
        DropdownInput(
            name="analysis_mode",
            display_name="Analysis Mode",
            options=["initial", "clarification", "refinement"],
            value="initial",
            info="Mode of analysis based on conversation stage",
        ),
        IntInput(
            name="confidence_threshold",
            display_name="Confidence Threshold",
            value=80,
            info="Minimum confidence percentage to proceed without clarification",
            range_spec={"min": 1, "max": 100},
        ),
    ]

    outputs = [
        Output(display_name="Intent Analysis", name="intent_analysis", method="analyze_intent"),
        Output(display_name="Requirements Extracted", name="requirements", method="extract_requirements"),
        Output(display_name="Missing Information", name="missing_info", method="identify_missing_info"),
        Output(display_name="Clarifying Questions", name="questions", method="generate_questions"),
        Output(display_name="Confidence Score", name="confidence", method="get_confidence"),
    ]

    def analyze_intent(self) -> DataType:
        """Analyze the user's intent for agent building"""

        analysis_prompt = self._build_analysis_prompt()

        # Create mock LLM response for demonstration
        # In production, this would call an actual LLM
        intent_analysis = {
            "primary_intent": self._classify_primary_intent(),
            "agent_type": self._determine_agent_type(),
            "domain": self._identify_domain(),
            "complexity_level": self._assess_complexity(),
            "use_case_category": self._categorize_use_case(),
            "confidence_score": self._calculate_confidence(),
        }

        return DataType(value=intent_analysis)

    def extract_requirements(self) -> DataType:
        """Extract explicit and implicit requirements from user message"""

        requirements = {
            "explicit_requirements": self._extract_explicit_requirements(),
            "implicit_requirements": self._infer_implicit_requirements(),
            "functional_requirements": self._identify_functional_requirements(),
            "non_functional_requirements": self._identify_non_functional_requirements(),
            "integration_requirements": self._identify_integration_requirements(),
            "data_requirements": self._identify_data_requirements(),
        }

        return DataType(value=requirements)

    def identify_missing_info(self) -> DataType:
        """Identify what information is missing for complete requirements"""

        missing_info = self._analyze_missing_information()

        return DataType(value={
            "missing_categories": missing_info,
            "critical_missing": [item for item in missing_info if item.get("priority") == "critical"],
            "optional_missing": [item for item in missing_info if item.get("priority") == "optional"],
        })

    def generate_questions(self) -> DataType:
        """Generate clarifying questions based on missing information"""

        questions = self._generate_clarifying_questions()

        return DataType(value={
            "questions": questions,
            "question_categories": self._categorize_questions(questions),
            "suggested_order": self._prioritize_questions(questions),
        })

    def get_confidence(self) -> DataType:
        """Get confidence score for the analysis"""

        confidence_score = self._calculate_confidence()

        return DataType(value={
            "overall_confidence": confidence_score,
            "confidence_breakdown": self._get_confidence_breakdown(),
            "ready_to_proceed": confidence_score >= self.confidence_threshold,
            "needs_clarification": confidence_score < self.confidence_threshold,
        })

    def _build_analysis_prompt(self) -> str:
        """Build the LLM prompt for intent analysis"""

        history_context = ""
        if self.conversation_history:
            history_context = f"\nConversation History: {json.dumps(self.conversation_history, indent=2)}"

        return f"""
You are an expert AI agent builder analyst. Analyze this user message to understand their intent for building an AI agent.

User Message: "{self.user_message}"
Analysis Mode: {self.analysis_mode}
{history_context}

Analyze and extract:

1. PRIMARY INTENT:
   - create_new_agent
   - modify_existing_agent
   - ask_questions
   - request_examples
   - seek_guidance

2. AGENT TYPE:
   - single_agent (one agent handles everything)
   - multi_agent (multiple coordinated agents)
   - workflow_agent (complex multi-step process)
   - specialized_agent (domain-specific functionality)

3. DOMAIN:
   - healthcare
   - finance
   - automation
   - customer_service
   - data_processing
   - other

4. COMPLEXITY LEVEL:
   - simple (3-4 components)
   - intermediate (5-7 components)
   - advanced (8+ components)
   - enterprise (complex integrations)

5. USE CASE CATEGORY:
   - prior_authorization
   - clinical_decision_support
   - patient_communication
   - data_analysis
   - workflow_automation
   - compliance_monitoring
   - other

Extract all requirements, identify missing information, and generate clarifying questions.
Focus on healthcare workflows and API-based patterns.
"""

    def _classify_primary_intent(self) -> str:
        """Classify the primary intent from user message"""

        message_lower = self.user_message.lower()

        if any(word in message_lower for word in ["create", "build", "make", "develop"]):
            return "create_new_agent"
        elif any(word in message_lower for word in ["modify", "change", "update", "edit"]):
            return "modify_existing_agent"
        elif any(word in message_lower for word in ["how", "what", "when", "why", "?"]):
            return "ask_questions"
        elif any(word in message_lower for word in ["example", "sample", "demo", "show"]):
            return "request_examples"
        else:
            return "seek_guidance"

    def _determine_agent_type(self) -> str:
        """Determine the type of agent needed"""

        message_lower = self.user_message.lower()

        if any(word in message_lower for word in ["workflow", "multi-step", "complex", "pipeline"]):
            return "workflow_agent"
        elif any(word in message_lower for word in ["multiple", "team", "coordinate", "collaborate"]):
            return "multi_agent"
        elif any(word in message_lower for word in ["specialized", "specific", "domain", "expert"]):
            return "specialized_agent"
        else:
            return "single_agent"

    def _identify_domain(self) -> str:
        """Identify the domain from user message"""

        message_lower = self.user_message.lower()

        healthcare_keywords = ["healthcare", "medical", "clinical", "patient", "doctor", "hospital", "ehr", "prior auth", "insurance"]
        finance_keywords = ["finance", "financial", "banking", "trading", "investment", "loan", "credit"]

        if any(keyword in message_lower for keyword in healthcare_keywords):
            return "healthcare"
        elif any(keyword in message_lower for keyword in finance_keywords):
            return "finance"
        else:
            return "general"

    def _assess_complexity(self) -> str:
        """Assess complexity level based on requirements"""

        message_lower = self.user_message.lower()
        complexity_indicators = 0

        # Count complexity indicators
        if any(word in message_lower for word in ["integration", "api", "database", "external"]):
            complexity_indicators += 1
        if any(word in message_lower for word in ["multiple", "various", "different", "several"]):
            complexity_indicators += 1
        if any(word in message_lower for word in ["workflow", "process", "pipeline", "automation"]):
            complexity_indicators += 1
        if any(word in message_lower for word in ["compliance", "security", "hipaa", "regulations"]):
            complexity_indicators += 1

        if complexity_indicators >= 3:
            return "advanced"
        elif complexity_indicators >= 2:
            return "intermediate"
        else:
            return "simple"

    def _categorize_use_case(self) -> str:
        """Categorize the specific use case"""

        message_lower = self.user_message.lower()

        use_case_patterns = {
            "prior_authorization": ["prior auth", "authorization", "approval", "preauth"],
            "clinical_decision_support": ["clinical decision", "recommendations", "guidelines", "protocols"],
            "patient_communication": ["patient", "communication", "messaging", "notification"],
            "data_analysis": ["analyze", "analysis", "insights", "reports", "dashboard"],
            "workflow_automation": ["automate", "workflow", "process", "streamline"],
            "compliance_monitoring": ["compliance", "audit", "monitoring", "tracking"],
        }

        for use_case, keywords in use_case_patterns.items():
            if any(keyword in message_lower for keyword in keywords):
                return use_case

        return "general"

    def _calculate_confidence(self) -> int:
        """Calculate confidence score for the analysis"""

        confidence = 60  # Base confidence

        # Increase confidence based on clear indicators
        message_lower = self.user_message.lower()

        if len(self.user_message.split()) > 10:  # Detailed message
            confidence += 15

        if any(word in message_lower for word in ["create", "build", "agent"]):  # Clear intent
            confidence += 10

        if self._identify_domain() != "general":  # Clear domain
            confidence += 10

        if any(word in message_lower for word in ["api", "integration", "system"]):  # Technical details
            confidence += 5

        return min(confidence, 100)

    def _extract_explicit_requirements(self) -> List[Dict[str, Any]]:
        """Extract explicitly stated requirements"""

        explicit_reqs = []
        message_lower = self.user_message.lower()

        # Look for explicit requirement patterns
        if "api" in message_lower:
            explicit_reqs.append({"type": "integration", "requirement": "API integration", "source": "explicit"})

        if any(word in message_lower for word in ["database", "data"]):
            explicit_reqs.append({"type": "data", "requirement": "Data processing", "source": "explicit"})

        if any(word in message_lower for word in ["email", "sms", "notification"]):
            explicit_reqs.append({"type": "communication", "requirement": "Messaging capability", "source": "explicit"})

        return explicit_reqs

    def _infer_implicit_requirements(self) -> List[Dict[str, Any]]:
        """Infer implicit requirements based on context"""

        implicit_reqs = []

        # Healthcare domain implies HIPAA compliance
        if self._identify_domain() == "healthcare":
            implicit_reqs.extend([
                {"type": "compliance", "requirement": "HIPAA compliance", "source": "inferred"},
                {"type": "security", "requirement": "PHI encryption", "source": "inferred"},
                {"type": "audit", "requirement": "Audit logging", "source": "inferred"},
            ])

        # API mentions imply authentication
        if "api" in self.user_message.lower():
            implicit_reqs.append({"type": "security", "requirement": "API authentication", "source": "inferred"})

        return implicit_reqs

    def _identify_functional_requirements(self) -> List[str]:
        """Identify functional requirements"""

        functional_reqs = []
        message_lower = self.user_message.lower()

        if any(word in message_lower for word in ["process", "handle", "manage"]):
            functional_reqs.append("Data processing capability")

        if any(word in message_lower for word in ["send", "notify", "communicate"]):
            functional_reqs.append("Communication functionality")

        if any(word in message_lower for word in ["analyze", "evaluate", "assess"]):
            functional_reqs.append("Analysis and evaluation")

        return functional_reqs

    def _identify_non_functional_requirements(self) -> List[str]:
        """Identify non-functional requirements"""

        non_functional_reqs = []

        # Default non-functional requirements for healthcare
        if self._identify_domain() == "healthcare":
            non_functional_reqs.extend([
                "99.9% availability",
                "Sub-5 second response time",
                "HIPAA compliance",
                "Data encryption at rest and in transit",
            ])

        return non_functional_reqs

    def _identify_integration_requirements(self) -> List[str]:
        """Identify integration requirements"""

        integration_reqs = []
        message_lower = self.user_message.lower()

        if any(word in message_lower for word in ["ehr", "epic", "cerner"]):
            integration_reqs.append("EHR system integration")

        if any(word in message_lower for word in ["insurance", "payer", "eligibility"]):
            integration_reqs.append("Insurance verification API")

        if any(word in message_lower for word in ["email", "sms"]):
            integration_reqs.append("Communication service integration")

        return integration_reqs

    def _identify_data_requirements(self) -> List[str]:
        """Identify data requirements"""

        data_reqs = []

        if self._identify_domain() == "healthcare":
            data_reqs.extend([
                "Patient demographic data",
                "Clinical data (if applicable)",
                "Insurance information",
                "Provider information",
            ])

        return data_reqs

    def _analyze_missing_information(self) -> List[Dict[str, Any]]:
        """Analyze what information is missing"""

        missing_info = []

        # Check for missing critical information
        if not any(word in self.user_message.lower() for word in ["input", "data", "receive"]):
            missing_info.append({
                "category": "input_specification",
                "description": "How will data be provided to the agent?",
                "priority": "critical"
            })

        if not any(word in self.user_message.lower() for word in ["output", "return", "response"]):
            missing_info.append({
                "category": "output_specification",
                "description": "What should the agent return or provide?",
                "priority": "critical"
            })

        if not any(word in self.user_message.lower() for word in ["api", "trigger", "call", "invoke"]):
            missing_info.append({
                "category": "invocation_method",
                "description": "How will the agent be triggered or called?",
                "priority": "critical"
            })

        return missing_info

    def _generate_clarifying_questions(self) -> List[Dict[str, Any]]:
        """Generate clarifying questions based on missing information"""

        questions = []

        # Questions based on intent and domain
        if self._classify_primary_intent() == "create_new_agent":
            questions.extend([
                {
                    "question": "What specific task should this agent accomplish?",
                    "category": "functionality",
                    "priority": "high"
                },
                {
                    "question": "What data will be provided as input to the agent?",
                    "category": "input",
                    "priority": "high"
                },
                {
                    "question": "What should the agent return or output?",
                    "category": "output",
                    "priority": "high"
                },
            ])

        if self._identify_domain() == "healthcare":
            questions.extend([
                {
                    "question": "Which healthcare systems need integration (EHR, payer portals, etc.)?",
                    "category": "integration",
                    "priority": "medium"
                },
                {
                    "question": "Are there specific compliance requirements beyond HIPAA?",
                    "category": "compliance",
                    "priority": "medium"
                },
            ])

        return questions

    def _categorize_questions(self, questions: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """Categorize questions by type"""

        categories = {}
        for question in questions:
            category = question.get("category", "general")
            if category not in categories:
                categories[category] = []
            categories[category].append(question["question"])

        return categories

    def _prioritize_questions(self, questions: List[Dict[str, Any]]) -> List[str]:
        """Prioritize questions by importance"""

        priority_order = {"high": 1, "medium": 2, "low": 3}

        sorted_questions = sorted(
            questions,
            key=lambda q: priority_order.get(q.get("priority", "low"), 3)
        )

        return [q["question"] for q in sorted_questions]

    def _get_confidence_breakdown(self) -> Dict[str, int]:
        """Get breakdown of confidence by category"""

        return {
            "intent_clarity": 85,
            "domain_identification": 90,
            "requirement_completeness": 60,
            "technical_specificity": 70,
            "overall": self._calculate_confidence(),
        }