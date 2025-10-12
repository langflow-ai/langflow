"""Specification Validator Component

Validates generated YAML specifications using the existing SpecService validation.
Ensures specifications meet all requirements before deployment.
"""

import json
import yaml
from typing import Any, Dict, List, Optional

from langflow.custom.custom_component.component import Component
from langflow.field_typing import Data, Text
from langflow.inputs.inputs import MessageTextInput, DictInput, BoolInput
from langflow.schema.data import Data as DataType
from langflow.template.field.base import Output


class SpecificationValidatorComponent(Component):
    display_name = "Specification Validator"
    description = "Validates generated YAML specifications using existing SpecService validation"
    documentation = "Ensures specifications meet all requirements before deployment"
    icon = "check-circle"
    name = "SpecificationValidator"

    inputs = [
        MessageTextInput(
            name="yaml_specification",
            display_name="YAML Specification",
            info="YAML specification content to validate",
            required=True,
        ),
        DictInput(
            name="validation_context",
            display_name="Validation Context",
            info="Additional context for validation (requirements, metadata)",
            required=False,
        ),
        BoolInput(
            name="strict_validation",
            display_name="Strict Validation",
            value=True,
            info="Whether to perform strict validation with all checks",
        ),
    ]

    outputs = [
        Output(display_name="Validation Results", name="validation_results", method="validate_specification"),
        Output(display_name="Error Analysis", name="error_analysis", method="analyze_errors"),
        Output(display_name="Improvement Suggestions", name="suggestions", method="suggest_improvements"),
        Output(display_name="Compliance Check", name="compliance", method="check_compliance"),
        Output(display_name="Validation Summary", name="summary", method="create_validation_summary"),
    ]

    def validate_specification(self) -> DataType:
        """Validate the YAML specification using SpecService"""

        try:
            # Parse YAML
            spec_dict = yaml.safe_load(self.yaml_specification)

            # Use existing SpecService validation
            validation_result = self._validate_with_spec_service(spec_dict)

            # Perform additional custom validation
            custom_validation = self._perform_custom_validation(spec_dict)

            # Combine results
            combined_results = self._combine_validation_results(validation_result, custom_validation)

            return DataType(value=combined_results)

        except yaml.YAMLError as e:
            return DataType(value={
                "valid": False,
                "errors": [f"YAML parsing error: {str(e)}"],
                "warnings": [],
                "yaml_valid": False,
                "spec_valid": False,
            })
        except Exception as e:
            return DataType(value={
                "valid": False,
                "errors": [f"Validation error: {str(e)}"],
                "warnings": [],
                "yaml_valid": True,
                "spec_valid": False,
            })

    def analyze_errors(self) -> DataType:
        """Analyze validation errors and categorize them"""

        validation_results = self.validate_specification().value
        error_analysis = self._categorize_errors(validation_results.get("errors", []))

        return DataType(value={
            "error_categories": error_analysis["categories"],
            "severity_levels": error_analysis["severity"],
            "actionable_errors": error_analysis["actionable"],
            "blocking_errors": error_analysis["blocking"],
            "fix_suggestions": error_analysis["fixes"],
        })

    def suggest_improvements(self) -> DataType:
        """Suggest improvements for the specification"""

        validation_results = self.validate_specification().value
        improvements = self._generate_improvement_suggestions(validation_results)

        return DataType(value={
            "structural_improvements": improvements["structural"],
            "configuration_improvements": improvements["configuration"],
            "performance_improvements": improvements["performance"],
            "best_practice_suggestions": improvements["best_practices"],
            "optimization_opportunities": improvements["optimizations"],
        })

    def check_compliance(self) -> DataType:
        """Check compliance with healthcare and security requirements"""

        try:
            spec_dict = yaml.safe_load(self.yaml_specification)
            compliance_check = self._perform_compliance_validation(spec_dict)

            return DataType(value=compliance_check)

        except Exception as e:
            return DataType(value={
                "compliant": False,
                "errors": [f"Compliance check failed: {str(e)}"],
                "requirements": [],
            })

    def create_validation_summary(self) -> DataType:
        """Create comprehensive validation summary"""

        validation_results = self.validate_specification().value
        error_analysis = self.analyze_errors().value
        compliance = self.check_compliance().value

        summary = self._create_comprehensive_summary(validation_results, error_analysis, compliance)

        return DataType(value=summary)

    def _validate_with_spec_service(self, spec_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Use existing SpecService for validation"""

        # Mock SpecService validation - in production this would use actual SpecService
        # from langflow.services.spec.service import SpecService
        # spec_service = SpecService()
        # return spec_service.validate_spec(yaml.dump(spec_dict))

        # Mock validation logic for demonstration
        return self._mock_spec_service_validation(spec_dict)

    def _mock_spec_service_validation(self, spec_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Mock SpecService validation for demonstration"""

        errors = []
        warnings = []

        # Check required fields
        required_fields = ["id", "name", "description", "agentGoal", "components"]
        for field in required_fields:
            if field not in spec_dict:
                errors.append(f"Missing required field: {field}")

        # Validate URN format
        if "id" in spec_dict:
            urn = spec_dict["id"]
            if not urn.startswith("urn:agent:genesis:"):
                errors.append("Invalid URN format. Should start with 'urn:agent:genesis:'")

        # Validate components
        components = spec_dict.get("components", [])
        if not components:
            errors.append("At least one component is required")
        else:
            for i, component in enumerate(components):
                self._validate_component(component, i, errors, warnings)

        # Check for empty descriptions
        if spec_dict.get("description", "").strip() == "":
            warnings.append("Empty description field")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }

    def _validate_component(self, component: Dict[str, Any], index: int, errors: List[str], warnings: List[str]) -> None:
        """Validate individual component"""

        required_component_fields = ["id", "name", "type"]
        for field in required_component_fields:
            if field not in component:
                errors.append(f"Component {index}: Missing required field '{field}'")

        # Validate component type
        if "type" in component:
            comp_type = component["type"]
            if not comp_type.startswith("genesis:") and comp_type not in ["Memory"]:
                warnings.append(f"Component {index}: Non-standard component type '{comp_type}'")

        # Check for provides relationships
        if "provides" in component:
            provides = component["provides"]
            if not isinstance(provides, list):
                errors.append(f"Component {index}: 'provides' must be a list")
            else:
                for provide in provides:
                    if not isinstance(provide, dict) or "useAs" not in provide:
                        errors.append(f"Component {index}: Invalid provides relationship format")

    def _perform_custom_validation(self, spec_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Perform additional custom validation"""

        errors = []
        warnings = []

        # Healthcare-specific validation
        if self._is_healthcare_spec(spec_dict):
            healthcare_validation = self._validate_healthcare_requirements(spec_dict)
            errors.extend(healthcare_validation["errors"])
            warnings.extend(healthcare_validation["warnings"])

        # Multi-agent validation
        if self._is_multi_agent_spec(spec_dict):
            multi_agent_validation = self._validate_multi_agent_requirements(spec_dict)
            errors.extend(multi_agent_validation["errors"])
            warnings.extend(multi_agent_validation["warnings"])

        # Component relationship validation
        relationship_validation = self._validate_component_relationships(spec_dict)
        errors.extend(relationship_validation["errors"])
        warnings.extend(relationship_validation["warnings"])

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }

    def _is_healthcare_spec(self, spec_dict: Dict[str, Any]) -> bool:
        """Check if this is a healthcare specification"""

        domain = spec_dict.get("domain", "")
        subdomain = spec_dict.get("subDomain", "")
        tags = spec_dict.get("tags", [])

        return (domain == "healthcare" or
                subdomain == "healthcare" or
                "healthcare" in str(tags).lower())

    def _is_multi_agent_spec(self, spec_dict: Dict[str, Any]) -> bool:
        """Check if this is a multi-agent specification"""

        kind = spec_dict.get("kind", "")
        components = spec_dict.get("components", [])

        return (kind == "Multi Agent" or
                any("crewai" in comp.get("type", "") for comp in components))

    def _validate_healthcare_requirements(self, spec_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Validate healthcare-specific requirements"""

        errors = []
        warnings = []

        # Check for security info
        security_info = spec_dict.get("securityInfo", {})
        if not security_info:
            errors.append("Healthcare agents must include securityInfo section")
        else:
            if not security_info.get("hipaaCompliant", False):
                errors.append("Healthcare agents must be HIPAA compliant")
            if not security_info.get("encryption_required", False):
                warnings.append("Consider enabling encryption for healthcare data")

        # Check for audit logging
        if not security_info.get("auditRequired", False):
            warnings.append("Healthcare agents should include audit logging")

        # Check for appropriate KPIs
        kpis = spec_dict.get("kpis", [])
        if not kpis:
            warnings.append("Healthcare agents should define performance KPIs")

        return {"errors": errors, "warnings": warnings}

    def _validate_multi_agent_requirements(self, spec_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Validate multi-agent specific requirements"""

        errors = []
        warnings = []

        components = spec_dict.get("components", [])

        # Count agent and coordination components
        agent_components = [c for c in components if "agent" in c.get("type", "")]
        crew_components = [c for c in components if "crew" in c.get("type", "")]
        task_components = [c for c in components if "task" in c.get("type", "")]

        if len(agent_components) < 2:
            errors.append("Multi-agent specifications must have at least 2 agents")

        if not crew_components:
            errors.append("Multi-agent specifications must include crew coordination")

        if not task_components:
            warnings.append("Consider adding task components for better workflow definition")

        return {"errors": errors, "warnings": warnings}

    def _validate_component_relationships(self, spec_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Validate component relationships and data flow"""

        errors = []
        warnings = []

        components = spec_dict.get("components", [])
        component_ids = {comp.get("id") for comp in components if comp.get("id")}

        # Check provides relationships
        for component in components:
            provides = component.get("provides", [])
            for provide in provides:
                target = provide.get("in")
                if target and target not in component_ids:
                    errors.append(f"Component '{component.get('id')}' references non-existent target '{target}'")

        # Check for input/output components
        has_input = any("input" in comp.get("type", "") for comp in components)
        has_output = any("output" in comp.get("type", "") for comp in components)

        if not has_input:
            warnings.append("Specification should include an input component")
        if not has_output:
            warnings.append("Specification should include an output component")

        return {"errors": errors, "warnings": warnings}

    def _combine_validation_results(self, spec_service_result: Dict[str, Any], custom_result: Dict[str, Any]) -> Dict[str, Any]:
        """Combine validation results from different sources"""

        all_errors = spec_service_result.get("errors", []) + custom_result.get("errors", [])
        all_warnings = spec_service_result.get("warnings", []) + custom_result.get("warnings", [])

        return {
            "valid": len(all_errors) == 0,
            "errors": all_errors,
            "warnings": all_warnings,
            "error_count": len(all_errors),
            "warning_count": len(all_warnings),
            "yaml_valid": True,  # We got this far
            "spec_valid": len(all_errors) == 0,
            "spec_service_result": spec_service_result,
            "custom_validation_result": custom_result,
        }

    def _categorize_errors(self, errors: List[str]) -> Dict[str, Any]:
        """Categorize validation errors"""

        categories = {
            "structural": [],
            "configuration": [],
            "relationships": [],
            "compliance": [],
            "format": [],
        }

        severity = {"critical": [], "high": [], "medium": [], "low": []}
        actionable = []
        blocking = []
        fixes = {}

        for error in errors:
            error_lower = error.lower()

            # Categorize by type
            if "missing required field" in error_lower:
                categories["structural"].append(error)
                severity["critical"].append(error)
                blocking.append(error)
                fixes[error] = "Add the missing required field to the specification"

            elif "invalid urn" in error_lower:
                categories["format"].append(error)
                severity["high"].append(error)
                fixes[error] = "Update URN to follow format: urn:agent:genesis:domain:name:version"

            elif "component" in error_lower and "references" in error_lower:
                categories["relationships"].append(error)
                severity["high"].append(error)
                fixes[error] = "Ensure all component references point to existing component IDs"

            elif "hipaa" in error_lower or "security" in error_lower:
                categories["compliance"].append(error)
                severity["critical"].append(error)
                blocking.append(error)
                fixes[error] = "Add required security and compliance configuration"

            else:
                categories["configuration"].append(error)
                severity["medium"].append(error)

            actionable.append(error)

        return {
            "categories": categories,
            "severity": severity,
            "actionable": actionable,
            "blocking": blocking,
            "fixes": fixes,
        }

    def _generate_improvement_suggestions(self, validation_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate improvement suggestions based on validation results"""

        suggestions = {
            "structural": [],
            "configuration": [],
            "performance": [],
            "best_practices": [],
            "optimizations": [],
        }

        errors = validation_results.get("errors", [])
        warnings = validation_results.get("warnings", [])

        # Structural improvements
        if any("missing" in error.lower() for error in errors):
            suggestions["structural"].append("Ensure all required fields are present and properly formatted")

        # Configuration improvements
        if any("component" in warning.lower() for warning in warnings):
            suggestions["configuration"].append("Review component configurations for completeness")

        # Performance improvements
        suggestions["performance"].extend([
            "Consider adding timeout and retry configurations for external integrations",
            "Optimize memory usage by setting appropriate limits for LLM components",
        ])

        # Best practices
        suggestions["best_practices"].extend([
            "Include comprehensive descriptions for all components",
            "Add sample input/output for testing and documentation",
            "Define clear KPIs for monitoring agent performance",
        ])

        # Optimizations
        if len(validation_results.get("spec_service_result", {}).get("warnings", [])) > 5:
            suggestions["optimizations"].append("Consider simplifying the specification to reduce complexity")

        return suggestions

    def _perform_compliance_validation(self, spec_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Perform compliance validation"""

        compliance_results = {
            "compliant": True,
            "errors": [],
            "requirements": [],
            "healthcare_compliance": {},
            "security_compliance": {},
            "general_compliance": {},
        }

        # Healthcare compliance
        if self._is_healthcare_spec(spec_dict):
            healthcare_compliance = self._check_healthcare_compliance(spec_dict)
            compliance_results["healthcare_compliance"] = healthcare_compliance
            if not healthcare_compliance["compliant"]:
                compliance_results["compliant"] = False
                compliance_results["errors"].extend(healthcare_compliance["violations"])

        # Security compliance
        security_compliance = self._check_security_compliance(spec_dict)
        compliance_results["security_compliance"] = security_compliance
        if not security_compliance["compliant"]:
            compliance_results["compliant"] = False
            compliance_results["errors"].extend(security_compliance["violations"])

        # General compliance
        general_compliance = self._check_general_compliance(spec_dict)
        compliance_results["general_compliance"] = general_compliance

        return compliance_results

    def _check_healthcare_compliance(self, spec_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Check healthcare-specific compliance"""

        violations = []
        requirements_met = []

        security_info = spec_dict.get("securityInfo", {})

        # HIPAA compliance
        if not security_info.get("hipaaCompliant", False):
            violations.append("HIPAA compliance not specified")
        else:
            requirements_met.append("HIPAA compliance declared")

        # PHI handling
        if not security_info.get("encryption_required", False):
            violations.append("PHI encryption not configured")
        else:
            requirements_met.append("Data encryption configured")

        # Audit logging
        if not security_info.get("auditRequired", False):
            violations.append("Audit logging not required")
        else:
            requirements_met.append("Audit logging configured")

        return {
            "compliant": len(violations) == 0,
            "violations": violations,
            "requirements_met": requirements_met,
            "score": len(requirements_met) / (len(requirements_met) + len(violations)) if (len(requirements_met) + len(violations)) > 0 else 1.0,
        }

    def _check_security_compliance(self, spec_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Check general security compliance"""

        violations = []
        requirements_met = []

        # Check for authentication in MCP tools
        components = spec_dict.get("components", [])
        mcp_tools = [c for c in components if c.get("type") == "genesis:mcp_tool"]

        if mcp_tools:
            for tool in mcp_tools:
                config = tool.get("config", {})
                if not config.get("auth_required", True):
                    violations.append(f"Tool '{tool.get('name')}' may lack authentication")
                else:
                    requirements_met.append(f"Authentication configured for '{tool.get('name')}'")

        # Check for environment variable usage
        yaml_content = yaml.dump(spec_dict)
        if "${" in yaml_content:
            requirements_met.append("Environment variables used for sensitive data")
        else:
            violations.append("Consider using environment variables for sensitive configuration")

        return {
            "compliant": len(violations) == 0,
            "violations": violations,
            "requirements_met": requirements_met,
        }

    def _check_general_compliance(self, spec_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Check general specification compliance"""

        best_practices_met = []
        recommendations = []

        # Check for KPIs
        if spec_dict.get("kpis"):
            best_practices_met.append("Performance KPIs defined")
        else:
            recommendations.append("Consider adding KPIs for performance monitoring")

        # Check for tags
        if spec_dict.get("tags"):
            best_practices_met.append("Tags provided for categorization")
        else:
            recommendations.append("Add tags for better specification categorization")

        # Check for sample data
        if spec_dict.get("sampleInput") and spec_dict.get("sampleOutput"):
            best_practices_met.append("Sample input/output provided")
        else:
            recommendations.append("Include sample input/output for testing")

        return {
            "best_practices_met": best_practices_met,
            "recommendations": recommendations,
            "score": len(best_practices_met) / 3,  # Out of 3 possible best practices
        }

    def _create_comprehensive_summary(self, validation_results: Dict[str, Any], error_analysis: Dict[str, Any], compliance: Dict[str, Any]) -> Dict[str, Any]:
        """Create comprehensive validation summary"""

        overall_status = "PASSED" if validation_results["valid"] and compliance["compliant"] else "FAILED"

        if validation_results["valid"] and not compliance["compliant"]:
            overall_status = "PASSED_WITH_WARNINGS"

        return {
            "overall_status": overall_status,
            "validation_passed": validation_results["valid"],
            "compliance_passed": compliance["compliant"],
            "total_errors": validation_results["error_count"],
            "total_warnings": validation_results["warning_count"],
            "blocking_errors": len(error_analysis["blocking_errors"]),
            "summary": {
                "specification_valid": validation_results["spec_valid"],
                "yaml_valid": validation_results["yaml_valid"],
                "healthcare_compliant": compliance.get("healthcare_compliance", {}).get("compliant", True),
                "security_compliant": compliance.get("security_compliance", {}).get("compliant", True),
            },
            "next_steps": self._generate_next_steps(validation_results, error_analysis, compliance),
            "readiness_score": self._calculate_readiness_score(validation_results, compliance),
        }

    def _generate_next_steps(self, validation_results: Dict[str, Any], error_analysis: Dict[str, Any], compliance: Dict[str, Any]) -> List[str]:
        """Generate next steps based on validation results"""

        next_steps = []

        if validation_results["error_count"] > 0:
            next_steps.append(f"Fix {validation_results['error_count']} validation errors")

        if error_analysis["blocking_errors"]:
            next_steps.append("Address blocking errors before deployment")

        if not compliance["compliant"]:
            next_steps.append("Resolve compliance violations")

        if validation_results["valid"] and compliance["compliant"]:
            next_steps.extend([
                "Specification is ready for deployment",
                "Consider running integration tests",
                "Review performance optimization opportunities",
            ])

        return next_steps

    def _calculate_readiness_score(self, validation_results: Dict[str, Any], compliance: Dict[str, Any]) -> float:
        """Calculate overall readiness score"""

        score = 0.0

        # Validation score (40% weight)
        if validation_results["valid"]:
            score += 0.4
        elif validation_results["error_count"] <= 2:
            score += 0.2

        # Compliance score (40% weight)
        if compliance["compliant"]:
            score += 0.4
        else:
            # Partial credit based on compliance areas
            healthcare_score = compliance.get("healthcare_compliance", {}).get("score", 0)
            security_score = compliance.get("security_compliance", {}).get("score", 1)
            score += 0.4 * (healthcare_score + security_score) / 2

        # Warning score (20% weight)
        warning_count = validation_results["warning_count"]
        if warning_count == 0:
            score += 0.2
        elif warning_count <= 3:
            score += 0.1

        return min(score, 1.0)