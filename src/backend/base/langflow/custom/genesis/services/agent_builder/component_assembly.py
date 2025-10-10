"""
Component Assembly Engine for Agent Builder

Assembles and validates component chains with healthcare compliance rules.
Adapted from Genesis ComponentAssemblyEngine for service context.
"""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from .kb_loader import ComponentSpec
from .semantic_search import ComponentMatch


@dataclass
class AssemblyResult:
    """Result of component assembly"""
    components: List[ComponentMatch]
    compatibility_score: float
    validation_passed: bool
    healthcare_compliant: bool
    reasoning: str


class ComponentAssemblyEngine:
    """Engine for assembling and validating component chains"""

    def __init__(self, kb_loader):
        self.logger = logging.getLogger(__name__)
        self.kb_loader = kb_loader

    def assemble_chain(self, component_matches: List[ComponentMatch]) -> AssemblyResult:
        """
        Assemble and validate a chain of components

        Args:
            component_matches: List of component matches from semantic search

        Returns:
            Assembly result with validation and scoring
        """
        try:
            # Basic chain assembly - for now, just validate compatibility
            validation_passed = self._validate_chain_compatibility(component_matches)
            healthcare_compliant = self._validate_healthcare_compliance(component_matches)
            compatibility_score = self._calculate_chain_score(component_matches)

            reasoning = self._generate_assembly_reasoning(
                validation_passed, healthcare_compliant, compatibility_score
            )

            return AssemblyResult(
                components=component_matches,
                compatibility_score=compatibility_score,
                validation_passed=validation_passed,
                healthcare_compliant=healthcare_compliant,
                reasoning=reasoning
            )

        except Exception as e:
            self.logger.error(f"Error in component assembly: {e}")
            return AssemblyResult(
                components=component_matches[:3],  # Return first 3 as fallback
                compatibility_score=0.5,
                validation_passed=False,
                healthcare_compliant=False,
                reasoning=f"Assembly failed: {str(e)}"
            )

    def _validate_chain_compatibility(self, components: List[ComponentMatch]) -> bool:
        """Validate data flow compatibility between components"""
        if len(components) <= 1:
            return True  # Single component is always compatible

        for i in range(len(components) - 1):
            current_comp = components[i].component_spec
            next_comp = components[i + 1].component_spec

            if not self._components_compatible(current_comp, next_comp):
                self.logger.warning(f"Incompatible components: {current_comp.name} -> {next_comp.name}")
                return False

        return True

    def _components_compatible(self, comp_a: ComponentSpec, comp_b: ComponentSpec) -> bool:
        """Check if two components are compatible for data flow"""
        # Check if component B can accept output from component A
        compatible = False

        for output_type in comp_a.output_data_types:
            if output_type in comp_b.input_data_types:
                compatible = True
                break

        # Also check component type acceptance rules
        if comp_b.accepts_input_from:
            for pattern in comp_b.accepts_input_from:
                if '*' in pattern:
                    # Wildcard matching
                    if comp_a.component_type.startswith(pattern.split('*')[0]):
                        compatible = True
                        break
                elif comp_a.component_type == pattern:
                    compatible = True
                    break

        return compatible

    def _validate_healthcare_compliance(self, components: List[ComponentMatch]) -> bool:
        """Validate healthcare compliance of component chain"""
        # Basic healthcare validation rules

        # Rule 1: Must have at least one healthcare-capable component
        has_healthcare_component = any(
            "healthcare" in comp.component_spec.category.lower() or
            any("medical" in cap.lower() or "clinical" in cap.lower()
                for cap in comp.component_spec.capabilities)
            for comp in components
        )

        if not has_healthcare_component:
            self.logger.warning("No healthcare-capable components in chain")
            return False

        # Rule 2: Avoid incompatible component combinations
        # (e.g., don't mix highly sensitive medical data with generic processors)
        sensitive_components = ["extraction_agent", "clinical_validator"]
        generic_components = ["calculator", "generic_processor"]

        has_sensitive = any(comp.component_spec.component_type in sensitive_components
                          for comp in components)
        has_generic = any(comp.component_spec.component_type in generic_components
                         for comp in components)

        if has_sensitive and has_generic:
            self.logger.warning("Mixing sensitive and generic components")
            # Allow but with warning - not a hard failure for MVP

        return True

    def _calculate_chain_score(self, components: List[ComponentMatch]) -> float:
        """Calculate overall chain compatibility score (0-1)"""
        if not components:
            return 0.0

        # Average of individual component scores
        total_score = sum(comp.overall_score for comp in components)
        avg_score = total_score / len(components)

        # Bonus for chain compatibility
        compatibility_bonus = 0.1 if self._validate_chain_compatibility(components) else 0.0

        # Healthcare compliance bonus
        healthcare_bonus = 0.1 if self._validate_healthcare_compliance(components) else 0.0

        final_score = min(1.0, avg_score + compatibility_bonus + healthcare_bonus)
        return final_score

    def _generate_assembly_reasoning(self, validation_passed: bool,
                                   healthcare_compliant: bool,
                                   compatibility_score: float) -> str:
        """Generate human-readable reasoning for assembly result"""
        reasons = []

        if validation_passed:
            reasons.append("Components are data-flow compatible")
        else:
            reasons.append("Some components may have data flow issues")

        if healthcare_compliant:
            reasons.append("Healthcare compliance validated")
        else:
            reasons.append("Healthcare compliance concerns identified")

        reasons.append(f"Overall compatibility score: {compatibility_score:.2f}")

        return "; ".join(reasons)
