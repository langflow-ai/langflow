"""MCP Framework for AI Studio Agent Builder - Unified framework for user/catalog/mock MCP tools."""

import asyncio
import json
from typing import Dict, List, Any, Optional, Union
from langflow.custom.custom_component.component import Component
from langflow.inputs import MessageTextInput, BoolInput, MultilineInput
from langflow.io import Output
from langflow.schema.data import Data
from langflow.logging import logger

# Import the actual mock tool templates from the MCP component
try:
    from langflow.components.agents.mcp_component import MOCK_TOOL_TEMPLATES
except ImportError:
    logger.warning("Could not import MOCK_TOOL_TEMPLATES from mcp_component")
    MOCK_TOOL_TEMPLATES = {}


class MCPFramework(Component):
    """Unified framework for MCP tools from user input, catalog, or mock sources."""

    display_name = "MCP Framework"
    description = "Unified framework for selecting and configuring MCP tools from user specs, catalog, or mock templates"
    icon = "layers"
    name = "MCPFramework"
    category = "Helpers"

    inputs = [
        MessageTextInput(
            name="tool_request",
            display_name="Tool Request",
            info="Describe the MCP tool you need or provide JSON specification",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="tool_source",
            display_name="Tool Source",
            info="Source preference: 'user', 'catalog', 'mock', or 'auto' to decide automatically",
            value="auto",
            tool_mode=True,
        ),
        MultilineInput(
            name="user_tool_spec",
            display_name="User Tool Specification",
            info="Optional: JSON specification for custom user-provided MCP tool",
            required=False,
            tool_mode=True,
        ),
        BoolInput(
            name="include_mock_fallback",
            display_name="Include Mock Fallback",
            info="Whether to provide mock fallback for development",
            value=True,
            tool_mode=True,
        ),
        BoolInput(
            name="validate_tool_spec",
            display_name="Validate Tool Spec",
            info="Whether to validate the generated tool specification",
            value=True,
            tool_mode=True,
        ),
        BoolInput(
            name="discovery_mode",
            display_name="Discovery Mode",
            info="Browse available tools instead of configuring specific tool",
            value=False,
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="MCP Tool Configuration", name="mcp_config", method="generate_mcp_config"),
    ]

    def generate_mcp_config(self) -> Data:
        """Generate MCP tool configuration from user/catalog/mock sources."""
        try:
            # Handle discovery mode - browse available tools
            if self.discovery_mode:
                return self._handle_discovery_mode()

            # Parse tool request for configuration mode
            tool_request = self.tool_request.strip()
            source_preference = self.tool_source.lower()

            # Determine tool source and generate configuration
            if source_preference == "user" and self.user_tool_spec:
                config = self._process_user_tool(tool_request, self.user_tool_spec)
            elif source_preference == "catalog":
                config = self._process_catalog_tool(tool_request)
            elif source_preference == "mock":
                config = self._process_mock_tool(tool_request)
            else:  # auto mode
                config = self._auto_select_tool_source(tool_request)

            # Add mock fallback if requested
            if self.include_mock_fallback and config.get("success"):
                config = self._add_mock_fallback(config)

            # Validate if requested
            if self.validate_tool_spec and config.get("success"):
                config = self._validate_tool_configuration(config)

            # Generate conversation response
            config["conversation_response"] = self._format_framework_response(config)

            return Data(data=config)

        except Exception as e:
            logger.error(f"Error in MCP framework: {e}")
            return Data(data={
                "success": False,
                "error": str(e),
                "tool_config": {},
                "message": "Failed to generate MCP tool configuration"
            })

    def _process_user_tool(self, request: str, user_spec: str) -> Dict[str, Any]:
        """Process user-provided MCP tool specification."""
        try:
            # Parse user specification
            if user_spec.strip():
                try:
                    spec = json.loads(user_spec) if isinstance(user_spec, str) else user_spec
                except json.JSONDecodeError:
                    return {
                        "success": False,
                        "error": "Invalid JSON format in user tool specification",
                        "source": "user"
                    }
            else:
                # Generate from request description
                spec = self._generate_tool_spec_from_description(request)

            # Validate and normalize user spec
            normalized_spec = self._normalize_user_tool_spec(spec)

            return {
                "success": True,
                "source": "user",
                "tool_config": normalized_spec,
                "original_spec": spec,
                "message": f"Generated user MCP tool: {normalized_spec.get('tool_name', 'custom_tool')}"
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Error processing user tool: {e}",
                "source": "user"
            }

    def _process_catalog_tool(self, request: str) -> Dict[str, Any]:
        """Process tool from existing catalog/mock templates."""
        # Get existing mock templates from mcp_component.py structure
        catalog_tools = self._get_catalog_tools()

        # Find best match
        best_match = self._find_best_catalog_match(request, catalog_tools)

        if best_match:
            tool_config = self._convert_catalog_to_config(best_match["tool_id"], best_match["tool_data"])
            return {
                "success": True,
                "source": "catalog",
                "tool_config": tool_config,
                "match_score": best_match["score"],
                "matched_tool": best_match["tool_id"],
                "message": f"Found catalog tool: {best_match['tool_data']['name']}"
            }
        else:
            return {
                "success": False,
                "error": "No suitable tool found in catalog",
                "source": "catalog",
                "available_tools": list(catalog_tools.keys())
            }

    def _process_mock_tool(self, request: str) -> Dict[str, Any]:
        """Generate a mock tool based on request description."""
        mock_config = self._generate_mock_tool_config(request)

        return {
            "success": True,
            "source": "mock",
            "tool_config": mock_config,
            "message": f"Generated mock tool: {mock_config.get('tool_name', 'mock_tool')}"
        }

    def _auto_select_tool_source(self, request: str) -> Dict[str, Any]:
        """Automatically select the best tool source based on request."""
        request_lower = request.lower()

        # Decision logic for source selection
        if self.user_tool_spec and self.user_tool_spec.strip():
            # User provided specification - use it
            return self._process_user_tool(request, self.user_tool_spec)

        # Check catalog first for existing tools
        catalog_result = self._process_catalog_tool(request)
        if catalog_result.get("success") and catalog_result.get("match_score", 0) > 0.7:
            # High confidence catalog match
            catalog_result["auto_selection_reason"] = "High confidence match in catalog"
            return catalog_result

        # Healthcare-specific keywords suggest catalog/mock
        healthcare_keywords = [
            "ehr", "emr", "fhir", "hl7", "patient", "clinical", "medical", "healthcare",
            "prior authorization", "eligibility", "claims", "pharmacy", "drug",
            "icd", "cpt", "diagnosis", "procedure", "medication"
        ]

        if any(keyword in request_lower for keyword in healthcare_keywords):
            # Try catalog first, then mock
            if catalog_result.get("success"):
                catalog_result["auto_selection_reason"] = "Healthcare domain - using catalog"
                return catalog_result
            else:
                mock_result = self._process_mock_tool(request)
                mock_result["auto_selection_reason"] = "Healthcare domain - generated mock"
                return mock_result

        # Default to mock for custom requirements
        mock_result = self._process_mock_tool(request)
        mock_result["auto_selection_reason"] = "Custom requirement - generated mock"
        return mock_result

    def _get_catalog_tools(self) -> Dict[str, Dict]:
        """Get available tools from catalog (based on actual mock templates)."""
        # Use the actual MOCK_TOOL_TEMPLATES from mcp_component.py
        catalog_tools = {}

        for tool_id, template in MOCK_TOOL_TEMPLATES.items():
            # Convert mock template to catalog format
            catalog_tools[tool_id] = {
                "name": template["name"],
                "description": template["description"],
                "category": self._infer_category_from_tool(tool_id, template),
                "domains": self._infer_domains_from_tool(tool_id, template),
                "complexity": self._infer_complexity_from_tool(template),
                "input_schema": template.get("input_schema", {}),
                "mock_response": template.get("mock_response", {}),
                "original_template": template  # Keep reference to original
            }

        return catalog_tools

    def _infer_category_from_tool(self, tool_id: str, template: Dict) -> str:
        """Infer category from tool ID and template."""
        if "ehr" in tool_id or "patient" in tool_id:
            return "Healthcare Integration"
        elif "pharmacy" in tool_id or "claims" in tool_id:
            return "Pharmacy & Claims"
        elif "insurance" in tool_id or "eligibility" in tool_id:
            return "Insurance & Benefits"
        elif "prior_auth" in tool_id or "authorization" in tool_id:
            return "Healthcare Workflow"
        elif "coding" in tool_id or "icd" in tool_id or "cpt" in tool_id:
            return "Medical Coding"
        else:
            return "Healthcare Tools"

    def _infer_domains_from_tool(self, tool_id: str, template: Dict) -> List[str]:
        """Infer domains from tool ID and template."""
        domains = []

        # Extract domains from tool ID
        if "ehr" in tool_id:
            domains.extend(["ehr", "patient_records", "clinical_data"])
        if "pharmacy" in tool_id:
            domains.extend(["pharmacy", "medications", "drug_interactions"])
        if "insurance" in tool_id:
            domains.extend(["insurance", "eligibility", "benefits"])
        if "prior_auth" in tool_id:
            domains.extend(["prior_authorization", "clinical_review"])
        if "claims" in tool_id:
            domains.extend(["claims", "billing", "reimbursement"])

        # Extract domains from description
        description_lower = template.get("description", "").lower()
        if "fhir" in description_lower:
            domains.append("fhir")
        if "hipaa" in description_lower:
            domains.append("hipaa")
        if "coding" in description_lower:
            domains.append("medical_coding")

        return list(set(domains)) if domains else ["healthcare"]

    def _infer_complexity_from_tool(self, template: Dict) -> str:
        """Infer complexity from template structure."""
        input_schema = template.get("input_schema", {})
        num_inputs = len(input_schema)

        if num_inputs <= 2:
            return "low"
        elif num_inputs <= 4:
            return "medium"
        else:
            return "high"

    def _find_best_catalog_match(self, request: str, catalog_tools: Dict) -> Optional[Dict]:
        """Find the best matching tool from catalog."""
        request_lower = request.lower()
        best_match = None
        best_score = 0

        for tool_id, tool_data in catalog_tools.items():
            score = 0

            # Check name match
            if any(word in tool_data["name"].lower() for word in request_lower.split()):
                score += 0.3

            # Check description match
            if any(word in tool_data["description"].lower() for word in request_lower.split()):
                score += 0.2

            # Check domain match
            for domain in tool_data.get("domains", []):
                if domain.lower() in request_lower:
                    score += 0.4

            # Specific keyword matching
            if "ehr" in request_lower and "ehr" in tool_id:
                score += 0.5
            if "prior auth" in request_lower and "prior_auth" in tool_id:
                score += 0.5
            if "coding" in request_lower and "coding" in tool_id:
                score += 0.5
            if "pharmacy" in request_lower and "pharmacy" in tool_id:
                score += 0.5
            if "eligibility" in request_lower and "eligibility" in tool_id:
                score += 0.5

            if score > best_score:
                best_score = score
                best_match = {
                    "tool_id": tool_id,
                    "tool_data": tool_data,
                    "score": score
                }

        return best_match if best_score > 0.3 else None

    def _convert_catalog_to_config(self, tool_id: str, tool_data: Dict) -> Dict[str, Any]:
        """Convert catalog tool to genesis:mcp_tool configuration."""
        return {
            "type": "genesis:mcp_tool",
            "tool_name": tool_id,
            "description": tool_data["description"],
            "input_schema": tool_data.get("input_schema", {}),
            "mock_response": tool_data.get("mock_response", {}),
            "category": tool_data.get("category", "Integration"),
            "complexity": tool_data.get("complexity", "medium"),
            "healthcare_domains": tool_data.get("domains", []),
            "source": "catalog"
        }

    def _generate_mock_tool_config(self, request: str) -> Dict[str, Any]:
        """Generate a mock tool configuration from request description."""
        # Extract key information from request
        tool_name = self._extract_tool_name(request)

        # Generate basic mock configuration
        mock_config = {
            "type": "genesis:mcp_tool",
            "tool_name": tool_name,
            "description": f"Mock tool for {request}",
            "input_schema": self._generate_input_schema(request),
            "mock_response": self._generate_mock_response(request),
            "category": "Custom Mock",
            "complexity": "medium",
            "source": "mock_generated"
        }

        return mock_config

    def _extract_tool_name(self, request: str) -> str:
        """Extract a suitable tool name from the request."""
        # Simple extraction logic - can be enhanced
        words = request.lower().split()
        # Remove common words
        filtered_words = [w for w in words if w not in ["a", "an", "the", "for", "to", "with", "tool", "integration"]]
        # Take first few significant words
        name_words = filtered_words[:3] if len(filtered_words) >= 3 else filtered_words
        return "_".join(name_words) + "_tool"

    def _generate_input_schema(self, request: str) -> Dict[str, Any]:
        """Generate input schema based on request context."""
        request_lower = request.lower()
        schema = {}

        # Healthcare-specific schemas
        if any(keyword in request_lower for keyword in ["patient", "clinical", "medical"]):
            schema["patient_id"] = {"type": "string", "description": "Patient identifier"}

        if "authorization" in request_lower:
            schema.update({
                "procedure_codes": {"type": "array", "items": {"type": "string"}},
                "diagnosis_codes": {"type": "array", "items": {"type": "string"}}
            })

        if "eligibility" in request_lower:
            schema.update({
                "insurance_id": {"type": "string", "description": "Insurance member ID"},
                "service_type": {"type": "string", "description": "Type of service"}
            })

        # Default schema if nothing specific detected
        if not schema:
            schema = {
                "input_data": {"type": "string", "description": "Input data for processing"},
                "options": {"type": "object", "description": "Optional parameters"}
            }

        return schema

    def _generate_mock_response(self, request: str) -> Dict[str, Any]:
        """Generate realistic mock response based on request context."""
        request_lower = request.lower()

        # Healthcare responses
        if "authorization" in request_lower:
            return {
                "authorization_id": "AUTH-2024-" + "".join(str(i) for i in range(6)),
                "status": "approved",
                "approval_date": "2024-10-13",
                "valid_through": "2024-12-31"
            }

        if "eligibility" in request_lower:
            return {
                "eligible": True,
                "coverage_percentage": 80,
                "deductible_remaining": "$250.00",
                "verification_date": "2024-10-13"
            }

        if "patient" in request_lower:
            return {
                "patient_found": True,
                "last_visit": "2024-09-15",
                "active_conditions": ["Hypertension", "Type 2 Diabetes"],
                "current_medications": 3
            }

        # Default response
        return {
            "status": "success",
            "data": {"processed": True, "timestamp": "2024-10-13T10:30:00Z"},
            "message": "Mock response generated successfully"
        }

    def _normalize_user_tool_spec(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize user-provided tool specification to standard format."""
        normalized = {
            "type": "genesis:mcp_tool",
            "tool_name": spec.get("tool_name", spec.get("name", "user_custom_tool")),
            "description": spec.get("description", "User-provided custom MCP tool"),
            "source": "user_provided"
        }

        # Copy other fields
        for field in ["input_schema", "mock_response", "category", "complexity"]:
            if field in spec:
                normalized[field] = spec[field]

        return normalized

    def _generate_tool_spec_from_description(self, description: str) -> Dict[str, Any]:
        """Generate a tool spec from text description."""
        return {
            "tool_name": self._extract_tool_name(description),
            "description": description,
            "input_schema": self._generate_input_schema(description),
            "mock_response": self._generate_mock_response(description)
        }

    def _add_mock_fallback(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Add mock fallback configuration for development."""
        if config.get("success") and "tool_config" in config:
            tool_config = config["tool_config"]

            # Ensure mock response exists
            if "mock_response" not in tool_config or not tool_config["mock_response"]:
                tool_config["mock_response"] = self._generate_mock_response(
                    tool_config.get("description", "")
                )

            # Add fallback configuration
            tool_config["fallback_config"] = {
                "enable_mock_fallback": True,
                "mock_timeout_ms": 5000,
                "development_mode": True,
                "mock_delay_ms": 100  # Simulate network delay
            }

            config["mock_fallback_added"] = True

        return config

    def _validate_tool_configuration(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the generated tool configuration."""
        if not config.get("success"):
            return config

        tool_config = config.get("tool_config", {})
        validation_errors = []

        # Required fields validation
        required_fields = ["type", "tool_name", "description"]
        for field in required_fields:
            if field not in tool_config:
                validation_errors.append(f"Missing required field: {field}")

        # Type validation
        if tool_config.get("type") != "genesis:mcp_tool":
            validation_errors.append("Tool type must be 'genesis:mcp_tool'")

        # Tool name format validation
        tool_name = tool_config.get("tool_name", "")
        if not tool_name.replace("_", "").replace("-", "").isalnum():
            validation_errors.append("Tool name should contain only alphanumeric characters, underscores, and hyphens")

        # Schema validation
        input_schema = tool_config.get("input_schema", {})
        if input_schema and not isinstance(input_schema, dict):
            validation_errors.append("Input schema must be a dictionary")

        # Mock response validation
        mock_response = tool_config.get("mock_response", {})
        if mock_response and not isinstance(mock_response, dict):
            validation_errors.append("Mock response must be a dictionary")

        # Add validation results
        config["validation"] = {
            "valid": len(validation_errors) == 0,
            "errors": validation_errors,
            "warnings": []
        }

        return config

    def _format_framework_response(self, config: Dict[str, Any]) -> str:
        """Format a comprehensive response for the user."""
        if not config.get("success"):
            return f"❌ **MCP Tool Configuration Failed**\n\nError: {config.get('error', 'Unknown error')}"

        tool_config = config.get("tool_config", {})
        source = config.get("source", "unknown")

        response = f"🔧 **MCP Tool Configuration Generated**\n\n"
        response += f"**Tool Name**: {tool_config.get('tool_name', 'Unknown')}\n"
        response += f"**Description**: {tool_config.get('description', 'No description')}\n"
        response += f"**Source**: {source.title()}\n"

        # Add source-specific information
        if source == "catalog":
            response += f"**Catalog Match**: {config.get('matched_tool', 'N/A')} (confidence: {config.get('match_score', 0):.1%})\n"
        elif source == "user":
            response += "**User Specification**: Custom tool from user input\n"
        elif source == "mock":
            response += "**Mock Generated**: Auto-generated mock tool\n"

        if config.get("auto_selection_reason"):
            response += f"**Auto Selection**: {config['auto_selection_reason']}\n"

        response += "\n**Configuration**:\n"
        response += f"```yaml\n"
        response += f"type: {tool_config.get('type', 'genesis:mcp_tool')}\n"
        response += f"tool_name: {tool_config.get('tool_name')}\n"
        response += f"description: {tool_config.get('description')}\n"

        if tool_config.get("input_schema"):
            response += f"input_schema:\n"
            for param, details in tool_config.get("input_schema", {}).items():
                response += f"  {param}: {details.get('type', 'string')}\n"

        response += "```\n\n"

        # Mock fallback information
        if config.get("mock_fallback_added"):
            response += "✅ **Mock Fallback**: Development mode enabled with automatic fallback\n"

        # Validation results
        validation = config.get("validation", {})
        if validation:
            if validation.get("valid"):
                response += "✅ **Validation**: Configuration passed all validation checks\n"
            else:
                response += "❌ **Validation Issues**:\n"
                for error in validation.get("errors", []):
                    response += f"• {error}\n"

        response += "\n**Ready for use in agent specification** 🚀"

        return response

    def _handle_discovery_mode(self) -> Data:
        """Handle discovery mode - browse available MCP tools like MCP_CATALOG."""
        try:
            # Get all available tools from catalog
            catalog_tools = self._get_catalog_tools()

            # Filter by search query if provided
            if self.tool_request and self.tool_request.strip():
                filtered_tools = {}
                query_lower = self.tool_request.lower()
                for tool_id, tool_info in catalog_tools.items():
                    if (query_lower in tool_info["name"].lower() or
                        query_lower in tool_info["description"].lower() or
                        any(query_lower in domain for domain in tool_info.get("domains", []))):
                        filtered_tools[tool_id] = tool_info
                catalog_tools = filtered_tools

            # Process tools into discovery format (similar to MCP_CATALOG)
            processed_tools = self._process_tools_for_discovery(catalog_tools)

            # Generate catalog-style response
            catalog_info = {
                "total_tools": len(processed_tools),
                "discovery_mode": True,
                "tools": processed_tools,
                "search_query": self.tool_request or "all",
                "development_guidance": {
                    "current_state": "All tools are production-ready with mock templates",
                    "mock_mode": "Use mock templates for development and testing without actual MCP servers",
                    "production_readiness": "Tools are ready for production with seamless MCP server integration",
                    "testing_approach": "Specifications can be built and tested using mock responses",
                    "migration_path": "Automatic fallback to live servers when available"
                },
                "healthcare_categories": list(set(tool["category"] for tool in processed_tools.values()))
            }

            return Data(data={
                "success": True,
                "mode": "discovery",
                "catalog": catalog_info,
                "message": f"Found {len(processed_tools)} MCP tools",
                "conversation_response": self._format_discovery_response(catalog_info)
            })

        except Exception as e:
            logger.error(f"Error in discovery mode: {e}")
            return Data(data={
                "success": False,
                "mode": "discovery",
                "error": str(e),
                "catalog": {},
                "message": "Failed to load MCP tool catalog"
            })

    def _process_tools_for_discovery(self, catalog_tools: Dict) -> Dict[str, Dict]:
        """Process catalog tools for discovery display."""
        processed_tools = {}

        for tool_id, tool_data in catalog_tools.items():
            # Enhance with categorization for discovery
            category = self._categorize_discovery_tool(tool_id, tool_data)
            complexity = self._assess_discovery_complexity(tool_data)
            domains = self._extract_discovery_domains(tool_id, tool_data)

            processed_tools[tool_id] = {
                "name": tool_data.get("name", tool_id.replace("_", " ").title()),
                "description": tool_data.get("description", "Healthcare integration tool"),
                "category": category,
                "status": "production_ready",
                "mock_available": True,
                "healthcare_domains": domains,
                "complexity": complexity,
                "input_parameters": len(tool_data.get("input_schema", {})),
                "response_complexity": self._count_nested_structures(tool_data.get("mock_response", {}))
            }

        return processed_tools

    def _categorize_discovery_tool(self, tool_id: str, template: Dict) -> str:
        """Categorize tool for discovery display."""
        tool_lower = tool_id.lower()
        desc_lower = template.get("description", "").lower()

        if any(keyword in tool_lower for keyword in ["ehr", "patient", "medical", "clinical"]):
            return "Healthcare Integration"
        elif any(keyword in tool_lower for keyword in ["pharmacy", "drug", "medication"]):
            return "Pharmacy"
        elif any(keyword in tool_lower for keyword in ["insurance", "eligibility", "member"]):
            return "Insurance"
        elif any(keyword in tool_lower for keyword in ["survey", "call", "feedback"]):
            return "Patient Experience"
        elif any(keyword in tool_lower for keyword in ["symptom", "nlp", "sentiment"]):
            return "Clinical Analytics"
        elif "claims" in tool_lower:
            return "Claims Processing"
        else:
            return "Healthcare Tools"

    def _extract_discovery_domains(self, tool_id: str, template: Dict) -> List[str]:
        """Extract healthcare domains for discovery."""
        domains = []
        tool_lower = tool_id.lower()
        desc_lower = template.get("description", "").lower()

        domain_keywords = {
            "patient_records": ["patient", "ehr", "medical", "records"],
            "clinical_data": ["clinical", "diagnosis", "treatment"],
            "pharmacy": ["pharmacy", "drug", "medication", "prescription"],
            "insurance": ["insurance", "eligibility", "benefits", "coverage"],
            "prior_authorization": ["authorization", "prior", "auth"],
            "billing": ["billing", "claims", "payment"],
            "compliance": ["compliance", "hipaa", "audit"],
            "patient_experience": ["survey", "feedback", "call", "experience"],
            "analytics": ["sentiment", "nlp", "analysis", "metrics"],
            "clinical_review": ["review", "assessment", "evaluation"],
            "fhir": ["fhir", "hl7", "interoperability"]
        }

        for domain, keywords in domain_keywords.items():
            if any(keyword in tool_lower or keyword in desc_lower for keyword in keywords):
                domains.append(domain)

        return domains if domains else ["healthcare_general"]

    def _assess_discovery_complexity(self, template: Dict) -> str:
        """Assess tool complexity for discovery."""
        input_schema = template.get("input_schema", {})
        mock_response = template.get("mock_response", {})

        param_count = len(input_schema)
        response_complexity = self._count_nested_structures(mock_response)

        if param_count >= 5 or response_complexity >= 3:
            return "high"
        elif param_count >= 3 or response_complexity >= 2:
            return "medium"
        else:
            return "low"

    def _format_discovery_response(self, catalog: Dict[str, Any]) -> str:
        """Format discovery mode response like MCP_CATALOG."""
        tools = catalog.get("tools", {})
        total = catalog.get("total_tools", 0)

        if total == 0:
            search_query = catalog.get("search_query", "")
            if search_query and search_query != "all":
                return f"No MCP tools found matching '{search_query}'. Try a different search term or browse all tools."
            return "No MCP tools found in catalog."

        response = f"🔧 **MCP Healthcare Tools Discovery** ({total} tools available)\n\n"
        response += "**Status**: All tools available with production-ready mock templates\n\n"

        # Group by categories
        categories = {}
        for tool_id, tool_info in tools.items():
            category = tool_info.get("category", "Other")
            if category not in categories:
                categories[category] = []
            categories[category].append((tool_id, tool_info))

        for category, category_tools in categories.items():
            response += f"### {category}\n"
            for tool_id, tool_info in category_tools:
                response += f"**{tool_info['name']}** (`{tool_id}`)\n"
                response += f"- {tool_info['description']}\n"
                response += f"- Complexity: {tool_info.get('complexity', 'medium')} | "
                response += f"Parameters: {tool_info.get('input_parameters', 0)} | "
                response += f"Domains: {', '.join(tool_info.get('healthcare_domains', [])[:2])}\n\n"

        response += "**💡 To configure a specific tool**:\n"
        response += "Use MCP_FRAMEWORK in configuration mode with the tool name or description.\n\n"

        response += "**🚀 Development Ready**: All tools include comprehensive mock templates for testing without MCP servers."

        return response