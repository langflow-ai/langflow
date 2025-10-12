"""Component Recommender Component

Recommends appropriate Langflow components based on agent requirements.
Analyzes needs and suggests the best component combinations for implementation.
"""

import json
from typing import Any, Dict, List, Optional, Tuple

from langflow.custom.custom_component.component import Component
from langflow.field_typing import Data, Text
from langflow.inputs.inputs import MessageTextInput, DictInput, DropdownInput, IntInput, BoolInput
from langflow.schema.data import Data as DataType
from langflow.template.field.base import Output


class ComponentRecommenderComponent(Component):
    display_name = "Component Recommender"
    description = "Recommends appropriate Langflow components based on agent requirements"
    documentation = "Analyzes needs and suggests the best component combinations for implementation"
    icon = "lightbulb"
    name = "ComponentRecommender"

    inputs = [
        DictInput(
            name="requirements",
            display_name="Requirements",
            info="Structured requirements from RequirementsGathererComponent",
            required=True,
        ),
        DictInput(
            name="similar_patterns",
            display_name="Similar Patterns",
            info="Results from SpecificationSearchComponent for pattern matching",
            required=False,
        ),
        DropdownInput(
            name="recommendation_mode",
            display_name="Recommendation Mode",
            options=["optimal", "minimal", "comprehensive"],
            value="optimal",
            info="Mode for component recommendations",
        ),
        BoolInput(
            name="prefer_genesis_components",
            display_name="Prefer Genesis Components",
            value=True,
            info="Whether to prefer Genesis-specific components over generic Langflow",
        ),
        IntInput(
            name="max_components",
            display_name="Maximum Components",
            value=15,
            info="Maximum number of components to recommend",
            range_spec={"min": 3, "max": 30},
        ),
    ]

    outputs = [
        Output(display_name="Recommended Components", name="components", method="recommend_components"),
        Output(display_name="Architecture Design", name="architecture", method="design_architecture"),
        Output(display_name="Component Justification", name="justification", method="justify_recommendations"),
        Output(display_name="Alternative Options", name="alternatives", method="get_alternatives"),
        Output(display_name="Integration Plan", name="integration", method="plan_integration"),
    ]

    def __init__(self, **data):
        super().__init__(**data)
        self.component_catalog = self._build_component_catalog()

    def recommend_components(self) -> DataType:
        """Recommend components based on requirements"""

        recommended_components = self._generate_recommendations()

        return DataType(value={
            "components": recommended_components,
            "total_components": len(recommended_components),
            "estimated_complexity": self._estimate_complexity(recommended_components),
            "component_categories": self._categorize_recommendations(recommended_components),
        })

    def design_architecture(self) -> DataType:
        """Design overall architecture based on component recommendations"""

        components = self.recommend_components().value["components"]
        architecture = self._design_architecture(components)

        return DataType(value={
            "architecture_type": architecture["type"],
            "data_flow": architecture["flow"],
            "component_layers": architecture["layers"],
            "connection_patterns": architecture["connections"],
            "scalability_considerations": architecture["scalability"],
        })

    def justify_recommendations(self) -> DataType:
        """Provide justification for component recommendations"""

        components = self.recommend_components().value["components"]
        justifications = self._generate_justifications(components)

        return DataType(value={
            "component_justifications": justifications,
            "pattern_reasoning": self._explain_pattern_choices(),
            "trade_off_analysis": self._analyze_trade_offs(components),
            "best_practices_applied": self._identify_applied_best_practices(components),
        })

    def get_alternatives(self) -> DataType:
        """Get alternative component options"""

        primary_recommendations = self.recommend_components().value["components"]
        alternatives = self._generate_alternatives(primary_recommendations)

        return DataType(value={
            "alternative_components": alternatives,
            "simpler_options": self._get_simpler_alternatives(),
            "advanced_options": self._get_advanced_alternatives(),
            "different_patterns": self._get_pattern_alternatives(),
        })

    def plan_integration(self) -> DataType:
        """Plan integration between recommended components"""

        components = self.recommend_components().value["components"]
        integration_plan = self._create_integration_plan(components)

        return DataType(value={
            "component_connections": integration_plan["connections"],
            "data_transformations": integration_plan["transformations"],
            "error_handling": integration_plan["error_handling"],
            "configuration_dependencies": integration_plan["dependencies"],
        })

    def _build_component_catalog(self) -> Dict[str, Any]:
        """Build catalog of available components with their capabilities"""

        return {
            # Input/Output Components
            "genesis:chat_input": {
                "category": "input_output",
                "purpose": "Receive user input for agent processing",
                "capabilities": ["text_input", "conversation_context"],
                "required_for": ["all_agents"],
                "complexity": "simple",
                "healthcare_compatible": True,
            },
            "genesis:chat_output": {
                "category": "input_output",
                "purpose": "Return agent responses and results",
                "capabilities": ["text_output", "structured_data", "conversation_context"],
                "required_for": ["all_agents"],
                "complexity": "simple",
                "healthcare_compatible": True,
            },

            # Core Agent Components
            "genesis:agent": {
                "category": "agent",
                "purpose": "Main LLM agent for processing and reasoning",
                "capabilities": ["llm_processing", "tool_usage", "conversation", "complex_reasoning"],
                "required_for": ["single_agent", "simple_workflows"],
                "complexity": "moderate",
                "healthcare_compatible": True,
            },
            "genesis:crewai_agent": {
                "category": "agent",
                "purpose": "Specialized agent for multi-agent coordination",
                "capabilities": ["role_specialization", "task_delegation", "team_coordination"],
                "required_for": ["multi_agent"],
                "complexity": "advanced",
                "healthcare_compatible": True,
            },

            # Coordination Components
            "genesis:crewai_sequential_crew": {
                "category": "coordination",
                "purpose": "Sequential workflow coordination for multi-agent",
                "capabilities": ["sequential_execution", "result_passing", "error_propagation"],
                "required_for": ["multi_agent"],
                "complexity": "advanced",
                "healthcare_compatible": True,
            },
            "genesis:crewai_hierarchical_crew": {
                "category": "coordination",
                "purpose": "Hierarchical workflow coordination",
                "capabilities": ["hierarchical_control", "task_distribution", "result_aggregation"],
                "required_for": ["complex_multi_agent"],
                "complexity": "advanced",
                "healthcare_compatible": True,
            },

            # Task Management
            "genesis:crewai_sequential_task": {
                "category": "task",
                "purpose": "Task definition for multi-agent workflows",
                "capabilities": ["task_specification", "expected_output", "context_passing"],
                "required_for": ["multi_agent"],
                "complexity": "moderate",
                "healthcare_compatible": True,
            },

            # Prompt Components
            "genesis:prompt_template": {
                "category": "prompt",
                "purpose": "Structured prompt management and templating",
                "capabilities": ["template_variables", "prompt_versioning", "context_injection"],
                "required_for": ["complex_agents", "specialized_prompts"],
                "complexity": "moderate",
                "healthcare_compatible": True,
            },

            # Knowledge and Search
            "genesis:knowledge_hub_search": {
                "category": "knowledge",
                "purpose": "Search and retrieve information from knowledge bases",
                "capabilities": ["semantic_search", "knowledge_retrieval", "context_enhancement"],
                "required_for": ["knowledge_intensive"],
                "complexity": "moderate",
                "healthcare_compatible": True,
            },

            # External Integration
            "genesis:mcp_tool": {
                "category": "integration",
                "purpose": "Integration with external systems via MCP protocol",
                "capabilities": ["external_apis", "healthcare_systems", "custom_tools"],
                "required_for": ["external_integration"],
                "complexity": "moderate",
                "healthcare_compatible": True,
            },
            "genesis:api_request": {
                "category": "integration",
                "purpose": "Direct HTTP API integration",
                "capabilities": ["rest_apis", "http_requests", "authentication"],
                "required_for": ["simple_api_integration"],
                "complexity": "simple",
                "healthcare_compatible": True,
            },

            # Memory Components
            "Memory": {
                "category": "memory",
                "purpose": "Conversation memory and context persistence",
                "capabilities": ["conversation_history", "session_management", "context_retrieval"],
                "required_for": ["conversational_agents"],
                "complexity": "moderate",
                "healthcare_compatible": True,
            },
        }

    def _generate_recommendations(self) -> List[Dict[str, Any]]:
        """Generate component recommendations based on requirements"""

        recommendations = []

        # Always start with basic input/output
        recommendations.extend(self._recommend_basic_components())

        # Add agent components based on type
        recommendations.extend(self._recommend_agent_components())

        # Add integration components
        recommendations.extend(self._recommend_integration_components())

        # Add specialized components
        recommendations.extend(self._recommend_specialized_components())

        # Add coordination components if needed
        recommendations.extend(self._recommend_coordination_components())

        # Filter by mode and preferences
        filtered_recommendations = self._filter_recommendations(recommendations)

        return filtered_recommendations[:self.max_components]

    def _recommend_basic_components(self) -> List[Dict[str, Any]]:
        """Recommend basic input/output components"""

        basic_components = [
            {
                "type": "genesis:chat_input",
                "name": "User Input",
                "description": "Receives user requests and agent interaction",
                "category": "input_output",
                "priority": "essential",
                "configuration": {
                    "message_type": "text",
                    "conversation_enabled": True,
                },
                "provides": [{"useAs": "input", "in": "main-agent"}],
            },
            {
                "type": "genesis:chat_output",
                "name": "Agent Response",
                "description": "Returns agent responses and results",
                "category": "input_output",
                "priority": "essential",
                "configuration": {
                    "should_store_message": True,
                    "include_metadata": True,
                },
                "provides": [],
            }
        ]

        return basic_components

    def _recommend_agent_components(self) -> List[Dict[str, Any]]:
        """Recommend agent components based on agent type"""

        agent_type = self.requirements.get("metadata", {}).get("agent_type", "single_agent")
        complexity = self.requirements.get("metadata", {}).get("complexity_level", "simple")

        agent_components = []

        if agent_type == "single_agent":
            agent_components.append({
                "type": "genesis:agent",
                "name": "Main Agent",
                "description": "Primary LLM agent for processing requests and coordinating tasks",
                "category": "agent",
                "priority": "essential",
                "configuration": {
                    "agent_llm": "Azure OpenAI",
                    "model_name": "gpt-4" if complexity in ["advanced", "enterprise"] else "gpt-3.5-turbo",
                    "temperature": 0.1,
                    "max_tokens": 2500 if complexity == "advanced" else 1500,
                    "max_iterations": 10,
                },
                "provides": [{"useAs": "input", "in": "agent-response"}],
            })

        elif agent_type == "multi_agent":
            # Multiple specialized agents
            domain = self.requirements.get("metadata", {}).get("domain", "general")
            use_case = self.requirements.get("metadata", {}).get("use_case_category", "general")

            if domain == "healthcare" and use_case == "prior_authorization":
                agent_components.extend([
                    {
                        "type": "genesis:crewai_agent",
                        "name": "Eligibility Verification Agent",
                        "description": "Specializes in insurance eligibility verification",
                        "category": "agent",
                        "priority": "essential",
                        "configuration": {
                            "role": "Insurance Eligibility Specialist",
                            "goal": "Verify patient insurance eligibility and benefits",
                            "backstory": "Expert in insurance verification with deep knowledge of payer systems",
                        },
                    },
                    {
                        "type": "genesis:crewai_agent",
                        "name": "Medical Necessity Agent",
                        "description": "Evaluates medical necessity for procedures",
                        "category": "agent",
                        "priority": "essential",
                        "configuration": {
                            "role": "Clinical Review Specialist",
                            "goal": "Evaluate medical necessity based on clinical guidelines",
                            "backstory": "Clinical expert with extensive knowledge of medical necessity criteria",
                        },
                    },
                    {
                        "type": "genesis:crewai_agent",
                        "name": "Documentation Agent",
                        "description": "Handles form generation and documentation",
                        "category": "agent",
                        "priority": "essential",
                        "configuration": {
                            "role": "Documentation Coordinator",
                            "goal": "Generate required forms and documentation for approval process",
                            "backstory": "Administrative expert specializing in healthcare documentation",
                        },
                    }
                ])
            else:
                # Generic multi-agent setup
                agent_components.extend([
                    {
                        "type": "genesis:crewai_agent",
                        "name": "Primary Processing Agent",
                        "description": "Main agent for primary task processing",
                        "category": "agent",
                        "priority": "essential",
                        "configuration": {
                            "role": "Primary Processor",
                            "goal": "Handle main processing tasks",
                            "backstory": "Expert in primary task execution",
                        },
                    },
                    {
                        "type": "genesis:crewai_agent",
                        "name": "Coordination Agent",
                        "description": "Coordinates workflow and manages results",
                        "category": "agent",
                        "priority": "essential",
                        "configuration": {
                            "role": "Workflow Coordinator",
                            "goal": "Coordinate tasks and consolidate results",
                            "backstory": "Expert in workflow management and result synthesis",
                        },
                    }
                ])

        return agent_components

    def _recommend_integration_components(self) -> List[Dict[str, Any]]:
        """Recommend integration components based on requirements"""

        integration_components = []
        integrations = self.requirements.get("technical", {}).get("integration_requirements", [])

        for integration in integrations:
            integration_lower = integration.lower()

            if any(keyword in integration_lower for keyword in ["ehr", "epic", "cerner", "allscripts"]):
                integration_components.append({
                    "type": "genesis:mcp_tool",
                    "name": "EHR Integration",
                    "description": "Integration with Electronic Health Record systems",
                    "category": "integration",
                    "priority": "high",
                    "configuration": {
                        "tool_name": "ehr_clinical_data",
                        "description": "Access patient data and clinical information from EHR systems",
                        "timeout_seconds": 30,
                    },
                    "provides": [{"useAs": "tools", "in": "main-agent"}],
                })

            elif any(keyword in integration_lower for keyword in ["insurance", "eligibility", "payer"]):
                integration_components.append({
                    "type": "genesis:mcp_tool",
                    "name": "Insurance Verification",
                    "description": "Real-time insurance eligibility and benefits verification",
                    "category": "integration",
                    "priority": "high",
                    "configuration": {
                        "tool_name": "insurance_eligibility_check",
                        "description": "Verify patient insurance eligibility and benefits",
                        "timeout_seconds": 30,
                    },
                    "provides": [{"useAs": "tools", "in": "main-agent"}],
                })

            elif any(keyword in integration_lower for keyword in ["email", "smtp"]):
                integration_components.append({
                    "type": "genesis:mcp_tool",
                    "name": "Email Service",
                    "description": "Email notification and communication service",
                    "category": "integration",
                    "priority": "medium",
                    "configuration": {
                        "tool_name": "email_service",
                        "description": "Send emails and notifications to patients and providers",
                        "timeout_seconds": 15,
                    },
                    "provides": [{"useAs": "tools", "in": "main-agent"}],
                })

            elif any(keyword in integration_lower for keyword in ["sms", "text", "messaging"]):
                integration_components.append({
                    "type": "genesis:mcp_tool",
                    "name": "SMS Gateway",
                    "description": "SMS messaging service for notifications",
                    "category": "integration",
                    "priority": "medium",
                    "configuration": {
                        "tool_name": "sms_gateway",
                        "description": "Send SMS notifications and reminders",
                        "timeout_seconds": 15,
                    },
                    "provides": [{"useAs": "tools", "in": "main-agent"}],
                })

            elif any(keyword in integration_lower for keyword in ["api", "rest", "http"]):
                integration_components.append({
                    "type": "genesis:api_request",
                    "name": "External API",
                    "description": "HTTP API integration for external services",
                    "category": "integration",
                    "priority": "medium",
                    "configuration": {
                        "method": "POST",
                        "timeout": 30,
                        "headers": [
                            {"key": "Content-Type", "value": "application/json"},
                            {"key": "Authorization", "value": "Bearer ${API_TOKEN}"}
                        ]
                    },
                    "provides": [{"useAs": "tools", "in": "main-agent"}],
                })

        return integration_components

    def _recommend_specialized_components(self) -> List[Dict[str, Any]]:
        """Recommend specialized components based on requirements"""

        specialized_components = []

        # Memory component for conversational agents
        if self._needs_memory():
            specialized_components.append({
                "type": "Memory",
                "name": "Conversation Memory",
                "description": "Maintains conversation history and context",
                "category": "memory",
                "priority": "high",
                "configuration": {
                    "mode": "Retrieve",
                    "n_messages": 10,
                    "session_id": "${SESSION_ID}",
                },
                "provides": [{"useAs": "memory", "in": "main-agent"}],
            })

        # Knowledge search for knowledge-intensive tasks
        if self._needs_knowledge_search():
            specialized_components.append({
                "type": "genesis:knowledge_hub_search",
                "name": "Knowledge Search",
                "description": "Search relevant knowledge bases and documentation",
                "category": "knowledge",
                "priority": "medium",
                "configuration": {
                    "search_type": "semantic",
                    "max_results": 5,
                },
                "provides": [{"useAs": "tools", "in": "main-agent"}],
            })

        # Prompt template for complex prompting
        if self._needs_prompt_template():
            specialized_components.append({
                "type": "genesis:prompt_template",
                "name": "System Prompt",
                "description": "Structured system prompt with healthcare guidelines",
                "category": "prompt",
                "priority": "medium",
                "configuration": {
                    "template": self._generate_prompt_template(),
                    "variables": ["user_input", "context", "guidelines"],
                },
                "provides": [{"useAs": "prompt", "in": "main-agent"}],
            })

        return specialized_components

    def _recommend_coordination_components(self) -> List[Dict[str, Any]]:
        """Recommend coordination components for multi-agent setups"""

        agent_type = self.requirements.get("metadata", {}).get("agent_type", "single_agent")

        if agent_type != "multi_agent":
            return []

        coordination_components = []

        # Tasks for each agent
        use_case = self.requirements.get("metadata", {}).get("use_case_category", "general")

        if use_case == "prior_authorization":
            coordination_components.extend([
                {
                    "type": "genesis:crewai_sequential_task",
                    "name": "Eligibility Verification Task",
                    "description": "Task for verifying insurance eligibility",
                    "category": "task",
                    "priority": "essential",
                    "configuration": {
                        "description": "Verify patient insurance eligibility and benefits for the requested procedure",
                        "expected_output": "Eligibility status, coverage details, and patient responsibility",
                        "agent": "eligibility-verification-agent",
                    },
                },
                {
                    "type": "genesis:crewai_sequential_task",
                    "name": "Medical Necessity Task",
                    "description": "Task for evaluating medical necessity",
                    "category": "task",
                    "priority": "essential",
                    "configuration": {
                        "description": "Evaluate medical necessity based on clinical guidelines and payer criteria",
                        "expected_output": "Medical necessity determination with supporting rationale",
                        "agent": "medical-necessity-agent",
                    },
                },
                {
                    "type": "genesis:crewai_sequential_task",
                    "name": "Documentation Task",
                    "description": "Task for generating required documentation",
                    "category": "task",
                    "priority": "essential",
                    "configuration": {
                        "description": "Generate required forms and documentation for prior authorization",
                        "expected_output": "Completed authorization forms and supporting documentation",
                        "agent": "documentation-agent",
                    },
                }
            ])

        # Crew coordination
        coordination_components.append({
            "type": "genesis:crewai_sequential_crew",
            "name": "Agent Coordination Crew",
            "description": "Coordinates execution of all agents in sequence",
            "category": "coordination",
            "priority": "essential",
            "configuration": {
                "verbose": False,
                "memory": True,
                "planning": True,
            },
            "provides": [{"useAs": "input", "in": "agent-response"}],
        })

        return coordination_components

    def _filter_recommendations(self, recommendations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter recommendations based on mode and preferences"""

        if self.recommendation_mode == "minimal":
            # Only essential components
            filtered = [comp for comp in recommendations if comp["priority"] == "essential"]
        elif self.recommendation_mode == "comprehensive":
            # All components
            filtered = recommendations
        else:  # optimal
            # Essential + high priority components
            filtered = [comp for comp in recommendations if comp["priority"] in ["essential", "high"]]

        # Prefer Genesis components if requested
        if self.prefer_genesis_components:
            genesis_components = [comp for comp in filtered if comp["type"].startswith("genesis:")]
            other_components = [comp for comp in filtered if not comp["type"].startswith("genesis:")]
            filtered = genesis_components + other_components

        return filtered

    def _needs_memory(self) -> bool:
        """Check if agent needs memory component"""

        functional_reqs = self.requirements.get("functional", {})
        input_methods = functional_reqs.get("input_methods", [])

        return ("conversational" in str(input_methods).lower() or
                "chat" in str(input_methods).lower() or
                self.requirements.get("metadata", {}).get("use_case_category") in ["patient_communication"])

    def _needs_knowledge_search(self) -> bool:
        """Check if agent needs knowledge search"""

        use_case = self.requirements.get("metadata", {}).get("use_case_category", "")
        domain = self.requirements.get("metadata", {}).get("domain", "")

        return (use_case in ["clinical_decision_support", "compliance_monitoring"] or
                "knowledge" in str(self.requirements.get("functional", {})).lower() or
                domain == "healthcare")

    def _needs_prompt_template(self) -> bool:
        """Check if agent needs structured prompt template"""

        complexity = self.requirements.get("metadata", {}).get("complexity_level", "simple")
        domain = self.requirements.get("metadata", {}).get("domain", "")

        return complexity in ["advanced", "enterprise"] or domain == "healthcare"

    def _generate_prompt_template(self) -> str:
        """Generate appropriate prompt template"""

        domain = self.requirements.get("metadata", {}).get("domain", "general")
        use_case = self.requirements.get("metadata", {}).get("use_case_category", "general")

        if domain == "healthcare":
            if use_case == "prior_authorization":
                return """You are a healthcare prior authorization specialist.

Your responsibilities:
1. Verify insurance eligibility and coverage
2. Evaluate medical necessity based on clinical guidelines
3. Generate required documentation and forms
4. Ensure HIPAA compliance in all activities

User Request: {user_input}
Context: {context}
Guidelines: {guidelines}

Provide thorough, accurate, and compliant responses."""

            else:
                return """You are a healthcare AI assistant.

Your responsibilities:
1. Process healthcare-related requests safely and accurately
2. Maintain HIPAA compliance and patient privacy
3. Provide evidence-based recommendations
4. Ensure clinical safety in all responses

User Request: {user_input}
Context: {context}
Guidelines: {guidelines}

Provide helpful, accurate, and compliant responses."""

        return """You are an intelligent AI assistant.

Process the user's request thoroughly and provide helpful, accurate responses.

User Request: {user_input}
Context: {context}

Provide clear and actionable responses."""

    def _design_architecture(self, components: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Design overall architecture for the components"""

        agent_components = [comp for comp in components if comp["category"] == "agent"]

        if len(agent_components) > 1:
            architecture_type = "multi_agent_workflow"
            flow_pattern = "sequential_coordination"
        else:
            architecture_type = "single_agent_pipeline"
            flow_pattern = "linear_processing"

        return {
            "type": architecture_type,
            "flow": flow_pattern,
            "layers": self._identify_layers(components),
            "connections": self._map_connections(components),
            "scalability": self._assess_scalability(components),
        }

    def _identify_layers(self, components: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """Identify architectural layers"""

        layers = {
            "input_layer": [],
            "processing_layer": [],
            "integration_layer": [],
            "output_layer": [],
            "coordination_layer": [],
        }

        for comp in components:
            comp_name = comp["name"]
            category = comp["category"]

            if category == "input_output" and "input" in comp["type"]:
                layers["input_layer"].append(comp_name)
            elif category == "input_output" and "output" in comp["type"]:
                layers["output_layer"].append(comp_name)
            elif category == "agent":
                layers["processing_layer"].append(comp_name)
            elif category == "integration":
                layers["integration_layer"].append(comp_name)
            elif category in ["coordination", "task"]:
                layers["coordination_layer"].append(comp_name)

        return layers

    def _map_connections(self, components: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Map connections between components"""

        connections = []

        for comp in components:
            provides = comp.get("provides", [])
            for connection in provides:
                connections.append({
                    "from": comp["name"],
                    "to": connection.get("in", ""),
                    "relationship": connection.get("useAs", ""),
                })

        return connections

    def _assess_scalability(self, components: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Assess scalability characteristics"""

        integration_count = len([comp for comp in components if comp["category"] == "integration"])
        agent_count = len([comp for comp in components if comp["category"] == "agent"])

        return {
            "resource_requirements": "high" if agent_count > 2 else "medium" if agent_count > 1 else "low",
            "horizontal_scaling": agent_count > 1,
            "integration_complexity": "high" if integration_count > 3 else "medium" if integration_count > 1 else "low",
            "recommended_deployment": "kubernetes" if agent_count > 1 else "container",
        }

    def _generate_justifications(self, components: List[Dict[str, Any]]) -> Dict[str, str]:
        """Generate justifications for component choices"""

        justifications = {}

        for comp in components:
            comp_name = comp["name"]
            comp_type = comp["type"]
            category = comp["category"]

            if category == "input_output":
                justifications[comp_name] = f"Essential for user interaction and response delivery"
            elif category == "agent":
                justifications[comp_name] = f"Core LLM processing component for {comp.get('description', 'task execution')}"
            elif category == "integration":
                justifications[comp_name] = f"Required for external system connectivity: {comp.get('description', '')}"
            elif category == "coordination":
                justifications[comp_name] = f"Necessary for multi-agent workflow orchestration"
            elif category == "memory":
                justifications[comp_name] = f"Enables conversation context and session persistence"
            else:
                justifications[comp_name] = f"Enhances functionality: {comp.get('description', '')}"

        return justifications

    def _explain_pattern_choices(self) -> Dict[str, str]:
        """Explain architectural pattern choices"""

        agent_type = self.requirements.get("metadata", {}).get("agent_type", "single_agent")
        complexity = self.requirements.get("metadata", {}).get("complexity_level", "simple")

        explanations = {}

        if agent_type == "single_agent":
            explanations["agent_pattern"] = "Single agent pattern chosen for simplicity and direct control"
        elif agent_type == "multi_agent":
            explanations["agent_pattern"] = "Multi-agent pattern chosen for specialized task handling and parallel processing"

        if complexity in ["advanced", "enterprise"]:
            explanations["complexity_handling"] = "Advanced components selected to handle complex requirements and integrations"

        return explanations

    def _analyze_trade_offs(self, components: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """Analyze trade-offs in component selection"""

        return {
            "benefits": [
                "Optimized for healthcare workflows",
                "HIPAA compliance built-in",
                "Scalable architecture",
                "Reusable components",
            ],
            "considerations": [
                "Higher resource requirements for multi-agent setup",
                "Complex integration setup",
                "Requires healthcare domain expertise",
            ],
            "alternatives": [
                "Simpler single-agent approach for reduced complexity",
                "API-only integration for faster development",
                "Generic components for non-healthcare domains",
            ],
        }

    def _identify_applied_best_practices(self, components: List[Dict[str, Any]]) -> List[str]:
        """Identify best practices applied in recommendations"""

        practices = []

        if self.prefer_genesis_components:
            practices.append("Using Genesis-specific components for better integration")

        if any(comp["category"] == "memory" for comp in components):
            practices.append("Including conversation memory for context persistence")

        if any("hipaa" in str(comp.get("configuration", {})).lower() for comp in components):
            practices.append("HIPAA compliance considerations in configuration")

        if len([comp for comp in components if comp["category"] == "integration"]) > 0:
            practices.append("Proper separation of integration concerns")

        return practices

    def _generate_alternatives(self, primary_recommendations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate alternative component options"""

        alternatives = []

        for comp in primary_recommendations:
            if comp["category"] == "agent" and comp["type"] == "genesis:agent":
                alternatives.append({
                    "original": comp["name"],
                    "alternative_type": "genesis:crewai_agent",
                    "alternative_name": "Specialized CrewAI Agent",
                    "trade_off": "More specialized but requires multi-agent setup",
                })

            elif comp["category"] == "integration" and comp["type"] == "genesis:mcp_tool":
                alternatives.append({
                    "original": comp["name"],
                    "alternative_type": "genesis:api_request",
                    "alternative_name": "Direct API Integration",
                    "trade_off": "Simpler setup but less feature-rich",
                })

        return alternatives

    def _get_simpler_alternatives(self) -> List[str]:
        """Get simpler alternative approaches"""

        return [
            "Use single agent instead of multi-agent for reduced complexity",
            "Replace MCP tools with direct API requests for simpler integration",
            "Remove memory component for stateless operation",
            "Use minimal prompt templates for faster development",
        ]

    def _get_advanced_alternatives(self) -> List[str]:
        """Get more advanced alternative approaches"""

        return [
            "Add hierarchical crew coordination for complex workflows",
            "Include advanced knowledge search with vector databases",
            "Add real-time monitoring and alerting components",
            "Implement sophisticated error handling and retry mechanisms",
        ]

    def _get_pattern_alternatives(self) -> List[str]:
        """Get alternative architectural patterns"""

        return [
            "Event-driven architecture for real-time processing",
            "Microservices pattern for independent component scaling",
            "Pipeline pattern for linear data processing",
            "Hub-and-spoke pattern for centralized coordination",
        ]

    def _create_integration_plan(self, components: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create integration plan between components"""

        connections = []
        transformations = []
        error_handling = []
        dependencies = []

        # Map data flow connections
        for comp in components:
            provides = comp.get("provides", [])
            for connection in provides:
                connections.append({
                    "source": comp["name"],
                    "target": connection.get("in", ""),
                    "data_type": connection.get("useAs", ""),
                    "description": f"Data flows from {comp['name']} to target component",
                })

        # Identify required transformations
        integration_components = [comp for comp in components if comp["category"] == "integration"]
        for integration in integration_components:
            transformations.append({
                "component": integration["name"],
                "input_format": "structured_request",
                "output_format": "api_response",
                "transformation": "Convert agent request to external API format",
            })

        # Define error handling strategies
        for comp in components:
            if comp["category"] in ["integration", "agent"]:
                error_handling.append({
                    "component": comp["name"],
                    "strategy": "timeout_and_retry",
                    "fallback": "graceful_degradation",
                    "timeout": comp.get("configuration", {}).get("timeout_seconds", 30),
                })

        # Map configuration dependencies
        for comp in components:
            config = comp.get("configuration", {})
            for key, value in config.items():
                if isinstance(value, str) and "${" in value:
                    dependencies.append({
                        "component": comp["name"],
                        "parameter": key,
                        "dependency": value,
                        "type": "environment_variable",
                    })

        return {
            "connections": connections,
            "transformations": transformations,
            "error_handling": error_handling,
            "dependencies": dependencies,
        }

    def _estimate_complexity(self, components: List[Dict[str, Any]]) -> str:
        """Estimate overall complexity of the component setup"""

        total_components = len(components)
        agent_count = len([comp for comp in components if comp["category"] == "agent"])
        integration_count = len([comp for comp in components if comp["category"] == "integration"])

        if total_components > 15 or agent_count > 3:
            return "enterprise"
        elif total_components > 10 or agent_count > 1:
            return "advanced"
        elif total_components > 6 or integration_count > 2:
            return "intermediate"
        else:
            return "simple"

    def _categorize_recommendations(self, components: List[Dict[str, Any]]) -> Dict[str, int]:
        """Categorize component recommendations"""

        categories = {}
        for comp in components:
            category = comp["category"]
            categories[category] = categories.get(category, 0) + 1

        return categories