"""Specification Search Component

Searches existing agent specifications to find similar patterns and reusable components.
Helps identify best practices and accelerate agent development through pattern reuse.
"""

import json
import os
import re
import yaml
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

from langflow.custom.custom_component.component import Component
from langflow.field_typing import Data, Text
from langflow.inputs.inputs import MessageTextInput, DictInput, DropdownInput, IntInput, BoolInput
from langflow.schema.data import Data as DataType
from langflow.schema.message import Message
from langflow.template.field.base import Output


class SpecificationSearchComponent(Component):
    display_name = "Specification Search"
    description = "Searches existing agent specifications to find similar patterns and reusable components"
    documentation = "Helps identify best practices and accelerate development through pattern reuse"
    icon = "search"
    name = "SpecificationSearch"

    inputs = [
        DictInput(
            name="requirements",
            display_name="Requirements",
            info="Requirements from RequirementsGathererComponent to search against",
            required=True,
        ),
        MessageTextInput(
            name="search_terms",
            display_name="Additional Search Terms",
            info="Additional keywords to include in search",
            required=False,
        ),
        DropdownInput(
            name="search_scope",
            display_name="Search Scope",
            options=["all", "healthcare", "similar_domain", "similar_use_case"],
            value="similar_domain",
            info="Scope of the search through specifications",
        ),
        IntInput(
            name="max_results",
            display_name="Maximum Results",
            value=10,
            info="Maximum number of specifications to return",
            range_spec={"min": 1, "max": 50},
        ),
        IntInput(
            name="similarity_threshold",
            display_name="Similarity Threshold",
            value=60,
            info="Minimum similarity percentage to include in results",
            range_spec={"min": 1, "max": 100},
        ),
        BoolInput(
            name="include_components",
            display_name="Include Component Analysis",
            value=True,
            info="Whether to analyze components for reusability",
        ),
    ]

    outputs = [
        Output(display_name="Similar Specifications", name="similar_specs", method="find_similar_specs"),
        Output(display_name="Reusable Components", name="reusable_components", method="find_reusable_components"),
        Output(display_name="Pattern Analysis", name="patterns", method="analyze_patterns"),
        Output(display_name="Best Practices", name="best_practices", method="extract_best_practices"),
        Output(display_name="Search Summary", name="search_summary", method="get_search_summary"),
    ]

    def __init__(self, **data):
        super().__init__(**data)
        self.specs_directory = "/Users/jagveersingh/Developer/studio/ai-studio/src/backend/base/langflow/specifications_library"

    def find_similar_specs(self) -> DataType:
        """Find specifications similar to the requirements"""

        search_results = self._perform_search()
        similar_specs = self._rank_by_similarity(search_results)

        return DataType(value={
            "specifications": similar_specs[:self.max_results],
            "total_found": len(search_results),
            "search_criteria": self._get_search_criteria(),
            "similarity_scores": {spec["name"]: spec["similarity_score"] for spec in similar_specs[:self.max_results]},
        })

    def find_reusable_components(self) -> DataType:
        """Find components that can be reused from similar specifications"""

        if not self.include_components:
            return DataType(value={"message": "Component analysis disabled"})

        similar_specs = self.find_similar_specs().value["specifications"]
        reusable_components = self._analyze_component_reusability(similar_specs)

        return DataType(value={
            "reusable_components": reusable_components,
            "component_categories": self._categorize_components(reusable_components),
            "reuse_recommendations": self._generate_reuse_recommendations(reusable_components),
            "adaptation_required": self._assess_adaptation_needs(reusable_components),
        })

    def analyze_patterns(self) -> DataType:
        """Analyze common patterns in similar specifications"""

        similar_specs = self.find_similar_specs().value["specifications"]
        patterns = self._extract_patterns(similar_specs)

        return DataType(value={
            "architectural_patterns": patterns["architectural"],
            "component_patterns": patterns["components"],
            "integration_patterns": patterns["integrations"],
            "workflow_patterns": patterns["workflows"],
            "pattern_frequency": patterns["frequency"],
        })

    def extract_best_practices(self) -> DataType:
        """Extract best practices from high-quality specifications"""

        similar_specs = self.find_similar_specs().value["specifications"]
        best_practices = self._identify_best_practices(similar_specs)

        return DataType(value={
            "configuration_practices": best_practices["configuration"],
            "security_practices": best_practices["security"],
            "performance_practices": best_practices["performance"],
            "compliance_practices": best_practices["compliance"],
            "naming_conventions": best_practices["naming"],
        })

    def get_search_summary(self) -> DataType:
        """Get summary of search results and recommendations"""

        similar_specs = self.find_similar_specs().value
        reusable_components = self.find_reusable_components().value if self.include_components else {}
        patterns = self.analyze_patterns().value

        summary = self._create_search_summary(similar_specs, reusable_components, patterns)

        return DataType(value=summary)

    def _perform_search(self) -> List[Dict[str, Any]]:
        """Perform the actual search through specification files"""

        search_results = []

        if not os.path.exists(self.specs_directory):
            return search_results

        # Get search criteria
        search_criteria = self._get_search_criteria()

        # Walk through specification directory
        for root, dirs, files in os.walk(self.specs_directory):
            for file in files:
                if file.endswith('.yaml') or file.endswith('.yml'):
                    file_path = os.path.join(root, file)
                    try:
                        spec_data = self._load_specification(file_path)
                        if spec_data and self._matches_search_scope(spec_data, root):
                            similarity_score = self._calculate_similarity(spec_data, search_criteria)
                            if similarity_score >= self.similarity_threshold:
                                search_results.append({
                                    "file_path": file_path,
                                    "specification": spec_data,
                                    "similarity_score": similarity_score,
                                    "category": self._extract_category_from_path(root),
                                })
                    except Exception as e:
                        continue

        return search_results

    def _load_specification(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Load and parse a YAML specification file"""

        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                spec_data = yaml.safe_load(file)
                return spec_data
        except Exception:
            return None

    def _get_search_criteria(self) -> Dict[str, Any]:
        """Extract search criteria from requirements"""

        criteria = {
            "domain": self.requirements.get("metadata", {}).get("domain", ""),
            "agent_type": self.requirements.get("metadata", {}).get("agent_type", ""),
            "use_case": self.requirements.get("metadata", {}).get("use_case_category", ""),
            "complexity": self.requirements.get("metadata", {}).get("complexity_level", ""),
            "integrations": self.requirements.get("technical", {}).get("integration_requirements", []),
            "keywords": self._extract_keywords(),
        }

        return criteria

    def _extract_keywords(self) -> List[str]:
        """Extract keywords from requirements and search terms"""

        keywords = []

        # Extract from agent goal
        agent_goal = self.requirements.get("metadata", {}).get("agent_goal", "")
        if agent_goal:
            keywords.extend(agent_goal.lower().split())

        # Extract from functional requirements
        functional = self.requirements.get("functional", {}).get("primary_functions", [])
        for func in functional:
            keywords.extend(str(func).lower().split())

        # Add search terms
        if self.search_terms:
            keywords.extend(self.search_terms.lower().split())

        # Clean and deduplicate
        keywords = [word.strip(".,!?;:") for word in keywords if len(word) > 2]
        return list(set(keywords))

    def _matches_search_scope(self, spec_data: Dict[str, Any], file_path: str) -> bool:
        """Check if specification matches the search scope"""

        if self.search_scope == "all":
            return True

        if self.search_scope == "healthcare":
            return ("healthcare" in file_path.lower() or
                   spec_data.get("domain") == "healthcare" or
                   "healthcare" in str(spec_data.get("tags", [])).lower())

        if self.search_scope == "similar_domain":
            target_domain = self.requirements.get("metadata", {}).get("domain", "")
            spec_domain = spec_data.get("domain", "")
            return target_domain == spec_domain

        if self.search_scope == "similar_use_case":
            target_use_case = self.requirements.get("metadata", {}).get("use_case_category", "")
            spec_tags = spec_data.get("tags", [])
            return target_use_case in str(spec_tags).lower()

        return True

    def _calculate_similarity(self, spec_data: Dict[str, Any], search_criteria: Dict[str, Any]) -> float:
        """Calculate similarity score between specification and search criteria"""

        total_score = 0
        max_score = 0

        # Domain similarity (weight: 25%)
        domain_weight = 25
        max_score += domain_weight
        if spec_data.get("domain") == search_criteria["domain"]:
            total_score += domain_weight
        elif search_criteria["domain"] in str(spec_data.get("subDomain", "")):
            total_score += domain_weight * 0.7

        # Agent type similarity (weight: 20%)
        agent_type_weight = 20
        max_score += agent_type_weight
        if spec_data.get("kind", "").replace(" ", "_").lower() == search_criteria["agent_type"]:
            total_score += agent_type_weight

        # Use case similarity (weight: 20%)
        use_case_weight = 20
        max_score += use_case_weight
        spec_tags = str(spec_data.get("tags", [])).lower()
        if search_criteria["use_case"] in spec_tags:
            total_score += use_case_weight

        # Keyword similarity (weight: 20%)
        keyword_weight = 20
        max_score += keyword_weight
        keyword_score = self._calculate_keyword_similarity(spec_data, search_criteria["keywords"])
        total_score += keyword_weight * keyword_score

        # Integration similarity (weight: 15%)
        integration_weight = 15
        max_score += integration_weight
        integration_score = self._calculate_integration_similarity(spec_data, search_criteria["integrations"])
        total_score += integration_weight * integration_score

        return (total_score / max_score) * 100 if max_score > 0 else 0

    def _calculate_keyword_similarity(self, spec_data: Dict[str, Any], keywords: List[str]) -> float:
        """Calculate keyword similarity between specification and search keywords"""

        if not keywords:
            return 0.5

        spec_text = self._extract_text_from_spec(spec_data).lower()
        matching_keywords = sum(1 for keyword in keywords if keyword in spec_text)

        return matching_keywords / len(keywords)

    def _calculate_integration_similarity(self, spec_data: Dict[str, Any], target_integrations: List[str]) -> float:
        """Calculate similarity in integration requirements"""

        if not target_integrations:
            return 0.5

        spec_components = spec_data.get("components", [])
        spec_integrations = []

        for component in spec_components:
            comp_type = component.get("type", "")
            if "mcp_tool" in comp_type or "api" in comp_type:
                spec_integrations.append(component.get("config", {}).get("tool_name", ""))

        if not spec_integrations:
            return 0.3

        matching_integrations = 0
        for target_int in target_integrations:
            for spec_int in spec_integrations:
                if target_int.lower() in spec_int.lower():
                    matching_integrations += 1
                    break

        return matching_integrations / len(target_integrations)

    def _extract_text_from_spec(self, spec_data: Dict[str, Any]) -> str:
        """Extract searchable text from specification"""

        text_parts = [
            spec_data.get("name", ""),
            spec_data.get("description", ""),
            spec_data.get("agentGoal", ""),
            " ".join(spec_data.get("tags", [])),
        ]

        # Add component descriptions
        components = spec_data.get("components", [])
        for component in components:
            text_parts.extend([
                component.get("name", ""),
                component.get("description", ""),
                str(component.get("config", {})),
            ])

        return " ".join(text_parts)

    def _rank_by_similarity(self, search_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Rank search results by similarity score"""

        # Sort by similarity score (descending)
        ranked_results = sorted(search_results, key=lambda x: x["similarity_score"], reverse=True)

        # Format results
        formatted_results = []
        for result in ranked_results:
            spec = result["specification"]
            formatted_results.append({
                "name": spec.get("name", "Unknown"),
                "description": spec.get("description", ""),
                "domain": spec.get("domain", ""),
                "kind": spec.get("kind", ""),
                "tags": spec.get("tags", []),
                "similarity_score": result["similarity_score"],
                "category": result["category"],
                "file_path": result["file_path"],
                "components_count": len(spec.get("components", [])),
                "reusability_potential": self._assess_reusability_potential(spec),
            })

        return formatted_results

    def _extract_category_from_path(self, file_path: str) -> str:
        """Extract category from file path"""

        path_parts = file_path.split(os.sep)
        for part in reversed(path_parts):
            if part in ["simple", "multi-tool", "multi-agent", "healthcare", "finance", "patient-experience"]:
                return part

        return "general"

    def _analyze_component_reusability(self, similar_specs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Analyze which components can be reused"""

        reusable_components = []
        component_frequency = {}

        for spec in similar_specs:
            spec_data = self._load_specification(spec["file_path"])
            if not spec_data:
                continue

            components = spec_data.get("components", [])
            for component in components:
                comp_type = component.get("type", "")
                comp_name = component.get("name", "")

                # Track frequency
                key = f"{comp_type}:{comp_name}"
                component_frequency[key] = component_frequency.get(key, 0) + 1

                # Assess reusability
                reusability_score = self._calculate_component_reusability(component, spec_data)

                if reusability_score > 0.6:  # High reusability threshold
                    reusable_components.append({
                        "type": comp_type,
                        "name": comp_name,
                        "description": component.get("description", ""),
                        "config": component.get("config", {}),
                        "reusability_score": reusability_score,
                        "source_spec": spec["name"],
                        "frequency": component_frequency[key],
                        "adaptation_needs": self._identify_adaptation_needs(component),
                    })

        # Remove duplicates and sort by reusability
        unique_components = {}
        for comp in reusable_components:
            key = f"{comp['type']}:{comp['name']}"
            if key not in unique_components or comp["reusability_score"] > unique_components[key]["reusability_score"]:
                unique_components[key] = comp

        return sorted(unique_components.values(), key=lambda x: x["reusability_score"], reverse=True)

    def _calculate_component_reusability(self, component: Dict[str, Any], spec_data: Dict[str, Any]) -> float:
        """Calculate how reusable a component is"""

        reusability_score = 0.5  # Base score

        comp_type = component.get("type", "")

        # Generic components are more reusable
        if comp_type in ["genesis:chat_input", "genesis:chat_output", "genesis:agent", "genesis:prompt_template"]:
            reusability_score += 0.3

        # MCP tools and API components are moderately reusable
        if "mcp_tool" in comp_type or "api" in comp_type:
            reusability_score += 0.2

        # Components with detailed descriptions are more reusable
        if len(component.get("description", "")) > 50:
            reusability_score += 0.1

        # Components with flexible configuration are more reusable
        config = component.get("config", {})
        if isinstance(config, dict) and len(config) > 2:
            reusability_score += 0.1

        return min(reusability_score, 1.0)

    def _categorize_components(self, reusable_components: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """Categorize reusable components by type"""

        categories = {
            "input_output": [],
            "agents": [],
            "tools": [],
            "integrations": [],
            "processing": [],
        }

        for component in reusable_components:
            comp_type = component["type"]
            comp_name = component["name"]

            if "input" in comp_type or "output" in comp_type:
                categories["input_output"].append(comp_name)
            elif "agent" in comp_type:
                categories["agents"].append(comp_name)
            elif "mcp_tool" in comp_type or "api" in comp_type:
                categories["tools"].append(comp_name)
            elif "integration" in comp_name.lower():
                categories["integrations"].append(comp_name)
            else:
                categories["processing"].append(comp_name)

        return categories

    def _assess_reusability_potential(self, spec_data: Dict[str, Any]) -> str:
        """Assess overall reusability potential of a specification"""

        components = spec_data.get("components", [])
        generic_count = 0
        total_count = len(components)

        for component in components:
            comp_type = component.get("type", "")
            if comp_type.startswith("genesis:"):
                generic_count += 1

        if total_count == 0:
            return "low"

        generic_ratio = generic_count / total_count

        if generic_ratio > 0.8:
            return "high"
        elif generic_ratio > 0.5:
            return "medium"
        else:
            return "low"

    def _extract_patterns(self, similar_specs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract common patterns from similar specifications"""

        patterns = {
            "architectural": {},
            "components": {},
            "integrations": {},
            "workflows": {},
            "frequency": {},
        }

        for spec in similar_specs:
            spec_data = self._load_specification(spec["file_path"])
            if not spec_data:
                continue

            # Architectural patterns
            kind = spec_data.get("kind", "")
            patterns["architectural"][kind] = patterns["architectural"].get(kind, 0) + 1

            # Component patterns
            components = spec_data.get("components", [])
            component_types = [comp.get("type", "") for comp in components]
            for comp_type in component_types:
                patterns["components"][comp_type] = patterns["components"].get(comp_type, 0) + 1

            # Integration patterns
            for component in components:
                if "mcp_tool" in component.get("type", ""):
                    tool_name = component.get("config", {}).get("tool_name", "")
                    if tool_name:
                        patterns["integrations"][tool_name] = patterns["integrations"].get(tool_name, 0) + 1

        # Calculate frequency rankings
        for category in ["architectural", "components", "integrations"]:
            total = sum(patterns[category].values())
            patterns["frequency"][category] = {
                pattern: (count / total) * 100
                for pattern, count in patterns[category].items()
            } if total > 0 else {}

        return patterns

    def _identify_best_practices(self, similar_specs: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """Identify best practices from high-quality specifications"""

        best_practices = {
            "configuration": [],
            "security": [],
            "performance": [],
            "compliance": [],
            "naming": [],
        }

        high_quality_specs = [spec for spec in similar_specs if spec["similarity_score"] > 80]

        for spec in high_quality_specs:
            spec_data = self._load_specification(spec["file_path"])
            if not spec_data:
                continue

            # Configuration best practices
            if spec_data.get("variables"):
                best_practices["configuration"].append("Use variables for configurable parameters")

            # Security best practices
            security_info = spec_data.get("securityInfo", {})
            if security_info.get("hipaaCompliant"):
                best_practices["security"].append("Implement HIPAA compliance for healthcare agents")

            if security_info.get("encryption_required"):
                best_practices["security"].append("Require encryption for sensitive data")

            # Performance best practices
            if spec_data.get("kpis"):
                best_practices["performance"].append("Define KPIs for monitoring agent performance")

            # Compliance best practices
            if spec_data.get("domain") == "healthcare" and security_info:
                best_practices["compliance"].append("Include comprehensive security info for healthcare")

            # Naming best practices
            if spec_data.get("name") and "-" in spec_data["name"]:
                best_practices["naming"].append("Use kebab-case for agent names")

        # Remove duplicates
        for category in best_practices:
            best_practices[category] = list(set(best_practices[category]))

        return best_practices

    def _generate_reuse_recommendations(self, reusable_components: List[Dict[str, Any]]) -> List[str]:
        """Generate recommendations for component reuse"""

        recommendations = []

        if not reusable_components:
            recommendations.append("No highly reusable components found. Consider creating custom components.")
            return recommendations

        # Group by type
        by_type = {}
        for comp in reusable_components:
            comp_type = comp["type"]
            if comp_type not in by_type:
                by_type[comp_type] = []
            by_type[comp_type].append(comp)

        # Generate recommendations
        for comp_type, components in by_type.items():
            best_component = max(components, key=lambda x: x["reusability_score"])
            recommendations.append(
                f"Reuse {comp_type} from '{best_component['source_spec']}' "
                f"(reusability score: {best_component['reusability_score']:.1f})"
            )

        if len(reusable_components) > 5:
            recommendations.append(f"Found {len(reusable_components)} reusable components. Prioritize top 5.")

        return recommendations

    def _assess_adaptation_needs(self, reusable_components: List[Dict[str, Any]]) -> Dict[str, str]:
        """Assess what adaptations are needed for reusable components"""

        adaptation_needs = {}

        for component in reusable_components:
            needs = self._identify_adaptation_needs(component)
            key = f"{component['type']}:{component['name']}"
            adaptation_needs[key] = needs

        return adaptation_needs

    def _identify_adaptation_needs(self, component: Dict[str, Any]) -> str:
        """Identify what adaptations are needed for a component"""

        config = component.get("config", {})

        if not config:
            return "minimal"

        # Check for hard-coded values
        config_str = str(config)
        if any(keyword in config_str.lower() for keyword in ["localhost", "127.0.0.1", "test", "demo"]):
            return "significant"

        if len(config) > 5:
            return "moderate"

        return "minimal"

    def _create_search_summary(self, similar_specs: Dict[str, Any], reusable_components: Dict[str, Any], patterns: Dict[str, Any]) -> Dict[str, Any]:
        """Create comprehensive search summary"""

        summary = {
            "search_overview": {
                "total_specs_found": similar_specs["total_found"],
                "specs_returned": len(similar_specs["specifications"]),
                "average_similarity": sum(similar_specs["similarity_scores"].values()) / len(similar_specs["similarity_scores"]) if similar_specs["similarity_scores"] else 0,
                "search_scope": self.search_scope,
            },
            "reusability_analysis": {
                "reusable_components_found": len(reusable_components.get("reusable_components", [])),
                "highest_reusability_score": max([comp["reusability_score"] for comp in reusable_components.get("reusable_components", [])], default=0),
                "component_categories": list(reusable_components.get("component_categories", {}).keys()),
            },
            "pattern_insights": {
                "most_common_architecture": max(patterns["architectural"].items(), key=lambda x: x[1])[0] if patterns["architectural"] else None,
                "most_used_components": list(patterns["frequency"].get("components", {}).keys())[:3],
                "common_integrations": list(patterns["frequency"].get("integrations", {}).keys())[:3],
            },
            "recommendations": self._generate_summary_recommendations(similar_specs, reusable_components, patterns),
        }

        return summary

    def _generate_summary_recommendations(self, similar_specs: Dict[str, Any], reusable_components: Dict[str, Any], patterns: Dict[str, Any]) -> List[str]:
        """Generate high-level recommendations based on search results"""

        recommendations = []

        # Similarity-based recommendations
        if similar_specs["total_found"] > 5:
            recommendations.append(f"Found {similar_specs['total_found']} similar specifications. Consider adapting the highest-scoring ones.")
        elif similar_specs["total_found"] > 0:
            recommendations.append("Few similar specifications found. You may need more custom development.")
        else:
            recommendations.append("No similar specifications found. This appears to be a novel use case.")

        # Component reusability recommendations
        reusable_count = len(reusable_components.get("reusable_components", []))
        if reusable_count > 10:
            recommendations.append(f"Excellent component reusability: {reusable_count} components can be reused.")
        elif reusable_count > 5:
            recommendations.append(f"Good component reusability: {reusable_count} components can be reused.")
        elif reusable_count > 0:
            recommendations.append(f"Limited reusability: {reusable_count} components can be reused.")

        # Pattern-based recommendations
        if patterns["architectural"]:
            most_common = max(patterns["architectural"].items(), key=lambda x: x[1])[0]
            recommendations.append(f"Consider using '{most_common}' architecture pattern (most common in similar specs).")

        return recommendations