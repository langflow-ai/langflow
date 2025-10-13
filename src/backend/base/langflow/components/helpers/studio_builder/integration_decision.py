"""Integration Decision Tool for AI Studio Agent Builder - Helps decide between API and MCP."""

import asyncio
from typing import Dict, List, Optional
from langflow.custom.custom_component.component import Component
from langflow.inputs import MessageTextInput, BoolInput
from langflow.io import Output
from langflow.schema.data import Data
from langflow.logging import logger
from langflow.components.helpers.studio_builder.api_client import SpecAPIClient


class IntegrationDecision(Component):
    """Helps users decide between API and MCP tool integration approaches."""

    display_name = "Integration Decision"
    description = "Guides decision between API Request and MCP Tool components"
    icon = "git-branch"
    name = "IntegrationDecision"
    category = "Helpers"

    inputs = [
        MessageTextInput(
            name="integration_description",
            display_name="Integration Description",
            info="Describe what you need to integrate with",
            required=True,
            tool_mode=True,
        ),
        BoolInput(
            name="has_mcp_server",
            display_name="Has MCP Server",
            info="Does the user have an MCP server available?",
            value=False,
            tool_mode=True,
        ),
        MessageTextInput(
            name="api_details",
            display_name="API Details",
            info="Known API endpoints, authentication, etc.",
            required=False,
            tool_mode=True,
        ),
        BoolInput(
            name="needs_state_management",
            display_name="Needs State Management",
            info="Does the integration need to maintain state?",
            value=False,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Integration Decision", name="decision", method="decide"),
    ]

    def decide(self) -> Data:
        """Decide on the best integration approach."""
        try:
            # First check available components from API
            available_components = self._get_available_components()

            decision = self._analyze_requirements(available_components)
            guidance = self._generate_guidance(decision)
            examples = self._get_examples(decision)

            return Data(data={
                "success": True,
                "decision": decision,
                "guidance": guidance,
                "examples": examples,
                "available_integration_components": self._filter_integration_components(available_components),
                "conversation_response": self._format_response(decision, guidance, examples)
            })

        except Exception as e:
            logger.error(f"Error in integration decision: {e}")
            return Data(data={
                "success": False,
                "error": str(e)
            })

    def _get_available_components(self) -> Dict:
        """Get available components from the API."""
        try:
            async def _fetch_components():
                async with SpecAPIClient() as client:
                    return await client.get_available_components()

            return asyncio.run(_fetch_components())
        except Exception as e:
            logger.warning(f"Could not fetch components from API: {e}")
            # Return minimal set of known integration components
            return {
                "genesis:api_request": {"name": "API Request", "category": "Integration"},
                "genesis:mcp_tool": {"name": "MCP Tool", "category": "Tool"}
            }

    def _filter_integration_components(self, components: Dict) -> List[str]:
        """Filter components to show only integration-related ones."""
        integration_types = []
        for comp_type, comp_info in components.items():
            if any(keyword in comp_type.lower() for keyword in ["api", "mcp", "tool", "request", "webhook"]):
                integration_types.append(comp_type)
        return integration_types

    def _analyze_requirements(self, available_components: Dict) -> Dict:
        """Analyze requirements and provide guidance for both API and MCP approaches."""
        description_lower = self.integration_description.lower()

        # Decision factors
        factors = {
            "has_mcp": self.has_mcp_server,
            "has_api_details": bool(self.api_details),
            "needs_state": self.needs_state_management,
            "is_healthcare": any(term in description_lower for term in
                                ["healthcare", "medical", "patient", "ehr", "fhir", "hl7"]),
            "is_complex": any(term in description_lower for term in
                             ["workflow", "multi-step", "complex", "orchestration"]),
            "is_simple_api": any(term in description_lower for term in
                                ["rest", "api", "endpoint", "http", "webhook"])
        }

        # Check what's actually available
        has_api_request = "genesis:api_request" in available_components
        has_mcp_tool = "genesis:mcp_tool" in available_components

        # PRIMARY RECOMMENDATION: Always provide both options with clear guidance
        api_score = 0
        mcp_score = 0

        # Scoring for API Request
        if factors["is_simple_api"]:
            api_score += 3
        if factors["has_api_details"]:
            api_score += 2
        if not factors["is_complex"]:
            api_score += 1
        if not factors["needs_state"]:
            api_score += 1

        # Scoring for MCP Tool
        if factors["is_healthcare"]:
            mcp_score += 3
        if factors["is_complex"]:
            mcp_score += 2
        if factors["needs_state"]:
            mcp_score += 2
        if factors["has_mcp"]:
            mcp_score += 1

        # Determine primary recommendation
        if mcp_score > api_score:
            primary_recommendation = "genesis:mcp_tool"
            primary_reason = "Healthcare complexity and state management favor MCP approach"
        elif api_score > mcp_score:
            primary_recommendation = "genesis:api_request"
            primary_reason = "Simple API integration with known endpoints is most efficient"
        else:
            # Tie - default to MCP for healthcare, API for others
            if factors["is_healthcare"]:
                primary_recommendation = "genesis:mcp_tool"
                primary_reason = "Healthcare integrations benefit from MCP's specialized capabilities"
            else:
                primary_recommendation = "genesis:api_request"
                primary_reason = "API Request provides straightforward integration"

        return {
            "primary_recommendation": primary_recommendation,
            "primary_reason": primary_reason,
            "api_score": api_score,
            "mcp_score": mcp_score,
            "factors": factors,
            "both_available": has_api_request and has_mcp_tool,
            "comparison": {
                "api_pros": [
                    "Direct HTTP integration",
                    "Simple configuration",
                    "Fast performance",
                    "Standard authentication"
                ],
                "api_cons": [
                    "Limited business logic",
                    "Manual error handling",
                    "No state management",
                    "Harder to extend"
                ],
                "mcp_pros": [
                    "Healthcare-specific logic",
                    "Mock templates for development",
                    "State management capabilities",
                    "Extensible architecture"
                ],
                "mcp_cons": [
                    "More complex setup",
                    "Requires MCP server (or mock mode)",
                    "Additional abstraction layer",
                    "Development overhead"
                ]
            }
        }

    def _generate_guidance(self, decision: Dict) -> Dict:
        """Generate specific guidance for both API and MCP approaches."""
        primary_component = decision["primary_recommendation"]
        comparison = decision["comparison"]

        # Provide guidance for both approaches
        guidance = {
            "primary_recommendation": {
                "component": "API Request" if primary_component == "genesis:api_request" else "MCP Tool",
                "reason": decision["primary_reason"],
                "score": decision["api_score"] if primary_component == "genesis:api_request" else decision["mcp_score"]
            },
            "api_request_guidance": {
                "component": "API Request",
                "when_to_use": "Simple HTTP API integrations with known endpoints",
                "pros": comparison["api_pros"],
                "cons": comparison["api_cons"],
                "setup_steps": [
                    "Define the HTTP method (GET, POST, etc.)",
                    "Specify the endpoint URL",
                    "Configure headers (including authentication)",
                    "Set up request body if needed",
                    "Configure timeout settings"
                ],
                "configuration_template": {
                    "type": "genesis:api_request",
                    "config": {
                        "method": "POST",
                        "url_input": "https://api.healthcare.gov/v1/endpoint",
                        "headers": [
                            {"key": "Authorization", "value": "${API_KEY}"},
                            {"key": "Content-Type", "value": "application/json"}
                        ],
                        "body": [
                            {"key": "patient_id", "value": "${PATIENT_ID}"}
                        ],
                        "timeout": 30
                    }
                }
            },
            "mcp_tool_guidance": {
                "component": "MCP Tool",
                "when_to_use": "Complex healthcare integrations requiring business logic",
                "pros": comparison["mcp_pros"],
                "cons": comparison["mcp_cons"],
                "setup_steps": [
                    "Define the tool name identifier",
                    "Provide tool description for the agent",
                    "Configure MCP server connection (if available)",
                    "Set up mock response for development",
                    "Define expected input/output schemas"
                ],
                "configuration_template": {
                    "type": "genesis:mcp_tool",
                    "config": {
                        "tool_name": "healthcare_integration_tool",
                        "description": "Healthcare-specific integration tool with FHIR/HL7 support",
                        "mock_response": {
                            "status": "success",
                            "data": {
                                "patient_id": "PAT123",
                                "fhir_compliant": True,
                                "hipaa_status": "compliant"
                            }
                        }
                    }
                },
                "development_mode": "Use mock templates for development without actual MCP servers"
            }
        }

        return guidance

    def _generate_guidance_old(self, decision: Dict) -> Dict:
        """OLD VERSION - Generate specific guidance for the chosen approach."""
        component_type = decision.get("recommended_component", "genesis:api_request")

        if component_type == "genesis:api_request":
            return {
                "component": "API Request",
                "setup_steps": [
                    "Define the HTTP method (GET, POST, etc.)",
                    "Specify the endpoint URL",
                    "Configure headers (including authentication)",
                    "Set up request body if needed",
                    "Configure timeout settings"
                ],
                "configuration_template": {
                    "type": "genesis:api_request",
                    "config": {
                        "method": "POST",
                        "url_input": "https://api.example.com/endpoint",
                        "headers": [
                            {"key": "Authorization", "value": "${API_KEY}"},
                            {"key": "Content-Type", "value": "application/json"}
                        ],
                        "body": [],
                        "timeout": 30
                    }
                },
                "best_for": [
                    "Simple REST API calls",
                    "Webhooks",
                    "Direct HTTP integrations",
                    "Public APIs with standard auth"
                ]
            }
        else:  # genesis:mcp_tool
            return {
                "component": "MCP Tool",
                "setup_steps": [
                    "Define the tool name identifier",
                    "Provide tool description for the agent",
                    "Configure MCP server connection (if available)",
                    "Set up mock response for development",
                    "Define expected input/output schemas"
                ],
                "configuration_template": {
                    "type": "genesis:mcp_tool",
                    "config": {
                        "tool_name": "integration_tool",
                        "description": "Tool description for agent context",
                        "mock_response": {
                            "status": "success",
                            "data": {}
                        }
                    }
                },
                "best_for": [
                    "Complex healthcare integrations",
                    "Multi-step workflows",
                    "Stateful operations",
                    "Tools requiring business logic",
                    "Development without actual servers (mock mode)"
                ]
            }

    def _get_examples(self, decision: Dict) -> List[Dict]:
        """Get relevant examples for the chosen approach."""
        component_type = decision["recommended_component"]

        if component_type == "genesis:api_request":
            return [
                {
                    "name": "Insurance Eligibility Check",
                    "description": "Direct API call to insurance provider",
                    "config": {
                        "method": "POST",
                        "url_input": "https://api.insurer.com/eligibility",
                        "headers": [{"key": "X-API-Key", "value": "${INSURER_API_KEY}"}]
                    }
                },
                {
                    "name": "Send Notification",
                    "description": "Webhook to notification service",
                    "config": {
                        "method": "POST",
                        "url_input": "https://hooks.slack.com/services/...",
                        "body": [{"key": "text", "value": "Notification message"}]
                    }
                }
            ]
        else:  # MCP Tool examples
            return [
                {
                    "name": "EHR Integration",
                    "description": "Complex EHR system integration",
                    "config": {
                        "tool_name": "ehr_patient_lookup",
                        "description": "Search and retrieve patient records from EHR"
                    }
                },
                {
                    "name": "Prior Auth Processor",
                    "description": "Multi-payer authorization system",
                    "config": {
                        "tool_name": "prior_auth_submit",
                        "description": "Submit and track prior authorization requests"
                    }
                }
            ]

    def _format_response(self, decision: Dict, guidance: Dict, examples: List[Dict]) -> str:
        """Format a comprehensive conversational response for the user."""
        primary = guidance["primary_recommendation"]
        api_guidance = guidance["api_request_guidance"]
        mcp_guidance = guidance["mcp_tool_guidance"]

        response = f"""🔧 **Integration Decision Analysis**

**Primary Recommendation: {primary['component']}** (Score: {primary['score']})
**Reason:** {primary['reason']}

## 🌐 API Request Approach
**When to use:** {api_guidance['when_to_use']}

**Pros:**
"""
        for pro in api_guidance['pros']:
            response += f"✅ {pro}\n"

        response += f"""
**Cons:**
"""
        for con in api_guidance['cons']:
            response += f"❌ {con}\n"

        response += f"""
**Configuration:**
```yaml
{self._dict_to_yaml(api_guidance['configuration_template'])}
```

## 🔌 MCP Tool Approach
**When to use:** {mcp_guidance['when_to_use']}

**Pros:**
"""
        for pro in mcp_guidance['pros']:
            response += f"✅ {pro}\n"

        response += f"""
**Cons:**
"""
        for con in mcp_guidance['cons']:
            response += f"❌ {con}\n"

        response += f"""
**Configuration:**
```yaml
{self._dict_to_yaml(mcp_guidance['configuration_template'])}
```

**💡 Development Note:** {mcp_guidance['development_mode']}

## 🎯 Recommendation Summary
For your **{self.integration_description}** integration, I recommend **{primary['component']}** because {primary['reason'].lower()}.

Both approaches are available - would you like to proceed with **{primary['component']}** or explore the alternative?"""

        return response

    def _dict_to_yaml(self, data: dict, indent: int = 0) -> str:
        """Convert dict to YAML-like string for display."""
        yaml_str = ""
        for key, value in data.items():
            yaml_str += " " * indent + f"{key}: "
            if isinstance(value, dict):
                yaml_str += "\n" + self._dict_to_yaml(value, indent + 2)
            elif isinstance(value, list):
                yaml_str += "\n"
                for item in value:
                    yaml_str += " " * (indent + 2) + f"- "
                    if isinstance(item, dict):
                        first_key = list(item.keys())[0] if item else ""
                        yaml_str += f"{first_key}: {item[first_key]}\n" if first_key else "\n"
                    else:
                        yaml_str += f"{item}\n"
            else:
                yaml_str += f"{value}\n"
        return yaml_str