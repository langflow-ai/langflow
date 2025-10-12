"""Specification Builder Component

Generates complete YAML agent specifications from gathered requirements and component recommendations.
Follows the official schema and includes all necessary sections for deployment.
"""

import json
import yaml
from datetime import datetime
from typing import Any, Dict, List, Optional

from langflow.custom.custom_component.component import Component
from langflow.field_typing import Data, Text
from langflow.inputs.inputs import MessageTextInput, DictInput, DropdownInput, BoolInput, IntInput
from langflow.schema.data import Data as DataType
from langflow.template.field.base import Output


class SpecificationBuilderComponent(Component):
    display_name = "Specification Builder"
    description = "Generates complete YAML agent specifications from requirements and recommendations"
    documentation = "Creates deployment-ready specifications following official schema"
    icon = "file-text"
    name = "SpecificationBuilder"

    inputs = [
        DictInput(
            name="requirements",
            display_name="Complete Requirements",
            info="Validated requirements from RequirementsGathererComponent",
            required=True,
        ),
        DictInput(
            name="recommended_components",
            display_name="Recommended Components",
            info="Component recommendations from ComponentRecommenderComponent",
            required=True,
        ),
        DictInput(
            name="mcp_tools",
            display_name="MCP Tools Configuration",
            info="MCP tool configuration from MCPToolDiscoveryComponent",
            required=False,
        ),
        DropdownInput(
            name="specification_version",
            display_name="Specification Version",
            options=["1.0.0", "1.1.0", "2.0.0"],
            value="1.0.0",
            info="Version of the specification format",
        ),
        BoolInput(
            name="include_samples",
            display_name="Include Sample Data",
            value=True,
            info="Whether to include sample input/output in specification",
        ),
        BoolInput(
            name="optimize_for_production",
            display_name="Optimize for Production",
            value=True,
            info="Whether to optimize configuration for production deployment",
        ),
    ]

    outputs = [
        Output(display_name="YAML Specification", name="yaml_spec", method="build_specification"),
        Output(display_name="Specification Metadata", name="metadata", method="extract_metadata"),
        Output(display_name="Component Summary", name="component_summary", method="summarize_components"),
        Output(display_name="Configuration Guide", name="config_guide", method="generate_config_guide"),
        Output(display_name="Deployment Info", name="deployment_info", method="create_deployment_info"),
    ]

    def build_specification(self) -> DataType:
        """Build complete YAML specification"""

        specification = self._create_base_specification()
        specification.update(self._add_metadata_section())
        specification.update(self._add_components_section())
        specification.update(self._add_variables_section())
        specification.update(self._add_outputs_section())
        
        if self.include_samples:
            specification.update(self._add_sample_data())
            
        if self._is_healthcare_agent():
            specification.update(self._add_healthcare_sections())
            
        yaml_content = self._convert_to_yaml(specification)
        
        return DataType(value={
            "yaml_content": yaml_content,
            "specification_dict": specification,
            "component_count": len(specification.get("components", [])),
            "estimated_size": len(yaml_content),
        })

    def extract_metadata(self) -> DataType:
        """Extract and format specification metadata"""

        metadata = self._generate_metadata()
        
        return DataType(value={
            "agent_info": metadata["agent_info"],
            "technical_info": metadata["technical_info"],
            "compliance_info": metadata["compliance_info"],
            "deployment_info": metadata["deployment_info"],
        })

    def summarize_components(self) -> DataType:
        """Summarize components in the specification"""

        components = self.recommended_components.get("components", [])
        summary = self._create_component_summary(components)
        
        return DataType(value={
            "total_components": summary["total"],
            "by_category": summary["by_category"],
            "by_priority": summary["by_priority"],
            "integration_count": summary["integrations"],
            "complexity_assessment": summary["complexity"],
        })

    def generate_config_guide(self) -> DataType:
        """Generate configuration guide for the specification"""

        config_guide = self._create_configuration_guide()
        
        return DataType(value={
            "required_configuration": config_guide["required"],
            "optional_configuration": config_guide["optional"],
            "environment_variables": config_guide["env_vars"],
            "security_configuration": config_guide["security"],
        })

    def create_deployment_info(self) -> DataType:
        """Create deployment information"""

        deployment_info = self._generate_deployment_info()
        
        return DataType(value={
            "resource_requirements": deployment_info["resources"],
            "scaling_configuration": deployment_info["scaling"],
            "monitoring_setup": deployment_info["monitoring"],
            "health_checks": deployment_info["health_checks"],
        })

    def _create_base_specification(self) -> Dict[str, Any]:
        """Create base specification structure"""
        
        metadata = self.requirements.get("metadata", {})
        agent_name = self._generate_agent_name()
        
        return {
            "id": self._generate_urn(agent_name),
            "name": agent_name,
            "fullyQualifiedName": f"genesis.autonomize.ai.{agent_name.lower().replace(' ', '_')}",
            "description": metadata.get("agent_goal", "AI agent for processing and automation"),
            "domain": "autonomize.ai",
            "subDomain": metadata.get("domain", "general"),
            "version": self.specification_version,
            "environment": "production" if self.optimize_for_production else "development",
            "agentOwner": self._get_agent_owner(),
            "agentOwnerDisplayName": self._get_agent_owner_display(),
            "email": self._get_agent_email(),
            "status": "ACTIVE",
        }

    def _add_metadata_section(self) -> Dict[str, Any]:
        """Add metadata and characteristics section"""
        
        metadata = self.requirements.get("metadata", {})
        
        return {
            "kind": self._format_agent_kind(metadata.get("agent_type", "single_agent")),
            "agentGoal": metadata.get("agent_goal", ""),
            "targetUser": "internal",
            "valueGeneration": "ProcessAutomation",
            "interactionMode": "RequestResponse",
            "runMode": "RealTime",
            "agencyLevel": "KnowledgeDrivenWorkflow",
            "toolsUse": True,
            "learningCapability": "Supervised",
            "tags": self._generate_tags(),
        }

    def _add_components_section(self) -> Dict[str, Any]:
        """Add components section to specification"""
        
        components = []
        recommended_components = self.recommended_components.get("components", [])
        
        for comp in recommended_components:
            component_spec = self._convert_component_to_spec(comp)
            components.append(component_spec)
            
        # Add MCP tools if available
        if self.mcp_tools:
            mcp_components = self.mcp_tools.get("tool_configurations", [])
            for mcp_comp in mcp_components:
                components.append(mcp_comp)
                
        return {"components": components}

    def _add_variables_section(self) -> Dict[str, Any]:
        """Add variables section for configuration"""
        
        variables = self._generate_variables()
        
        return {"variables": variables} if variables else {}

    def _add_outputs_section(self) -> Dict[str, Any]:
        """Add outputs section"""
        
        outputs = self._determine_outputs()
        
        return {"outputs": outputs}

    def _add_sample_data(self) -> Dict[str, Any]:
        """Add sample input/output data"""
        
        return {
            "sampleInput": self._generate_sample_input(),
            "sampleOutput": self._generate_sample_output(),
        }

    def _add_healthcare_sections(self) -> Dict[str, Any]:
        """Add healthcare-specific sections"""
        
        healthcare_sections = {}
        
        # Add KPIs
        healthcare_sections["kpis"] = self._generate_healthcare_kpis()
        
        # Add security info
        healthcare_sections["securityInfo"] = {
            "visibility": "Private",
            "confidentiality": "High",
            "gdprSensitive": True,
            "hipaaCompliant": True,
            "patientDataAccess": True,
            "auditRequired": True,
        }
        
        # Add reusability info if applicable
        if self._should_include_reusability():
            healthcare_sections["reusability"] = self._generate_reusability_info()
            
        return healthcare_sections

    def _generate_agent_name(self) -> str:
        """Generate appropriate agent name"""
        
        metadata = self.requirements.get("metadata", {})
        domain = metadata.get("domain", "general")
        use_case = metadata.get("use_case_category", "general")
        
        name_parts = []
        
        if use_case != "general":
            name_parts.append(use_case.replace("_", " ").title())
            
        if domain == "healthcare":
            name_parts.append("Healthcare")
            
        name_parts.append("Agent")
        
        return " ".join(name_parts)

    def _generate_urn(self, agent_name: str) -> str:
        """Generate URN for the agent"""
        
        metadata = self.requirements.get("metadata", {})
        domain = metadata.get("domain", "general")
        name_slug = agent_name.lower().replace(" ", "_").replace("-", "_")
        
        return f"urn:agent:genesis:{domain}:{name_slug}:{self.specification_version}"

    def _get_agent_owner(self) -> str:
        """Get agent owner email"""
        
        domain = self.requirements.get("metadata", {}).get("domain", "general")
        
        owner_mapping = {
            "healthcare": "healthcare@autonomize.ai",
            "finance": "finance@autonomize.ai",
            "general": "platform@autonomize.ai",
        }
        
        return owner_mapping.get(domain, "platform@autonomize.ai")

    def _get_agent_owner_display(self) -> str:
        """Get agent owner display name"""
        
        domain = self.requirements.get("metadata", {}).get("domain", "general")
        
        display_mapping = {
            "healthcare": "Healthcare Team",
            "finance": "Finance Team",
            "general": "Platform Team",
        }
        
        return display_mapping.get(domain, "Platform Team")

    def _get_agent_email(self) -> str:
        """Get agent contact email"""
        
        return self._get_agent_owner()

    def _format_agent_kind(self, agent_type: str) -> str:
        """Format agent type to specification kind"""
        
        type_mapping = {
            "single_agent": "Single Agent",
            "multi_agent": "Multi Agent",
            "workflow_agent": "Workflow Agent",
        }
        
        return type_mapping.get(agent_type, "Single Agent")

    def _generate_tags(self) -> List[str]:
        """Generate appropriate tags"""
        
        tags = []
        
        metadata = self.requirements.get("metadata", {})
        domain = metadata.get("domain", "")
        use_case = metadata.get("use_case_category", "")
        
        if domain:
            tags.append(domain)
            
        if use_case:
            tags.append(use_case.replace("_", "-"))
            
        tags.extend(["automation", "ai-generated"])
        
        if self._is_healthcare_agent():
            tags.extend(["hipaa-compliant", "clinical-workflow"])
            
        return tags

    def _convert_component_to_spec(self, component: Dict[str, Any]) -> Dict[str, Any]:
        """Convert component recommendation to specification format"""
        
        spec_component = {
            "id": self._generate_component_id(component),
            "name": component.get("name", ""),
            "kind": self._determine_component_kind(component),
            "type": component.get("type", ""),
            "description": component.get("description", ""),
        }
        
        # Add configuration if present
        if "configuration" in component:
            spec_component["config"] = component["configuration"]
            
        # Add provides relationships
        if "provides" in component:
            spec_component["provides"] = component["provides"]
            
        # Add asTools flag for tool components
        if component.get("category") == "integration":
            spec_component["asTools"] = True
            
        return spec_component

    def _generate_component_id(self, component: Dict[str, Any]) -> str:
        """Generate component ID"""
        
        name = component.get("name", "component")
        return name.lower().replace(" ", "-")

    def _determine_component_kind(self, component: Dict[str, Any]) -> str:
        """Determine component kind"""
        
        category = component.get("category", "")
        
        kind_mapping = {
            "input_output": "Data",
            "agent": "Agent",
            "integration": "Tool",
            "coordination": "Coordination",
            "task": "Task",
            "prompt": "Prompt",
            "memory": "Memory",
        }
        
        return kind_mapping.get(category, "Component")

    def _generate_variables(self) -> List[Dict[str, Any]]:
        """Generate configuration variables"""
        
        variables = []
        
        # Add standard variables
        variables.extend([
            {
                "name": "llm_provider",
                "type": "string",
                "required": False,
                "default": "Azure OpenAI",
                "description": "LLM provider for agent processing"
            },
            {
                "name": "model_name",
                "type": "string",
                "required": False,
                "default": "gpt-4",
                "description": "Model name for LLM processing"
            },
            {
                "name": "temperature",
                "type": "float",
                "required": False,
                "default": 0.1,
                "description": "Temperature for LLM responses"
            }
        ])
        
        # Add domain-specific variables
        if self._is_healthcare_agent():
            variables.extend([
                {
                    "name": "hipaa_logging",
                    "type": "boolean",
                    "required": False,
                    "default": True,
                    "description": "Enable HIPAA-compliant audit logging"
                },
                {
                    "name": "phi_encryption",
                    "type": "boolean",
                    "required": False,
                    "default": True,
                    "description": "Enable PHI data encryption"
                }
            ])
            
        return variables

    def _determine_outputs(self) -> List[str]:
        """Determine agent outputs"""
        
        outputs = []
        
        # Standard outputs
        outputs.extend(["agent_response", "processing_status"])
        
        # Add domain-specific outputs
        use_case = self.requirements.get("metadata", {}).get("use_case_category", "")
        
        if use_case == "prior_authorization":
            outputs.extend(["authorization_status", "approval_details", "required_documentation"])
        elif use_case == "clinical_decision_support":
            outputs.extend(["recommendations", "evidence_links", "confidence_score"])
        elif use_case == "patient_communication":
            outputs.extend(["message_status", "delivery_confirmation", "response_tracking"])
            
        return outputs

    def _generate_sample_input(self) -> Dict[str, Any]:
        """Generate sample input data"""
        
        use_case = self.requirements.get("metadata", {}).get("use_case_category", "general")
        
        if use_case == "prior_authorization":
            return {
                "patient_id": "P123456789",
                "procedure_code": "99213",
                "provider_npi": "1234567890",
                "insurance_info": {
                    "plan_id": "BCBS_PPO_2024",
                    "member_id": "M987654321",
                    "group_number": "GRP12345"
                },
                "clinical_notes": "Patient presents with chronic condition requiring specialist consultation."
            }
        else:
            return {
                "user_request": "Process this healthcare request",
                "context": "Sample context for processing",
                "priority": "normal"
            }

    def _generate_sample_output(self) -> Dict[str, Any]:
        """Generate sample output data"""
        
        use_case = self.requirements.get("metadata", {}).get("use_case_category", "general")
        
        if use_case == "prior_authorization":
            return {
                "authorization_status": "approved",
                "approval_number": "AUTH202401001",
                "valid_until": "2024-12-31",
                "conditions": ["Valid for original provider only"],
                "processing_time": "2.3 seconds"
            }
        else:
            return {
                "response": "Request processed successfully",
                "status": "completed",
                "processing_time": "1.2 seconds",
                "confidence": 0.95
            }

    def _generate_healthcare_kpis(self) -> List[Dict[str, Any]]:
        """Generate healthcare-specific KPIs"""
        
        return [
            {
                "name": "Processing Accuracy",
                "category": "Quality",
                "valueType": "percentage",
                "target": 95,
                "unit": "%",
                "description": "Accuracy of agent processing and decisions"
            },
            {
                "name": "Response Time",
                "category": "Performance",
                "valueType": "numeric",
                "target": 5,
                "unit": "seconds",
                "description": "Average response time for processing requests"
            },
            {
                "name": "HIPAA Compliance Rate",
                "category": "Compliance",
                "valueType": "percentage",
                "target": 100,
                "unit": "%",
                "description": "Percentage of interactions meeting HIPAA requirements"
            }
        ]

    def _generate_reusability_info(self) -> Dict[str, Any]:
        """Generate reusability information"""
        
        return {
            "asTools": True,
            "standalone": True,
            "provides": {
                "toolName": self._generate_agent_name().replace(" ", ""),
                "toolDescription": self.requirements.get("metadata", {}).get("agent_goal", ""),
                "inputSchema": self._generate_tool_input_schema(),
                "outputSchema": self._generate_tool_output_schema()
            }
        }

    def _generate_tool_input_schema(self) -> Dict[str, Any]:
        """Generate input schema for tool reusability"""
        
        return {
            "type": "object",
            "properties": {
                "request": {
                    "type": "string",
                    "description": "User request to process"
                },
                "context": {
                    "type": "object",
                    "description": "Additional context for processing"
                }
            },
            "required": ["request"]
        }

    def _generate_tool_output_schema(self) -> Dict[str, Any]:
        """Generate output schema for tool reusability"""
        
        return {
            "type": "object",
            "properties": {
                "result": {
                    "type": "string",
                    "description": "Processing result"
                },
                "status": {
                    "type": "string",
                    "description": "Processing status"
                },
                "metadata": {
                    "type": "object",
                    "description": "Additional result metadata"
                }
            }
        }

    def _convert_to_yaml(self, specification: Dict[str, Any]) -> str:
        """Convert specification dictionary to YAML string"""
        
        # Custom YAML formatting for better readability
        yaml_content = yaml.dump(
            specification,
            default_flow_style=False,
            sort_keys=False,
            indent=2,
            width=120,
            allow_unicode=True
        )
        
        return yaml_content

    def _is_healthcare_agent(self) -> bool:
        """Check if this is a healthcare agent"""
        
        return self.requirements.get("metadata", {}).get("domain") == "healthcare"

    def _should_include_reusability(self) -> bool:
        """Check if reusability section should be included"""
        
        complexity = self.requirements.get("metadata", {}).get("complexity_level", "simple")
        return complexity in ["intermediate", "advanced"]

    def _generate_metadata(self) -> Dict[str, Any]:
        """Generate metadata summary"""
        
        metadata = self.requirements.get("metadata", {})
        
        return {
            "agent_info": {
                "name": self._generate_agent_name(),
                "domain": metadata.get("domain", "general"),
                "use_case": metadata.get("use_case_category", "general"),
                "complexity": metadata.get("complexity_level", "simple"),
            },
            "technical_info": {
                "agent_type": metadata.get("agent_type", "single_agent"),
                "component_count": len(self.recommended_components.get("components", [])),
                "integration_count": len([c for c in self.recommended_components.get("components", []) if c.get("category") == "integration"]),
            },
            "compliance_info": {
                "hipaa_required": self._is_healthcare_agent(),
                "encryption_required": self._is_healthcare_agent(),
                "audit_logging": self._is_healthcare_agent(),
            },
            "deployment_info": {
                "environment": "production" if self.optimize_for_production else "development",
                "scaling_required": metadata.get("agent_type") == "multi_agent",
                "resource_intensive": metadata.get("complexity_level") in ["advanced", "enterprise"],
            }
        }

    def _create_component_summary(self, components: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create summary of components"""
        
        by_category = {}
        by_priority = {}
        integration_count = 0
        
        for comp in components:
            category = comp.get("category", "other")
            priority = comp.get("priority", "medium")
            
            by_category[category] = by_category.get(category, 0) + 1
            by_priority[priority] = by_priority.get(priority, 0) + 1
            
            if category == "integration":
                integration_count += 1
                
        complexity = "simple"
        if len(components) > 10:
            complexity = "advanced"
        elif len(components) > 6:
            complexity = "intermediate"
            
        return {
            "total": len(components),
            "by_category": by_category,
            "by_priority": by_priority,
            "integrations": integration_count,
            "complexity": complexity,
        }

    def _create_configuration_guide(self) -> Dict[str, Any]:
        """Create configuration guide"""
        
        return {
            "required": [
                "Set LLM provider and model configuration",
                "Configure authentication for external services",
                "Set up environment variables for sensitive data",
            ],
            "optional": [
                "Adjust temperature and token limits",
                "Configure timeout and retry settings",
                "Set up custom prompt templates",
            ],
            "env_vars": self._list_required_env_vars(),
            "security": [
                "Enable encryption for data at rest and in transit",
                "Configure audit logging for compliance",
                "Set up access controls and authentication",
            ]
        }

    def _list_required_env_vars(self) -> List[str]:
        """List required environment variables"""
        
        env_vars = ["OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT"]
        
        if self._is_healthcare_agent():
            env_vars.extend(["EHR_API_KEY", "INSURANCE_API_KEY"])
            
        if self.mcp_tools:
            mcp_env_vars = self.mcp_tools.get("environment_variables", [])
            env_vars.extend(mcp_env_vars)
            
        return sorted(list(set(env_vars)))

    def _generate_deployment_info(self) -> Dict[str, Any]:
        """Generate deployment information"""
        
        complexity = self.requirements.get("metadata", {}).get("complexity_level", "simple")
        agent_type = self.requirements.get("metadata", {}).get("agent_type", "single_agent")
        
        resource_map = {
            "simple": {"cpu": "200m", "memory": "512Mi"},
            "intermediate": {"cpu": "500m", "memory": "1Gi"},
            "advanced": {"cpu": "1000m", "memory": "2Gi"},
        }
        
        return {
            "resources": resource_map.get(complexity, resource_map["simple"]),
            "scaling": {
                "min_replicas": 1,
                "max_replicas": 3 if agent_type == "multi_agent" else 2,
                "target_cpu": 70,
            },
            "monitoring": [
                "Response time monitoring",
                "Error rate tracking",
                "Resource utilization metrics",
            ],
            "health_checks": {
                "liveness_probe": "/health",
                "readiness_probe": "/ready",
                "startup_probe": "/startup",
            }
        }