"""MCP Tool Discovery Component

Identifies required MCP tools and checks availability for agent specifications.
Provides fallback options and mock template recommendations.
"""

import json
from typing import Any, Dict, List, Optional

from langflow.custom.custom_component.component import Component
from langflow.field_typing import Data, Text
from langflow.inputs.inputs import MessageTextInput, DictInput, DropdownInput, BoolInput
from langflow.schema.data import Data as DataType
from langflow.template.field.base import Output


class MCPToolDiscoveryComponent(Component):
    display_name = "MCP Tool Discovery"
    description = "Identifies required MCP tools and checks availability for agent specifications"
    documentation = "Provides fallback options and mock template recommendations"
    icon = "tool"
    name = "MCPToolDiscovery"

    inputs = [
        DictInput(
            name="requirements",
            display_name="Requirements",
            info="Agent requirements from RequirementsGathererComponent",
            required=True,
        ),
        DictInput(
            name="recommended_components",
            display_name="Recommended Components",
            info="Components from ComponentRecommenderComponent that need MCP tools",
            required=True,
        ),
        DropdownInput(
            name="discovery_mode",
            display_name="Discovery Mode",
            options=["comprehensive", "essential_only", "mock_preferred"],
            value="comprehensive",
            info="Mode for MCP tool discovery",
        ),
        BoolInput(
            name="include_mocks",
            display_name="Include Mock Templates",
            value=True,
            info="Whether to provide mock template alternatives",
        ),
    ]

    outputs = [
        Output(display_name="Required Tools", name="required_tools", method="discover_tools"),
        Output(display_name="Mock Availability", name="mock_status", method="check_mock_availability"),
        Output(display_name="Tool Configuration", name="tool_config", method="generate_tool_config"),
        Output(display_name="Integration Guide", name="integration_guide", method="create_integration_guide"),
        Output(display_name="Fallback Options", name="fallbacks", method="suggest_fallbacks"),
    ]

    def __init__(self, **data):
        super().__init__(**data)
        self.mcp_catalog = self._build_mcp_catalog()
        self.mock_templates = self._get_available_mock_templates()

    def discover_tools(self) -> DataType:
        """Discover required MCP tools based on requirements and components"""

        required_tools = self._identify_required_tools()
        tool_analysis = self._analyze_tool_requirements(required_tools)

        return DataType(value={
            "tools": required_tools,
            "tool_categories": self._categorize_tools(required_tools),
            "priority_levels": tool_analysis["priorities"],
            "integration_complexity": tool_analysis["complexity"],
            "server_requirements": self._identify_server_requirements(required_tools),
        })

    def check_mock_availability(self) -> DataType:
        """Check availability of mock templates for required tools"""

        required_tools = self.discover_tools().value["tools"]
        mock_status = self._check_mock_coverage(required_tools)

        return DataType(value={
            "mock_coverage": mock_status["coverage_percentage"],
            "available_mocks": mock_status["available"],
            "missing_mocks": mock_status["missing"],
            "mock_recommendations": self._generate_mock_recommendations(mock_status),
            "development_readiness": mock_status["coverage_percentage"] >= 80,
        })

    def generate_tool_config(self) -> DataType:
        """Generate configuration for MCP tools"""

        required_tools = self.discover_tools().value["tools"]
        tool_configs = self._generate_configurations(required_tools)

        return DataType(value={
            "tool_configurations": tool_configs,
            "server_connections": self._generate_server_connections(required_tools),
            "authentication_requirements": self._identify_auth_requirements(required_tools),
            "environment_variables": self._list_required_env_vars(required_tools),
        })

    def create_integration_guide(self) -> DataType:
        """Create integration guide for MCP tools"""

        required_tools = self.discover_tools().value["tools"]
        integration_guide = self._create_integration_instructions(required_tools)

        return DataType(value={
            "setup_instructions": integration_guide["setup"],
            "configuration_steps": integration_guide["configuration"],
            "testing_procedures": integration_guide["testing"],
            "troubleshooting_guide": integration_guide["troubleshooting"],
        })

    def suggest_fallbacks(self) -> DataType:
        """Suggest fallback options for unavailable MCP tools"""

        required_tools = self.discover_tools().value["tools"]
        mock_status = self.check_mock_availability().value
        fallback_options = self._generate_fallback_options(required_tools, mock_status)

        return DataType(value={
            "api_alternatives": fallback_options["api_alternatives"],
            "mock_alternatives": fallback_options["mock_alternatives"],
            "simplified_approaches": fallback_options["simplified"],
            "development_strategies": fallback_options["strategies"],
        })

    def _build_mcp_catalog(self) -> Dict[str, Any]:
        """Build catalog of available MCP tools and their capabilities"""

        return {
            # Healthcare Integration Tools
            "ehr_clinical_data": {
                "category": "healthcare_integration",
                "description": "Access patient clinical data from EHR systems",
                "capabilities": ["patient_lookup", "clinical_history", "lab_results", "medications"],
                "required_for": ["patient_care", "clinical_decision_support"],
                "complexity": "moderate",
                "mock_available": True,
                "auth_required": True,
                "server_type": "healthcare_apis",
            },
            "insurance_eligibility_check": {
                "category": "insurance_verification",
                "description": "Real-time insurance eligibility and benefits verification",
                "capabilities": ["eligibility_check", "benefit_verification", "coverage_details"],
                "required_for": ["prior_authorization", "billing"],
                "complexity": "moderate",
                "mock_available": True,
                "auth_required": True,
                "server_type": "insurance_apis",
            },
            "email_service": {
                "category": "communication",
                "description": "Email notification and communication service",
                "capabilities": ["send_email", "template_support", "delivery_tracking"],
                "required_for": ["notifications", "patient_communication"],
                "complexity": "simple",
                "mock_available": True,
                "auth_required": True,
                "server_type": "communication_services",
            },
            "sms_gateway": {
                "category": "communication",
                "description": "SMS messaging service for notifications",
                "capabilities": ["send_sms", "delivery_confirmation", "opt_out_handling"],
                "required_for": ["reminders", "alerts"],
                "complexity": "simple",
                "mock_available": True,
                "auth_required": True,
                "server_type": "communication_services",
            },
            "clinical_guidelines_mcp": {
                "category": "clinical_knowledge",
                "description": "Access to clinical guidelines and protocols",
                "capabilities": ["guideline_search", "protocol_lookup", "evidence_retrieval"],
                "required_for": ["clinical_decision_support", "medical_necessity"],
                "complexity": "moderate",
                "mock_available": True,
                "auth_required": False,
                "server_type": "knowledge_bases",
            },
            "document_generation_mcp": {
                "category": "document_processing",
                "description": "Generate and process healthcare documents",
                "capabilities": ["pdf_generation", "form_filling", "template_processing"],
                "required_for": ["prior_authorization", "documentation"],
                "complexity": "moderate",
                "mock_available": True,
                "auth_required": False,
                "server_type": "document_services",
            },
        }

    def _get_available_mock_templates(self) -> List[str]:
        """Get list of available mock templates from MCP component"""

        # This would typically read from the MCP component's mock templates
        # For now, return the known templates
        return [
            "ehr_clinical_data",
            "insurance_eligibility_check",
            "email_service",
            "sms_gateway",
            "clinical_guidelines_mcp",
            "document_generation_mcp",
            "provider_notes_api",
            "audit_database_connector",
            "healthcare_compliance_nlp",
            "template_matching_engine",
        ]

    def _identify_required_tools(self) -> List[Dict[str, Any]]:
        """Identify required MCP tools based on requirements and components"""

        required_tools = []

        # Analyze integration requirements
        integrations = self.requirements.get("technical", {}).get("integration_requirements", [])
        for integration in integrations:
            tools = self._map_integration_to_tools(integration)
            required_tools.extend(tools)

        # Analyze recommended components
        components = self.recommended_components.get("components", [])
        for component in components:
            if component.get("type") == "genesis:mcp_tool":
                tool_config = component.get("configuration", {})
                tool_name = tool_config.get("tool_name")
                if tool_name and tool_name in self.mcp_catalog:
                    required_tools.append({
                        "name": tool_name,
                        "component_name": component.get("name"),
                        "priority": component.get("priority", "medium"),
                        "catalog_info": self.mcp_catalog[tool_name],
                    })

        # Remove duplicates
        unique_tools = {}
        for tool in required_tools:
            tool_name = tool["name"]
            if tool_name not in unique_tools or tool["priority"] == "essential":
                unique_tools[tool_name] = tool

        return list(unique_tools.values())

    def _map_integration_to_tools(self, integration: str) -> List[Dict[str, Any]]:
        """Map integration requirement to specific MCP tools"""

        integration_lower = integration.lower()
        tools = []

        if any(keyword in integration_lower for keyword in ["ehr", "epic", "cerner"]):
            tools.append({
                "name": "ehr_clinical_data",
                "component_name": "EHR Integration",
                "priority": "high",
                "catalog_info": self.mcp_catalog.get("ehr_clinical_data", {}),
            })

        if any(keyword in integration_lower for keyword in ["insurance", "eligibility"]):
            tools.append({
                "name": "insurance_eligibility_check",
                "component_name": "Insurance Verification",
                "priority": "high",
                "catalog_info": self.mcp_catalog.get("insurance_eligibility_check", {}),
            })

        if "email" in integration_lower:
            tools.append({
                "name": "email_service",
                "component_name": "Email Service",
                "priority": "medium",
                "catalog_info": self.mcp_catalog.get("email_service", {}),
            })

        if "sms" in integration_lower:
            tools.append({
                "name": "sms_gateway",
                "component_name": "SMS Gateway",
                "priority": "medium",
                "catalog_info": self.mcp_catalog.get("sms_gateway", {}),
            })

        return tools

    def _analyze_tool_requirements(self, tools: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze tool requirements for priorities and complexity"""

        priorities = {"essential": 0, "high": 0, "medium": 0, "low": 0}
        complexity_levels = {"simple": 0, "moderate": 0, "advanced": 0}

        for tool in tools:
            priority = tool.get("priority", "medium")
            priorities[priority] = priorities.get(priority, 0) + 1

            catalog_info = tool.get("catalog_info", {})
            complexity = catalog_info.get("complexity", "moderate")
            complexity_levels[complexity] = complexity_levels.get(complexity, 0) + 1

        overall_complexity = "simple"
        if complexity_levels["advanced"] > 0:
            overall_complexity = "advanced"
        elif complexity_levels["moderate"] > complexity_levels["simple"]:
            overall_complexity = "moderate"

        return {
            "priorities": priorities,
            "complexity": overall_complexity,
            "total_tools": len(tools),
        }

    def _categorize_tools(self, tools: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """Categorize tools by type"""

        categories = {}
        for tool in tools:
            catalog_info = tool.get("catalog_info", {})
            category = catalog_info.get("category", "general")
            if category not in categories:
                categories[category] = []
            categories[category].append(tool["name"])

        return categories

    def _identify_server_requirements(self, tools: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """Identify MCP server requirements"""

        server_requirements = {}
        for tool in tools:
            catalog_info = tool.get("catalog_info", {})
            server_type = catalog_info.get("server_type", "general")
            if server_type not in server_requirements:
                server_requirements[server_type] = []
            server_requirements[server_type].append(tool["name"])

        return server_requirements

    def _check_mock_coverage(self, tools: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Check mock template coverage for required tools"""

        available_mocks = []
        missing_mocks = []

        for tool in tools:
            tool_name = tool["name"]
            if tool_name in self.mock_templates:
                available_mocks.append(tool_name)
            else:
                missing_mocks.append(tool_name)

        coverage_percentage = (len(available_mocks) / len(tools)) * 100 if tools else 100

        return {
            "coverage_percentage": coverage_percentage,
            "available": available_mocks,
            "missing": missing_mocks,
            "total_required": len(tools),
        }

    def _generate_mock_recommendations(self, mock_status: Dict[str, Any]) -> List[str]:
        """Generate recommendations for mock usage"""

        recommendations = []

        if mock_status["coverage_percentage"] >= 90:
            recommendations.append("Excellent mock coverage. Development can proceed with mock servers.")
        elif mock_status["coverage_percentage"] >= 70:
            recommendations.append("Good mock coverage. Consider creating missing mock templates.")
        else:
            recommendations.append("Limited mock coverage. Create additional mock templates or use API alternatives.")

        if mock_status["missing"]:
            recommendations.append(f"Create mock templates for: {', '.join(mock_status['missing'])}")

        if mock_status["coverage_percentage"] < 50:
            recommendations.append("Consider using direct API integration for faster development.")

        return recommendations

    def _generate_configurations(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate configuration for MCP tools"""

        configurations = []

        for tool in tools:
            tool_name = tool["name"]
            catalog_info = tool.get("catalog_info", {})

            config = {
                "id": f"{tool_name.replace('_', '-')}-tool",
                "name": tool.get("component_name", tool_name.title()),
                "kind": "Tool",
                "type": "genesis:mcp_tool",
                "description": catalog_info.get("description", ""),
                "asTools": True,
                "config": {
                    "tool_name": tool_name,
                    "description": catalog_info.get("description", ""),
                    "timeout_seconds": 30,
                    "retry_attempts": 3,
                },
                "provides": [
                    {
                        "useAs": "tools",
                        "in": "main-agent",
                        "description": f"Provide {tool_name} capabilities"
                    }
                ]
            }

            configurations.append(config)

        return configurations

    def _generate_server_connections(self, tools: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate MCP server connection configurations"""

        server_connections = {}
        server_requirements = self._identify_server_requirements(tools)

        for server_type, tool_names in server_requirements.items():
            server_connections[server_type] = {
                "connection_type": "STDIO",  # Default to STDIO
                "tools_provided": tool_names,
                "configuration": {
                    "command": f"mcp-{server_type}",
                    "args": ["--config", f"/etc/mcp/{server_type}.json"],
                    "env": self._get_server_env_vars(server_type),
                },
                "fallback": {
                    "mode": "mock",
                    "timeout_ms": 5000,
                }
            }

        return server_connections

    def _get_server_env_vars(self, server_type: str) -> Dict[str, str]:
        """Get environment variables required for server type"""

        env_vars = {
            "healthcare_apis": {
                "EHR_API_KEY": "${EHR_API_KEY}",
                "EHR_BASE_URL": "${EHR_BASE_URL}",
                "FHIR_VERSION": "R4",
            },
            "insurance_apis": {
                "INSURANCE_API_KEY": "${INSURANCE_API_KEY}",
                "PAYER_PORTAL_URL": "${PAYER_PORTAL_URL}",
            },
            "communication_services": {
                "EMAIL_API_KEY": "${EMAIL_API_KEY}",
                "SMS_API_KEY": "${SMS_API_KEY}",
            },
        }

        return env_vars.get(server_type, {})

    def _identify_auth_requirements(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify authentication requirements for tools"""

        auth_requirements = []

        for tool in tools:
            catalog_info = tool.get("catalog_info", {})
            if catalog_info.get("auth_required", False):
                auth_requirements.append({
                    "tool": tool["name"],
                    "auth_type": "api_key",  # Default
                    "env_var": f"{tool['name'].upper()}_API_KEY",
                    "description": f"API key for {tool['name']} integration",
                })

        return auth_requirements

    def _list_required_env_vars(self, tools: List[Dict[str, Any]]) -> List[str]:
        """List all required environment variables"""

        env_vars = set()
        server_requirements = self._identify_server_requirements(tools)

        for server_type in server_requirements.keys():
            server_env_vars = self._get_server_env_vars(server_type)
            env_vars.update(server_env_vars.keys())

        return sorted(list(env_vars))

    def _create_integration_instructions(self, tools: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create integration instructions for MCP tools"""

        return {
            "setup": [
                "1. Install required MCP servers for each tool category",
                "2. Configure environment variables for authentication",
                "3. Set up MCP server configurations",
                "4. Test connectivity to external services",
            ],
            "configuration": [
                "Configure MCP servers in ai-studio settings",
                "Set up STDIO or SSE connections as appropriate",
                "Configure timeout and retry settings",
                "Enable mock fallback for development",
            ],
            "testing": [
                "Test each MCP tool individually",
                "Verify authentication and connectivity",
                "Test error handling and timeouts",
                "Validate mock fallback functionality",
            ],
            "troubleshooting": [
                "Check server logs for connection issues",
                "Verify environment variable configuration",
                "Test network connectivity to external services",
                "Enable debug logging for detailed error information",
            ],
        }

    def _generate_fallback_options(self, tools: List[Dict[str, Any]], mock_status: Dict[str, Any]) -> Dict[str, Any]:
        """Generate fallback options for unavailable tools"""

        api_alternatives = []
        mock_alternatives = []
        simplified = []
        strategies = []

        for tool in tools:
            tool_name = tool["name"]
            catalog_info = tool.get("catalog_info", {})

            # API alternatives
            if catalog_info.get("complexity") == "simple":
                api_alternatives.append({
                    "tool": tool_name,
                    "alternative": "genesis:api_request",
                    "description": f"Use direct HTTP API instead of MCP for {tool_name}",
                })

            # Mock alternatives
            if tool_name in mock_status.get("available", []):
                mock_alternatives.append({
                    "tool": tool_name,
                    "approach": "mock_template",
                    "description": f"Use mock template for {tool_name} during development",
                })

        # Simplified approaches
        if len(tools) > 5:
            simplified.append("Reduce tool count by combining similar functions")
            simplified.append("Use generic API components instead of specialized MCP tools")

        # Development strategies
        if mock_status.get("coverage_percentage", 0) > 70:
            strategies.append("Start development with mock servers, migrate to live servers later")
        else:
            strategies.append("Begin with API-based integration, add MCP tools incrementally")

        strategies.append("Implement graceful degradation for unavailable tools")
        strategies.append("Use circuit breaker pattern for external service reliability")

        return {
            "api_alternatives": api_alternatives,
            "mock_alternatives": mock_alternatives,
            "simplified": simplified,
            "strategies": strategies,
        }