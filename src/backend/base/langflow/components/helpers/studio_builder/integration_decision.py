"""Integration Decision Tool for AI Studio Agent Builder - Helps decide between API and MCP."""

from typing import Dict, List, Optional
from langflow.custom.custom_component.component import Component
from langflow.inputs import MessageTextInput, BoolInput
from langflow.io import Output
from langflow.schema.data import Data
from langflow.logging import logger


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
            decision = self._analyze_requirements()
            guidance = self._generate_guidance(decision)
            examples = self._get_examples(decision)

            return Data(data={
                "success": True,
                "decision": decision,
                "guidance": guidance,
                "examples": examples,
                "conversation_response": self._format_response(decision, guidance, examples)
            })

        except Exception as e:
            logger.error(f"Error in integration decision: {e}")
            return Data(data={
                "success": False,
                "error": str(e)
            })

    def _analyze_requirements(self) -> Dict:
        """Analyze requirements to determine best approach."""
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

        # Decision logic
        if factors["has_mcp"]:
            component_type = "genesis:mcp_tool"
            reason = "You have an MCP server available, which provides better integration capabilities"
        elif factors["is_simple_api"] and factors["has_api_details"]:
            component_type = "genesis:api_request"
            reason = "This is a straightforward API integration with known endpoints"
        elif factors["is_healthcare"] or factors["is_complex"] or factors["needs_state"]:
            component_type = "genesis:mcp_tool"
            reason = "This complex integration would benefit from MCP's capabilities (can use mock mode)"
        else:
            component_type = "genesis:api_request"
            reason = "This appears to be a simple integration suitable for direct API calls"

        return {
            "recommended_component": component_type,
            "reason": reason,
            "factors": factors
        }

    def _generate_guidance(self, decision: Dict) -> Dict:
        """Generate specific guidance for the chosen approach."""
        component_type = decision["recommended_component"]

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
        """Format a conversational response for the user."""
        component_type = decision["recommended_component"]
        component_name = "API Request" if component_type == "genesis:api_request" else "MCP Tool"

        response = f"""Based on your integration needs, I recommend using **{component_name}**.

**Why this choice:**
{decision['reason']}

**How to configure it:**
"""

        for step in guidance["setup_steps"]:
            response += f"• {step}\n"

        response += f"""
**This approach is best for:**
"""
        for use_case in guidance["best_for"]:
            response += f"• {use_case}\n"

        response += f"""
**Example configuration:**
```yaml
{self._dict_to_yaml(guidance['configuration_template'])}
```

Would you like to proceed with this integration approach?"""

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