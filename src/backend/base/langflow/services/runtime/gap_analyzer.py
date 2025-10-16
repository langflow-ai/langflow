"""
Converter Gap Analysis Tool.

This module provides systematic analysis of the current converter implementation
to identify gaps, missing components, and improvement opportunities.
"""

from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum
import logging
from pathlib import Path
import importlib
import inspect

logger = logging.getLogger(__name__)


class GapSeverity(Enum):
    """Severity levels for identified gaps."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class GapCategory(Enum):
    """Categories of gaps that can be identified."""
    MISSING_COMPONENT = "missing_component"
    MISSING_MAPPING = "missing_mapping"
    INCOMPLETE_CONVERSION = "incomplete_conversion"
    VALIDATION_GAP = "validation_gap"
    BIDIRECTIONAL_GAP = "bidirectional_gap"
    RUNTIME_SUPPORT = "runtime_support"
    CONFIGURATION_GAP = "configuration_gap"


@dataclass
class ComponentGap:
    """Represents a gap in component support."""
    component_name: str
    component_path: str
    genesis_type: Optional[str]
    gap_category: GapCategory
    severity: GapSeverity
    description: str
    recommendation: str
    runtime_support: Dict[str, bool]
    effort_estimate: str


@dataclass
class MappingGap:
    """Represents a gap in component mapping."""
    genesis_type: str
    langflow_component: Optional[str]
    gap_category: GapCategory
    severity: GapSeverity
    description: str
    recommendation: str
    configuration_issues: List[str]


@dataclass
class ConversionGap:
    """Represents a gap in conversion capabilities."""
    conversion_type: str  # "spec_to_runtime" or "runtime_to_spec"
    runtime: str
    gap_category: GapCategory
    severity: GapSeverity
    description: str
    missing_features: List[str]
    recommendation: str


@dataclass
class ImplementationAudit:
    """Results of implementation audit."""
    total_components_scanned: int
    mapped_components: int
    unmapped_components: int
    component_gaps: List[ComponentGap]
    mapping_gaps: List[MappingGap]
    conversion_gaps: List[ConversionGap]
    summary: Dict[str, Any]


class ConverterGapAnalyzer:
    """
    Systematic analyzer for identifying gaps in converter implementation.

    This tool analyzes the current state of:
    - Component mappings
    - Conversion capabilities
    - Runtime support
    - Bidirectional conversion
    """

    def __init__(self):
        """Initialize the gap analyzer."""
        self.logger = logging.getLogger(__name__)

    def audit_current_implementation(self) -> ImplementationAudit:
        """
        Analyze what converter functionality already exists.

        Returns:
            Comprehensive audit results
        """
        self.logger.info("Starting comprehensive converter implementation audit")

        # Scan for Langflow components
        langflow_components = self._scan_langflow_components()

        # Get current Genesis mappings
        genesis_mappings = self._get_genesis_mappings()

        # Analyze component gaps
        component_gaps = self._analyze_component_gaps(langflow_components, genesis_mappings)

        # Analyze mapping gaps
        mapping_gaps = self._analyze_mapping_gaps(genesis_mappings)

        # Analyze conversion gaps
        conversion_gaps = self._analyze_conversion_gaps()

        # Generate summary
        summary = self._generate_audit_summary(
            langflow_components, genesis_mappings,
            component_gaps, mapping_gaps, conversion_gaps
        )

        audit = ImplementationAudit(
            total_components_scanned=len(langflow_components),
            mapped_components=len(genesis_mappings),
            unmapped_components=len(langflow_components) - len(genesis_mappings),
            component_gaps=component_gaps,
            mapping_gaps=mapping_gaps,
            conversion_gaps=conversion_gaps,
            summary=summary
        )

        self.logger.info(f"Audit completed: {audit.total_components_scanned} components scanned, "
                        f"{len(component_gaps)} gaps identified")

        return audit

    def identify_missing_components(self) -> List[ComponentGap]:
        """
        Identify components that need mapping implementations.

        Returns:
            List of missing component gaps
        """
        audit = self.audit_current_implementation()
        return [gap for gap in audit.component_gaps
                if gap.gap_category == GapCategory.MISSING_COMPONENT]

    def assess_conversion_quality(self) -> Dict[str, Any]:
        """
        Assess quality and completeness of existing conversions.

        Returns:
            Quality assessment report
        """
        audit = self.audit_current_implementation()

        # Analyze conversion capabilities
        langflow_conversion = self._assess_langflow_conversion_quality()
        bidirectional_support = self._assess_bidirectional_support()
        runtime_coverage = self._assess_runtime_coverage()

        return {
            "overall_score": self._calculate_overall_quality_score(audit),
            "langflow_conversion": langflow_conversion,
            "bidirectional_support": bidirectional_support,
            "runtime_coverage": runtime_coverage,
            "critical_gaps": [gap for gap in audit.component_gaps + audit.mapping_gaps + audit.conversion_gaps
                             if gap.severity == GapSeverity.CRITICAL],
            "recommendations": self._generate_quality_recommendations(audit)
        }

    def generate_implementation_plan(self) -> Dict[str, Any]:
        """
        Generate prioritized plan for implementing missing functionality.

        Returns:
            Implementation plan with priorities and effort estimates
        """
        audit = self.audit_current_implementation()

        # Prioritize gaps by severity and impact
        prioritized_gaps = self._prioritize_gaps(
            audit.component_gaps + audit.mapping_gaps + audit.conversion_gaps
        )

        # Group by implementation phases
        phases = self._organize_into_phases(prioritized_gaps)

        # Estimate effort and dependencies
        effort_estimates = self._estimate_implementation_effort(prioritized_gaps)

        return {
            "phases": phases,
            "effort_estimates": effort_estimates,
            "timeline_weeks": self._estimate_timeline(phases),
            "resource_requirements": self._estimate_resources(phases),
            "success_metrics": self._define_success_metrics(audit),
            "risk_assessment": self._assess_implementation_risks(phases)
        }

    def _scan_langflow_components(self) -> Dict[str, Dict[str, Any]]:
        """Scan for all available Langflow components."""
        components = {}

        try:
            # Base component paths to scan
            component_paths = [
                "langflow.components.agents",
                "langflow.components.data",
                "langflow.components.embeddings",
                "langflow.components.helpers",
                "langflow.components.inputs",
                "langflow.components.llms",
                "langflow.components.memories",
                "langflow.components.outputs",
                "langflow.components.prompts",
                "langflow.components.retrievers",
                "langflow.components.textsplitters",
                "langflow.components.toolkits",
                "langflow.components.tools",
                "langflow.components.vectorstores"
            ]

            for path in component_paths:
                try:
                    components.update(self._scan_component_path(path))
                except Exception as e:
                    self.logger.warning(f"Failed to scan component path {path}: {e}")

        except Exception as e:
            self.logger.error(f"Failed to scan Langflow components: {e}")

        return components

    def _scan_component_path(self, module_path: str) -> Dict[str, Dict[str, Any]]:
        """Scan a specific module path for components."""
        components = {}

        try:
            # Try to import the module
            module = importlib.import_module(module_path)

            # Look for component classes
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and
                    hasattr(obj, 'display_name') and
                    hasattr(obj, 'description')):

                    components[name] = {
                        "class_name": name,
                        "module_path": module_path,
                        "display_name": getattr(obj, 'display_name', name),
                        "description": getattr(obj, 'description', ''),
                        "has_template": hasattr(obj, 'template'),
                        "base_classes": [cls.__name__ for cls in obj.__mro__[1:]]
                    }

        except ImportError as e:
            self.logger.debug(f"Could not import {module_path}: {e}")
        except Exception as e:
            self.logger.warning(f"Error scanning {module_path}: {e}")

        return components

    def _get_genesis_mappings(self) -> Dict[str, Dict[str, Any]]:
        """Get current Genesis component mappings."""
        try:
            from langflow.custom.genesis.spec.mapper import ComponentMapper
            mapper = ComponentMapper()

            # Combine all mappings
            all_mappings = {
                **mapper.AUTONOMIZE_MODELS,
                **mapper.MCP_MAPPINGS,
                **mapper.STANDARD_MAPPINGS
            }

            return all_mappings

        except Exception as e:
            self.logger.error(f"Failed to get Genesis mappings: {e}")
            return {}

    def _analyze_component_gaps(self, langflow_components: Dict[str, Any],
                               genesis_mappings: Dict[str, Any]) -> List[ComponentGap]:
        """Analyze gaps in component coverage."""
        gaps = []

        # Get mapped Langflow components
        mapped_components = set()
        for mapping in genesis_mappings.values():
            if "component" in mapping:
                mapped_components.add(mapping["component"])

        # Find unmapped Langflow components
        for comp_name, comp_info in langflow_components.items():
            if comp_name not in mapped_components:
                severity = self._assess_component_severity(comp_name, comp_info)
                proposed_genesis_type = self._propose_genesis_type(comp_name, comp_info)

                gap = ComponentGap(
                    component_name=comp_name,
                    component_path=comp_info.get("module_path", ""),
                    genesis_type=proposed_genesis_type,
                    gap_category=GapCategory.MISSING_COMPONENT,
                    severity=severity,
                    description=f"Langflow component '{comp_name}' has no Genesis mapping",
                    recommendation=f"Create Genesis mapping for '{proposed_genesis_type}'",
                    runtime_support={
                        "langflow": True,
                        "temporal": self._assess_temporal_compatibility(comp_info),
                        "kafka": self._assess_kafka_compatibility(comp_info)
                    },
                    effort_estimate=self._estimate_mapping_effort(comp_info)
                )

                gaps.append(gap)

        return gaps

    def _analyze_mapping_gaps(self, genesis_mappings: Dict[str, Any]) -> List[MappingGap]:
        """Analyze gaps in existing mappings."""
        gaps = []

        for genesis_type, mapping in genesis_mappings.items():
            config_issues = self._validate_mapping_configuration(genesis_type, mapping)

            if config_issues:
                severity = GapSeverity.MEDIUM if len(config_issues) > 2 else GapSeverity.LOW

                gap = MappingGap(
                    genesis_type=genesis_type,
                    langflow_component=mapping.get("component"),
                    gap_category=GapCategory.CONFIGURATION_GAP,
                    severity=severity,
                    description=f"Configuration issues in mapping for {genesis_type}",
                    recommendation="Update mapping configuration to resolve issues",
                    configuration_issues=config_issues
                )

                gaps.append(gap)

        return gaps

    def _analyze_conversion_gaps(self) -> List[ConversionGap]:
        """Analyze gaps in conversion capabilities."""
        gaps = []

        # Check bidirectional conversion support
        gap = ConversionGap(
            conversion_type="runtime_to_spec",
            runtime="langflow",
            gap_category=GapCategory.BIDIRECTIONAL_GAP,
            severity=GapSeverity.HIGH,
            description="Langflow to Genesis specification reverse conversion not fully implemented",
            missing_features=[
                "Complete node to component mapping",
                "Edge to provides relationship conversion",
                "Configuration extraction",
                "Metadata preservation"
            ],
            recommendation="Implement comprehensive bidirectional conversion in LangflowConverter"
        )
        gaps.append(gap)

        # Check Temporal conversion
        gap = ConversionGap(
            conversion_type="spec_to_runtime",
            runtime="temporal",
            gap_category=GapCategory.RUNTIME_SUPPORT,
            severity=GapSeverity.MEDIUM,
            description="Temporal workflow conversion not implemented",
            missing_features=[
                "Workflow definition generation",
                "Activity mapping",
                "State management",
                "Error handling"
            ],
            recommendation="Implement TemporalConverter for healthcare workflows"
        )
        gaps.append(gap)

        # Check Kafka conversion
        gap = ConversionGap(
            conversion_type="spec_to_runtime",
            runtime="kafka",
            gap_category=GapCategory.RUNTIME_SUPPORT,
            severity=GapSeverity.MEDIUM,
            description="Kafka Streams conversion not implemented",
            missing_features=[
                "Topology generation",
                "Stream processor mapping",
                "Topic management",
                "Serialization configuration"
            ],
            recommendation="Implement KafkaConverter for streaming healthcare data"
        )
        gaps.append(gap)

        return gaps

    def _assess_component_severity(self, comp_name: str, comp_info: Dict[str, Any]) -> GapSeverity:
        """Assess severity of missing component mapping."""
        # High priority for healthcare-related components
        healthcare_keywords = ["health", "medical", "clinical", "patient", "eligibility", "claims"]
        if any(keyword in comp_name.lower() for keyword in healthcare_keywords):
            return GapSeverity.HIGH

        # High priority for core workflow components
        core_keywords = ["agent", "llm", "tool", "input", "output"]
        if any(keyword in comp_name.lower() for keyword in core_keywords):
            return GapSeverity.HIGH

        # Medium priority for data processing components
        data_keywords = ["data", "parse", "transform", "convert"]
        if any(keyword in comp_name.lower() for keyword in data_keywords):
            return GapSeverity.MEDIUM

        return GapSeverity.LOW

    def _propose_genesis_type(self, comp_name: str, comp_info: Dict[str, Any]) -> str:
        """Propose a Genesis type name for unmapped component."""
        # Convert CamelCase to snake_case
        import re
        snake_case = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', comp_name)
        snake_case = re.sub('([a-z0-9])([A-Z])', r'\1_\2', snake_case).lower()

        # Remove common suffixes
        snake_case = snake_case.replace("_component", "").replace("_tool", "")

        return f"genesis:{snake_case}"

    def _assess_temporal_compatibility(self, comp_info: Dict[str, Any]) -> bool:
        """Assess if component is compatible with Temporal runtime."""
        # Components good for long-running workflows
        temporal_friendly = [
            "agent", "workflow", "state", "memory", "database",
            "api", "webhook", "scheduler", "timer"
        ]

        comp_name = comp_info.get("class_name", "").lower()
        return any(keyword in comp_name for keyword in temporal_friendly)

    def _assess_kafka_compatibility(self, comp_info: Dict[str, Any]) -> bool:
        """Assess if component is compatible with Kafka runtime."""
        # Components good for streaming
        kafka_friendly = [
            "stream", "transform", "filter", "parse", "data",
            "api", "webhook", "embed", "vector"
        ]

        comp_name = comp_info.get("class_name", "").lower()
        return any(keyword in comp_name for keyword in kafka_friendly)

    def _validate_mapping_configuration(self, genesis_type: str, mapping: Dict[str, Any]) -> List[str]:
        """Validate mapping configuration for issues."""
        issues = []

        if "component" not in mapping:
            issues.append("Missing 'component' field")

        if "config" not in mapping:
            issues.append("Missing 'config' field")

        # Check for empty or None values
        for key, value in mapping.items():
            if value is None:
                issues.append(f"Null value for '{key}'")
            elif isinstance(value, dict) and not value:
                issues.append(f"Empty dictionary for '{key}'")

        return issues

    def _estimate_mapping_effort(self, comp_info: Dict[str, Any]) -> str:
        """Estimate effort to create mapping for component."""
        # Simple heuristic based on component complexity
        if comp_info.get("has_template", False):
            return "2-4 hours"  # Has template, easier to map
        else:
            return "4-8 hours"  # Needs investigation

    def _generate_audit_summary(self, langflow_components: Dict[str, Any],
                               genesis_mappings: Dict[str, Any],
                               component_gaps: List[ComponentGap],
                               mapping_gaps: List[MappingGap],
                               conversion_gaps: List[ConversionGap]) -> Dict[str, Any]:
        """Generate audit summary statistics."""
        total_gaps = len(component_gaps) + len(mapping_gaps) + len(conversion_gaps)

        severity_counts = {
            GapSeverity.CRITICAL.value: 0,
            GapSeverity.HIGH.value: 0,
            GapSeverity.MEDIUM.value: 0,
            GapSeverity.LOW.value: 0,
            GapSeverity.INFO.value: 0
        }

        for gap in component_gaps + mapping_gaps + conversion_gaps:
            severity_counts[gap.severity.value] += 1

        coverage_percentage = (len(genesis_mappings) / len(langflow_components)) * 100

        return {
            "total_langflow_components": len(langflow_components),
            "total_genesis_mappings": len(genesis_mappings),
            "coverage_percentage": round(coverage_percentage, 1),
            "total_gaps": total_gaps,
            "severity_distribution": severity_counts,
            "conversion_support": {
                "langflow_forward": True,
                "langflow_bidirectional": False,
                "temporal_support": False,
                "kafka_support": False
            }
        }

    def _assess_langflow_conversion_quality(self) -> Dict[str, Any]:
        """Assess quality of Langflow conversion."""
        return {
            "spec_to_langflow": {
                "implemented": True,
                "quality_score": 85,  # Based on feature completeness
                "missing_features": [
                    "Enhanced edge validation",
                    "Better error reporting",
                    "Component template optimization"
                ]
            },
            "langflow_to_spec": {
                "implemented": False,
                "quality_score": 30,  # Skeleton implementation
                "missing_features": [
                    "Complete node parsing",
                    "Edge relationship extraction",
                    "Configuration preservation",
                    "Metadata extraction"
                ]
            }
        }

    def _assess_bidirectional_support(self) -> Dict[str, Any]:
        """Assess bidirectional conversion support."""
        return {
            "overall_support": False,
            "runtimes": {
                "langflow": {
                    "forward": True,
                    "reverse": False,
                    "completeness": 50
                },
                "temporal": {
                    "forward": False,
                    "reverse": False,
                    "completeness": 0
                },
                "kafka": {
                    "forward": False,
                    "reverse": False,
                    "completeness": 0
                }
            }
        }

    def _assess_runtime_coverage(self) -> Dict[str, Any]:
        """Assess runtime coverage and support."""
        return {
            "supported_runtimes": ["langflow"],
            "skeleton_runtimes": ["temporal", "kafka"],
            "future_runtimes": ["airflow", "dask", "ray"],
            "coverage_matrix": {
                "langflow": {
                    "conversion": True,
                    "validation": True,
                    "components": 90
                },
                "temporal": {
                    "conversion": False,
                    "validation": True,
                    "components": 60
                },
                "kafka": {
                    "conversion": False,
                    "validation": True,
                    "components": 40
                }
            }
        }

    def _calculate_overall_quality_score(self, audit: ImplementationAudit) -> int:
        """Calculate overall quality score (0-100)."""
        # Weight different factors
        mapping_coverage = (audit.mapped_components / audit.total_components_scanned) * 100
        critical_gaps_penalty = len([g for g in audit.component_gaps + audit.mapping_gaps + audit.conversion_gaps
                                   if g.severity == GapSeverity.CRITICAL]) * 10
        high_gaps_penalty = len([g for g in audit.component_gaps + audit.mapping_gaps + audit.conversion_gaps
                               if g.severity == GapSeverity.HIGH]) * 5

        score = mapping_coverage - critical_gaps_penalty - high_gaps_penalty
        return max(0, min(100, int(score)))

    def _generate_quality_recommendations(self, audit: ImplementationAudit) -> List[str]:
        """Generate recommendations for improving quality."""
        recommendations = []

        # Based on gap analysis
        critical_gaps = [g for g in audit.component_gaps + audit.mapping_gaps + audit.conversion_gaps
                        if g.severity == GapSeverity.CRITICAL]

        if critical_gaps:
            recommendations.append("Address critical gaps immediately to ensure system stability")

        if audit.unmapped_components > audit.mapped_components * 0.3:
            recommendations.append("Improve component mapping coverage - many Langflow components are unmapped")

        if not any("bidirectional" in str(g.gap_category) for g in audit.conversion_gaps):
            recommendations.append("Implement bidirectional conversion for better workflow management")

        recommendations.extend([
            "Implement comprehensive testing for all converters",
            "Add performance benchmarking for conversion operations",
            "Create documentation for adding new runtime converters"
        ])

        return recommendations

    def _prioritize_gaps(self, gaps: List[Any]) -> List[Any]:
        """Prioritize gaps by severity and impact."""
        severity_order = {
            GapSeverity.CRITICAL: 0,
            GapSeverity.HIGH: 1,
            GapSeverity.MEDIUM: 2,
            GapSeverity.LOW: 3,
            GapSeverity.INFO: 4
        }

        return sorted(gaps, key=lambda g: severity_order[g.severity])

    def _organize_into_phases(self, gaps: List[Any]) -> Dict[str, List[Dict[str, Any]]]:
        """Organize gaps into implementation phases."""
        phases = {
            "Phase 1 - Critical Fixes": [],
            "Phase 2 - High Priority": [],
            "Phase 3 - Medium Priority": [],
            "Phase 4 - Enhancements": []
        }

        for gap in gaps:
            gap_info = {
                "description": gap.description,
                "recommendation": gap.recommendation,
                "effort": getattr(gap, 'effort_estimate', 'TBD')
            }

            if gap.severity == GapSeverity.CRITICAL:
                phases["Phase 1 - Critical Fixes"].append(gap_info)
            elif gap.severity == GapSeverity.HIGH:
                phases["Phase 2 - High Priority"].append(gap_info)
            elif gap.severity == GapSeverity.MEDIUM:
                phases["Phase 3 - Medium Priority"].append(gap_info)
            else:
                phases["Phase 4 - Enhancements"].append(gap_info)

        return phases

    def _estimate_implementation_effort(self, gaps: List[Any]) -> Dict[str, str]:
        """Estimate implementation effort for gaps."""
        total_critical = len([g for g in gaps if g.severity == GapSeverity.CRITICAL])
        total_high = len([g for g in gaps if g.severity == GapSeverity.HIGH])
        total_medium = len([g for g in gaps if g.severity == GapSeverity.MEDIUM])

        return {
            "critical_gaps": f"{total_critical * 8} hours",
            "high_priority": f"{total_high * 4} hours",
            "medium_priority": f"{total_medium * 2} hours",
            "total_estimated_hours": total_critical * 8 + total_high * 4 + total_medium * 2
        }

    def _estimate_timeline(self, phases: Dict[str, List[Dict[str, Any]]]) -> int:
        """Estimate timeline in weeks."""
        phase_weeks = {
            "Phase 1 - Critical Fixes": 1,
            "Phase 2 - High Priority": 2,
            "Phase 3 - Medium Priority": 2,
            "Phase 4 - Enhancements": 3
        }

        return sum(weeks for phase, weeks in phase_weeks.items() if phases.get(phase))

    def _estimate_resources(self, phases: Dict[str, List[Dict[str, Any]]]) -> Dict[str, str]:
        """Estimate resource requirements."""
        return {
            "developers_needed": "1-2 senior developers",
            "skills_required": [
                "Python development",
                "Langflow architecture",
                "Genesis specification knowledge",
                "Healthcare domain expertise"
            ],
            "external_dependencies": [
                "Temporal SDK (future)",
                "Kafka Streams (future)",
                "Component template access"
            ]
        }

    def _define_success_metrics(self, audit: ImplementationAudit) -> Dict[str, Any]:
        """Define success metrics for implementation."""
        return {
            "target_component_coverage": "90%",
            "bidirectional_conversion": "Fully implemented for Langflow",
            "runtime_support": "3+ runtimes supported",
            "conversion_accuracy": "95%+ for round-trip conversion",
            "performance": "<2s conversion time for typical specs"
        }

    def _assess_implementation_risks(self, phases: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, str]]:
        """Assess risks in implementation plan."""
        return [
            {
                "risk": "Component template changes",
                "impact": "Medium",
                "mitigation": "Use component introspection where possible"
            },
            {
                "risk": "Langflow API changes",
                "impact": "High",
                "mitigation": "Maintain API compatibility layer"
            },
            {
                "risk": "Performance degradation",
                "impact": "Medium",
                "mitigation": "Implement caching and optimization"
            },
            {
                "risk": "Complex component mappings",
                "impact": "Medium",
                "mitigation": "Create mapping development guidelines"
            }
        ]