"""Requirements Gatherer Component

Systematically collects and validates agent requirements through conversation.
Ensures all necessary information is gathered before proceeding to specification building.
"""

import json
from typing import Any, Dict, List, Optional

from langflow.custom.custom_component.component import Component
from langflow.field_typing import Data, Text
from langflow.inputs.inputs import MessageTextInput, DictInput, DropdownInput, BoolInput, IntInput
from langflow.schema.data import Data as DataType
from langflow.schema.message import Message
from langflow.template.field.base import Output


class RequirementsGathererComponent(Component):
    display_name = "Requirements Gatherer"
    description = "Systematically collects and validates agent requirements through conversation"
    documentation = "Ensures complete requirement gathering before agent specification building"
    icon = "clipboard-list"
    name = "RequirementsGatherer"

    inputs = [
        DictInput(
            name="intent_analysis",
            display_name="Intent Analysis",
            info="Analysis from IntentAnalyzerComponent containing user intent and extracted info",
            required=True,
        ),
        MessageTextInput(
            name="user_responses",
            display_name="User Responses",
            info="User's responses to clarifying questions",
            required=False,
        ),
        DictInput(
            name="existing_requirements",
            display_name="Existing Requirements",
            info="Previously gathered requirements to update or validate",
            required=False,
        ),
        DropdownInput(
            name="gathering_mode",
            display_name="Gathering Mode",
            options=["progressive", "validation", "completion"],
            value="progressive",
            info="Mode for requirement gathering process",
        ),
        IntInput(
            name="completeness_threshold",
            display_name="Completeness Threshold",
            value=85,
            info="Minimum completeness percentage to consider requirements sufficient",
            range_spec={"min": 1, "max": 100},
        ),
        BoolInput(
            name="strict_validation",
            display_name="Strict Validation",
            value=True,
            info="Whether to require all critical requirements before proceeding",
        ),
    ]

    outputs = [
        Output(display_name="Complete Requirements", name="requirements", method="gather_requirements"),
        Output(display_name="Readiness Assessment", name="readiness", method="assess_readiness"),
        Output(display_name="Next Questions", name="next_questions", method="get_next_questions"),
        Output(display_name="Validation Results", name="validation", method="validate_requirements"),
        Output(display_name="Requirements Summary", name="summary", method="summarize_requirements"),
    ]

    def gather_requirements(self) -> DataType:
        """Gather and consolidate all requirements"""

        # Start with intent analysis requirements
        base_requirements = self._extract_base_requirements()

        # Add user responses
        updated_requirements = self._incorporate_user_responses(base_requirements)

        # Merge with existing requirements if provided
        if self.existing_requirements:
            updated_requirements = self._merge_requirements(updated_requirements, self.existing_requirements)

        # Validate and structure requirements
        structured_requirements = self._structure_requirements(updated_requirements)

        return DataType(value=structured_requirements)

    def assess_readiness(self) -> DataType:
        """Assess if requirements are complete enough to proceed"""

        requirements = self.gather_requirements().value
        readiness_assessment = self._calculate_readiness(requirements)

        return DataType(value={
            "overall_completeness": readiness_assessment["completeness_score"],
            "ready_to_proceed": readiness_assessment["ready"],
            "critical_missing": readiness_assessment["critical_missing"],
            "optional_missing": readiness_assessment["optional_missing"],
            "category_scores": readiness_assessment["category_scores"],
            "recommendations": readiness_assessment["recommendations"],
        })

    def get_next_questions(self) -> DataType:
        """Generate next set of questions based on current requirements"""

        requirements = self.gather_requirements().value
        readiness = self.assess_readiness().value

        if readiness["ready_to_proceed"]:
            return DataType(value={
                "questions": [],
                "message": "All requirements gathered. Ready to proceed with agent building.",
                "next_stage": "specification_building"
            })

        next_questions = self._generate_next_questions(requirements, readiness)

        return DataType(value={
            "questions": next_questions,
            "question_categories": self._categorize_questions(next_questions),
            "priority_order": self._prioritize_questions(next_questions),
            "estimated_completion": self._estimate_completion_time(next_questions),
        })

    def validate_requirements(self) -> DataType:
        """Validate requirements for consistency and completeness"""

        requirements = self.gather_requirements().value
        validation_results = self._perform_validation(requirements)

        return DataType(value={
            "validation_passed": validation_results["passed"],
            "errors": validation_results["errors"],
            "warnings": validation_results["warnings"],
            "suggestions": validation_results["suggestions"],
            "consistency_check": validation_results["consistency"],
        })

    def summarize_requirements(self) -> DataType:
        """Create human-readable summary of gathered requirements"""

        requirements = self.gather_requirements().value
        summary = self._create_requirements_summary(requirements)

        return DataType(value={
            "executive_summary": summary["executive"],
            "functional_summary": summary["functional"],
            "technical_summary": summary["technical"],
            "compliance_summary": summary["compliance"],
            "integration_summary": summary["integration"],
            "estimated_complexity": summary["complexity"],
        })

    def _extract_base_requirements(self) -> Dict[str, Any]:
        """Extract base requirements from intent analysis"""

        if not self.intent_analysis:
            return {}

        base_requirements = {
            "agent_goal": self._extract_agent_goal(),
            "domain": self.intent_analysis.get("domain", "general"),
            "agent_type": self.intent_analysis.get("agent_type", "single_agent"),
            "complexity_level": self.intent_analysis.get("complexity_level", "simple"),
            "use_case_category": self.intent_analysis.get("use_case_category", "general"),
            "functional_requirements": self.intent_analysis.get("requirements", {}).get("functional_requirements", []),
            "non_functional_requirements": self.intent_analysis.get("requirements", {}).get("non_functional_requirements", []),
            "integration_requirements": self.intent_analysis.get("requirements", {}).get("integration_requirements", []),
            "data_requirements": self.intent_analysis.get("requirements", {}).get("data_requirements", []),
        }

        return base_requirements

    def _extract_agent_goal(self) -> str:
        """Extract the primary goal for the agent"""

        if not self.intent_analysis:
            return "General purpose agent"

        # Look for goal in various places
        if "agent_goal" in self.intent_analysis:
            return self.intent_analysis["agent_goal"]

        # Construct goal from use case and domain
        use_case = self.intent_analysis.get("use_case_category", "general")
        domain = self.intent_analysis.get("domain", "general")

        goal_templates = {
            "prior_authorization": f"Automate prior authorization processing for {domain} workflows",
            "clinical_decision_support": f"Provide clinical decision support for {domain} practitioners",
            "patient_communication": f"Manage patient communication and engagement in {domain}",
            "data_analysis": f"Analyze and process {domain} data for insights and reporting",
            "workflow_automation": f"Automate {domain} workflows and business processes",
            "compliance_monitoring": f"Monitor and ensure {domain} compliance requirements",
        }

        return goal_templates.get(use_case, f"Process {domain} tasks and workflows")

    def _incorporate_user_responses(self, base_requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Incorporate user responses into requirements"""

        if not self.user_responses:
            return base_requirements

        updated_requirements = base_requirements.copy()

        # Parse user responses (this would typically involve NLP)
        user_input = self.user_responses.lower()

        # Update input requirements
        if any(word in user_input for word in ["api", "rest", "endpoint"]):
            updated_requirements.setdefault("input_method", []).append("REST API")

        if any(word in user_input for word in ["batch", "file", "upload"]):
            updated_requirements.setdefault("input_method", []).append("Batch processing")

        # Update integration requirements
        if any(word in user_input for word in ["epic", "cerner", "ehr"]):
            updated_requirements.setdefault("integrations", []).append("EHR system")

        if any(word in user_input for word in ["email", "sms", "notification"]):
            updated_requirements.setdefault("integrations", []).append("Communication services")

        # Update output requirements
        if any(word in user_input for word in ["json", "structured", "data"]):
            updated_requirements.setdefault("output_format", []).append("Structured JSON")

        if any(word in user_input for word in ["pdf", "document", "form"]):
            updated_requirements.setdefault("output_format", []).append("Document generation")

        return updated_requirements

    def _merge_requirements(self, new_requirements: Dict[str, Any], existing_requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Merge new requirements with existing ones"""

        merged = existing_requirements.copy()

        for key, value in new_requirements.items():
            if key in merged:
                if isinstance(value, list) and isinstance(merged[key], list):
                    # Merge lists without duplicates
                    merged[key] = list(set(merged[key] + value))
                elif isinstance(value, dict) and isinstance(merged[key], dict):
                    # Merge dictionaries
                    merged[key].update(value)
                else:
                    # Override with new value
                    merged[key] = value
            else:
                merged[key] = value

        return merged

    def _structure_requirements(self, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Structure requirements into standardized format"""

        structured = {
            "metadata": {
                "agent_goal": requirements.get("agent_goal", ""),
                "domain": requirements.get("domain", "general"),
                "agent_type": requirements.get("agent_type", "single_agent"),
                "complexity_level": requirements.get("complexity_level", "simple"),
                "use_case_category": requirements.get("use_case_category", "general"),
                "estimated_components": self._estimate_component_count(requirements),
            },
            "functional": {
                "primary_functions": requirements.get("functional_requirements", []),
                "input_methods": requirements.get("input_method", ["API"]),
                "output_formats": requirements.get("output_format", ["JSON"]),
                "processing_requirements": requirements.get("processing_requirements", []),
            },
            "technical": {
                "integration_requirements": requirements.get("integrations", []),
                "data_requirements": requirements.get("data_requirements", []),
                "performance_requirements": requirements.get("performance_requirements", []),
                "scalability_requirements": requirements.get("scalability_requirements", []),
            },
            "compliance": {
                "regulatory_requirements": self._identify_regulatory_requirements(requirements),
                "security_requirements": self._identify_security_requirements(requirements),
                "audit_requirements": self._identify_audit_requirements(requirements),
            },
            "runtime": {
                "execution_mode": self._determine_execution_mode(requirements),
                "deployment_target": requirements.get("deployment_target", "kubernetes"),
                "resource_requirements": self._estimate_resources(requirements),
            }
        }

        return structured

    def _calculate_readiness(self, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate readiness score and identify missing requirements"""

        category_scores = {}
        critical_missing = []
        optional_missing = []

        # Assess metadata completeness
        metadata_score = self._assess_category_completeness(requirements.get("metadata", {}), "metadata")
        category_scores["metadata"] = metadata_score

        # Assess functional completeness
        functional_score = self._assess_category_completeness(requirements.get("functional", {}), "functional")
        category_scores["functional"] = functional_score

        # Assess technical completeness
        technical_score = self._assess_category_completeness(requirements.get("technical", {}), "technical")
        category_scores["technical"] = technical_score

        # Assess compliance completeness
        compliance_score = self._assess_category_completeness(requirements.get("compliance", {}), "compliance")
        category_scores["compliance"] = compliance_score

        # Calculate overall completeness
        overall_completeness = sum(category_scores.values()) / len(category_scores)

        # Identify missing critical requirements
        if metadata_score < 80:
            critical_missing.append("Agent goal and type specification")

        if functional_score < 70:
            critical_missing.append("Input/output specification")

        if requirements.get("domain") == "healthcare" and compliance_score < 90:
            critical_missing.append("Healthcare compliance requirements")

        ready = overall_completeness >= self.completeness_threshold and (not self.strict_validation or not critical_missing)

        return {
            "completeness_score": overall_completeness,
            "ready": ready,
            "critical_missing": critical_missing,
            "optional_missing": optional_missing,
            "category_scores": category_scores,
            "recommendations": self._generate_readiness_recommendations(category_scores, critical_missing),
        }

    def _assess_category_completeness(self, category_data: Dict[str, Any], category_name: str) -> float:
        """Assess completeness of a specific category"""

        required_fields = {
            "metadata": ["agent_goal", "domain", "agent_type"],
            "functional": ["primary_functions", "input_methods", "output_formats"],
            "technical": ["integration_requirements"],
            "compliance": ["regulatory_requirements", "security_requirements"],
        }

        if category_name not in required_fields:
            return 100.0

        total_required = len(required_fields[category_name])
        present_count = 0

        for field in required_fields[category_name]:
            if field in category_data and category_data[field]:
                present_count += 1

        return (present_count / total_required) * 100

    def _generate_next_questions(self, requirements: Dict[str, Any], readiness: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate next set of questions based on missing requirements"""

        questions = []

        # Generate questions for critical missing items
        for missing_item in readiness["critical_missing"]:
            if "goal" in missing_item.lower():
                questions.append({
                    "question": "What specific task or problem should this agent solve?",
                    "category": "metadata",
                    "priority": "critical",
                    "type": "open_ended"
                })

            if "input/output" in missing_item.lower():
                questions.extend([
                    {
                        "question": "How will data be provided to the agent? (API calls, file uploads, etc.)",
                        "category": "functional",
                        "priority": "critical",
                        "type": "multiple_choice",
                        "options": ["REST API", "File upload", "Database query", "Real-time stream"]
                    },
                    {
                        "question": "What should the agent return? (JSON data, documents, notifications, etc.)",
                        "category": "functional",
                        "priority": "critical",
                        "type": "multiple_choice",
                        "options": ["JSON response", "PDF document", "Email notification", "Database update"]
                    }
                ])

            if "compliance" in missing_item.lower():
                questions.append({
                    "question": "Are there specific regulatory or compliance requirements? (HIPAA, SOX, etc.)",
                    "category": "compliance",
                    "priority": "critical",
                    "type": "multiple_choice",
                    "options": ["HIPAA", "SOX", "GDPR", "FDA", "None specific"]
                })

        # Generate questions for improving low-scoring categories
        for category, score in readiness["category_scores"].items():
            if score < 70:
                questions.extend(self._generate_category_questions(category, requirements))

        return questions[:5]  # Limit to 5 questions to avoid overwhelming user

    def _generate_category_questions(self, category: str, requirements: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate questions for specific categories"""

        category_questions = {
            "technical": [
                {
                    "question": "Which external systems need integration? (EHR, CRM, databases, etc.)",
                    "category": "technical",
                    "priority": "high",
                    "type": "multiple_choice",
                    "options": ["EHR system", "CRM", "Database", "Email service", "SMS service", "None"]
                }
            ],
            "functional": [
                {
                    "question": "What are the main processing steps the agent should perform?",
                    "category": "functional",
                    "priority": "high",
                    "type": "open_ended"
                }
            ],
            "compliance": [
                {
                    "question": "What data sensitivity level will this agent handle?",
                    "category": "compliance",
                    "priority": "medium",
                    "type": "multiple_choice",
                    "options": ["Public", "Internal", "Confidential", "Restricted/PHI"]
                }
            ]
        }

        return category_questions.get(category, [])

    def _perform_validation(self, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Perform validation of requirements for consistency and completeness"""

        errors = []
        warnings = []
        suggestions = []

        # Validate consistency
        consistency_check = self._check_consistency(requirements)

        # Check for common issues
        if requirements.get("domain") == "healthcare":
            if "HIPAA" not in str(requirements.get("compliance", {})):
                warnings.append("Healthcare domain specified but HIPAA compliance not mentioned")

            if not any("EHR" in str(req) for req in requirements.get("technical", {}).get("integration_requirements", [])):
                suggestions.append("Consider EHR integration for healthcare workflows")

        # Check for missing critical components
        if not requirements.get("functional", {}).get("input_methods"):
            errors.append("Input methods not specified")

        if not requirements.get("functional", {}).get("output_formats"):
            errors.append("Output formats not specified")

        return {
            "passed": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "suggestions": suggestions,
            "consistency": consistency_check,
        }

    def _check_consistency(self, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Check internal consistency of requirements"""

        consistency_issues = []

        # Check agent type vs complexity
        agent_type = requirements.get("metadata", {}).get("agent_type", "")
        complexity = requirements.get("metadata", {}).get("complexity_level", "")

        if agent_type == "multi_agent" and complexity == "simple":
            consistency_issues.append("Multi-agent type typically requires intermediate or advanced complexity")

        # Check domain vs compliance
        domain = requirements.get("metadata", {}).get("domain", "")
        compliance = requirements.get("compliance", {})

        if domain == "healthcare" and not compliance.get("regulatory_requirements"):
            consistency_issues.append("Healthcare domain requires regulatory compliance specification")

        return {
            "consistent": len(consistency_issues) == 0,
            "issues": consistency_issues,
        }

    def _create_requirements_summary(self, requirements: Dict[str, Any]) -> Dict[str, str]:
        """Create human-readable summary of requirements"""

        metadata = requirements.get("metadata", {})
        functional = requirements.get("functional", {})
        technical = requirements.get("technical", {})
        compliance = requirements.get("compliance", {})

        return {
            "executive": f"Building a {metadata.get('complexity_level', 'simple')} {metadata.get('agent_type', 'agent')} for {metadata.get('domain', 'general')} domain to {metadata.get('agent_goal', 'process data')}",
            "functional": f"Agent will accept {', '.join(functional.get('input_methods', ['data']))} and return {', '.join(functional.get('output_formats', ['results']))}",
            "technical": f"Requires integration with {', '.join(technical.get('integration_requirements', ['no external systems']))}",
            "compliance": f"Must comply with {', '.join(compliance.get('regulatory_requirements', ['standard business requirements']))}",
            "complexity": metadata.get("complexity_level", "simple"),
        }

    def _identify_regulatory_requirements(self, requirements: Dict[str, Any]) -> List[str]:
        """Identify regulatory requirements based on domain and context"""

        regulatory_reqs = []

        domain = requirements.get("domain", "")
        if domain == "healthcare":
            regulatory_reqs.extend(["HIPAA", "Healthcare data privacy"])

        if domain == "finance":
            regulatory_reqs.extend(["SOX", "Financial data security"])

        return regulatory_reqs

    def _identify_security_requirements(self, requirements: Dict[str, Any]) -> List[str]:
        """Identify security requirements"""

        security_reqs = ["Authentication required", "Data encryption in transit"]

        domain = requirements.get("domain", "")
        if domain == "healthcare":
            security_reqs.extend(["PHI encryption at rest", "Audit logging", "Access controls"])

        return security_reqs

    def _identify_audit_requirements(self, requirements: Dict[str, Any]) -> List[str]:
        """Identify audit requirements"""

        audit_reqs = ["Basic operation logging"]

        domain = requirements.get("domain", "")
        if domain == "healthcare":
            audit_reqs.extend(["HIPAA audit trails", "Data access logging", "User activity tracking"])

        return audit_reqs

    def _determine_execution_mode(self, requirements: Dict[str, Any]) -> str:
        """Determine execution mode based on requirements"""

        input_methods = requirements.get("functional", {}).get("input_methods", [])

        if "API" in str(input_methods):
            return "API"
        elif "Batch" in str(input_methods):
            return "Batch"
        else:
            return "API"  # Default

    def _estimate_resources(self, requirements: Dict[str, Any]) -> Dict[str, str]:
        """Estimate resource requirements"""

        complexity = requirements.get("metadata", {}).get("complexity_level", "simple")

        resource_estimates = {
            "simple": {"cpu": "200m", "memory": "512Mi"},
            "intermediate": {"cpu": "500m", "memory": "1Gi"},
            "advanced": {"cpu": "1000m", "memory": "2Gi"},
            "enterprise": {"cpu": "2000m", "memory": "4Gi"},
        }

        return resource_estimates.get(complexity, resource_estimates["simple"])

    def _estimate_component_count(self, requirements: Dict[str, Any]) -> int:
        """Estimate number of components needed"""

        base_components = 3  # Input, Agent, Output

        # Add components based on requirements
        integration_count = len(requirements.get("integrations", []))
        function_count = len(requirements.get("functional_requirements", []))

        return base_components + integration_count + max(0, function_count - 1)

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

        priority_order = {"critical": 1, "high": 2, "medium": 3, "low": 4}

        sorted_questions = sorted(
            questions,
            key=lambda q: priority_order.get(q.get("priority", "low"), 4)
        )

        return [q["question"] for q in sorted_questions]

    def _estimate_completion_time(self, questions: List[Dict[str, Any]]) -> str:
        """Estimate time to complete remaining questions"""

        question_count = len(questions)
        if question_count <= 2:
            return "2-3 minutes"
        elif question_count <= 5:
            return "5-7 minutes"
        else:
            return "10+ minutes"

    def _generate_readiness_recommendations(self, category_scores: Dict[str, float], critical_missing: List[str]) -> List[str]:
        """Generate recommendations for improving readiness"""

        recommendations = []

        if critical_missing:
            recommendations.append(f"Address {len(critical_missing)} critical missing requirements first")

        low_scoring_categories = [cat for cat, score in category_scores.items() if score < 70]
        if low_scoring_categories:
            recommendations.append(f"Provide more details for: {', '.join(low_scoring_categories)}")

        if all(score > 80 for score in category_scores.values()):
            recommendations.append("Requirements are well-defined. Ready for specification building.")

        return recommendations