"""Specification Search Tool for Agent Builder."""

import json
from pathlib import Path
from typing import List, Dict, Any

from langflow.custom.custom_component.component import Component
from langflow.inputs import MessageTextInput, IntInput
from langflow.field_typing import RangeSpec
from langflow.io import Output
from langflow.schema.data import Data
from langflow.logging import logger


class SpecificationSearchTool(Component):
    """Search tool for finding specifications in the library."""

    display_name = "Specification Search"
    description = "Search existing agent specifications in the library"
    icon = "search"
    name = "SpecificationSearchTool"
    category = "Helpers"

    inputs = [
        MessageTextInput(
            name="query",
            display_name="Search Query",
            info="Search terms for finding specifications (searches in name, description, domain, and content)",
            placeholder="e.g., 'healthcare', 'chatbot', 'customer support'",
            required=True,
            tool_mode=True,
        ),
        IntInput(
            name="limit",
            display_name="Result Limit",
            info="Maximum number of results to return",
            value=5,
            range_spec=RangeSpec(min=1, max=20, step=1, step_type="int"),
            tool_mode=True,
        ),
        MessageTextInput(
            name="search_path",
            display_name="Search Path",
            info="Base path to search for specifications",
            value="src/backend/base/langflow/specifications_library",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Search Results", name="results", method="search"),
    ]

    def search(self) -> Data:
        """Search specification library for matching specifications."""
        try:
            # Get the base path for specifications
            base_path = Path(self.search_path)
            if not base_path.exists():
                # Try relative to project root
                base_path = Path("src/backend/base/langflow/specifications_library")
                if not base_path.exists():
                    logger.warning(f"Specification library not found at {self.search_path}")
                    return Data(data={
                        "results": [],
                        "message": "Specification library not found",
                        "query": self.query
                    })

            results = []
            search_terms = self.query.lower().split()

            # Search through all YAML files in the specifications library
            for spec_file in base_path.rglob("*.yaml"):
                try:
                    with open(spec_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        content_lower = content.lower()

                        # Check if all search terms are present
                        if all(term in content_lower for term in search_terms):
                            # Try to parse YAML to get structured data
                            import yaml
                            spec_data = yaml.safe_load(content)

                            # Calculate relevance score
                            relevance_score = self._calculate_relevance(
                                spec_data, search_terms, content_lower
                            )

                            results.append({
                                "file": str(spec_file.relative_to(base_path)),
                                "name": spec_data.get("name", "Unknown"),
                                "description": spec_data.get("description", ""),
                                "domain": spec_data.get("domain", ""),
                                "kind": spec_data.get("kind", ""),
                                "relevance_score": relevance_score,
                                "spec_data": spec_data
                            })
                except Exception as e:
                    logger.debug(f"Error processing file {spec_file}: {e}")
                    continue

            # Sort by relevance score
            results.sort(key=lambda x: x["relevance_score"], reverse=True)

            # Limit results
            results = results[:self.limit]

            # Format response
            response = {
                "query": self.query,
                "total_found": len(results),
                "results": results,
                "message": f"Found {len(results)} matching specifications"
            }

            return Data(data=response)

        except Exception as e:
            logger.error(f"Error searching specifications: {e}")
            return Data(data={
                "error": str(e),
                "results": [],
                "query": self.query
            })

    def _calculate_relevance(self, spec_data: Dict[str, Any],
                            search_terms: List[str],
                            content_lower: str) -> float:
        """Calculate relevance score for a specification."""
        score = 0.0

        # Weight different fields
        weights = {
            "name": 3.0,
            "description": 2.0,
            "domain": 2.0,
            "agentGoal": 1.5,
            "kind": 1.0,
        }

        for field, weight in weights.items():
            field_value = str(spec_data.get(field, "")).lower()
            for term in search_terms:
                if term in field_value:
                    score += weight

        # Bonus for exact phrase match
        if " ".join(search_terms) in content_lower:
            score += 5.0

        return score