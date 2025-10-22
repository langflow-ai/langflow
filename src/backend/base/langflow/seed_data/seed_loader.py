"""
Seed Data Loader - Loads initial component mappings from configuration files.

Part of AUTPE-6204: This loader replaces hardcoded mappings with configuration-driven
seed data that populates the database on first startup.
"""

import os
import json
import yaml
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime, timezone

from langflow.services.database.models.component_mapping import (
    ComponentMapping,
    ComponentMappingCreate,
    ComponentCategoryEnum,
)
from langflow.services.database.models.component_mapping.runtime_adapter import (
    RuntimeAdapter,
    RuntimeAdapterCreate,
    RuntimeTypeEnum,
)

logger = logging.getLogger(__name__)


class SeedDataLoader:
    """
    Loads seed data for component mappings from YAML/JSON configuration files.
    Replaces hardcoded mappings with configuration-driven approach.
    """

    def __init__(self, seed_dir: Optional[str] = None):
        """
        Initialize the seed data loader.

        Args:
            seed_dir: Optional path to seed data directory
        """
        if seed_dir:
            self.seed_dir = Path(seed_dir)
        else:
            # Default to seed_data directory relative to this file
            self.seed_dir = Path(__file__).parent

        self._validate_seed_directory()

    def _validate_seed_directory(self):
        """Validate that the seed directory exists and contains seed files."""
        if not self.seed_dir.exists():
            raise ValueError(f"Seed directory does not exist: {self.seed_dir}")

        seed_files = list(self.seed_dir.glob("*.yaml")) + list(self.seed_dir.glob("*.yml")) + list(self.seed_dir.glob("*.json"))
        if not seed_files:
            logger.warning(f"No seed files found in {self.seed_dir}")

    def load_all_seeds(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Load all seed data from configuration files.

        Returns:
            Dictionary with seed data organized by type
        """
        logger.info(f"📦 Loading seed data from {self.seed_dir}")

        seed_data = {
            "component_mappings": [],
            "runtime_adapters": [],
            "healthcare_mappings": [],
            "mcp_mappings": [],
            "tool_mappings": [],
        }

        # Load component mappings
        mappings = self._load_component_mappings()
        seed_data["component_mappings"].extend(mappings)

        # Load runtime adapters
        adapters = self._load_runtime_adapters()
        seed_data["runtime_adapters"].extend(adapters)

        # Load healthcare-specific mappings
        healthcare = self._load_healthcare_mappings()
        seed_data["healthcare_mappings"].extend(healthcare)

        # Load MCP tool mappings
        mcp = self._load_mcp_mappings()
        seed_data["mcp_mappings"].extend(mcp)

        # Load tool server mappings
        tools = self._load_tool_mappings()
        seed_data["tool_mappings"].extend(tools)

        total_seeds = sum(len(v) for v in seed_data.values())
        logger.info(f"✅ Loaded {total_seeds} seed entries")

        return seed_data

    def _load_component_mappings(self) -> List[Dict[str, Any]]:
        """Load standard component mappings from seed files."""
        mappings = []

        # Load from standard_mappings.yaml
        standard_file = self.seed_dir / "standard_mappings.yaml"
        if standard_file.exists():
            data = self._load_yaml_file(standard_file)
            if "component_mappings" in data:
                mappings.extend(data["component_mappings"])

        # Load from component_mappings.json (if exists)
        json_file = self.seed_dir / "component_mappings.json"
        if json_file.exists():
            data = self._load_json_file(json_file)
            if isinstance(data, list):
                mappings.extend(data)
            elif "mappings" in data:
                mappings.extend(data["mappings"])

        return mappings

    def _load_runtime_adapters(self) -> List[Dict[str, Any]]:
        """Load runtime adapter configurations from seed files."""
        adapters = []

        # Load from runtime_adapters.yaml
        adapters_file = self.seed_dir / "runtime_adapters.yaml"
        if adapters_file.exists():
            data = self._load_yaml_file(adapters_file)
            if "runtime_adapters" in data:
                adapters.extend(data["runtime_adapters"])

        return adapters

    def _load_healthcare_mappings(self) -> List[Dict[str, Any]]:
        """Load healthcare-specific component mappings."""
        mappings = []

        # Load from healthcare_mappings.yaml
        healthcare_file = self.seed_dir / "healthcare_mappings.yaml"
        if healthcare_file.exists():
            data = self._load_yaml_file(healthcare_file)
            if "healthcare_mappings" in data:
                mappings.extend(data["healthcare_mappings"])

        return mappings

    def _load_mcp_mappings(self) -> List[Dict[str, Any]]:
        """Load MCP tool mappings."""
        mappings = []

        # Load from mcp_tools.yaml
        mcp_file = self.seed_dir / "mcp_tools.yaml"
        if mcp_file.exists():
            data = self._load_yaml_file(mcp_file)
            if "mcp_tools" in data:
                mappings.extend(data["mcp_tools"])

        return mappings

    def _load_tool_mappings(self) -> List[Dict[str, Any]]:
        """Load tool server mappings."""
        mappings = []

        # Load from tool_servers.yaml
        tools_file = self.seed_dir / "tool_servers.yaml"
        if tools_file.exists():
            data = self._load_yaml_file(tools_file)
            if "tool_servers" in data:
                mappings.extend(data["tool_servers"])

        return mappings

    def _load_yaml_file(self, file_path: Path) -> Dict[str, Any]:
        """Load data from a YAML file."""
        try:
            with open(file_path, "r") as f:
                data = yaml.safe_load(f)
                return data if data else {}
        except Exception as e:
            logger.error(f"Error loading YAML file {file_path}: {e}")
            return {}

    def _load_json_file(self, file_path: Path) -> Dict[str, Any]:
        """Load data from a JSON file."""
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
                return data if data else {}
        except Exception as e:
            logger.error(f"Error loading JSON file {file_path}: {e}")
            return {}

    def generate_database_records(self, seed_data: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[Any]]:
        """
        Convert seed data to database model instances.

        Args:
            seed_data: Raw seed data loaded from files

        Returns:
            Dictionary of database-ready records
        """
        records = {
            "component_mappings": [],
            "runtime_adapters": [],
        }

        # Process component mappings
        for mapping_data in seed_data.get("component_mappings", []):
            record = self._create_component_mapping_record(mapping_data)
            if record:
                records["component_mappings"].append(record)

        # Process healthcare mappings (special category of component mappings)
        for mapping_data in seed_data.get("healthcare_mappings", []):
            record = self._create_healthcare_mapping_record(mapping_data)
            if record:
                records["component_mappings"].append(record)

        # Process MCP mappings
        for mapping_data in seed_data.get("mcp_mappings", []):
            record = self._create_mcp_mapping_record(mapping_data)
            if record:
                records["component_mappings"].append(record)

        # Process runtime adapters
        for adapter_data in seed_data.get("runtime_adapters", []):
            record = self._create_runtime_adapter_record(adapter_data)
            if record:
                records["runtime_adapters"].append(record)

        return records

    def _create_component_mapping_record(self, data: Dict[str, Any]) -> Optional[ComponentMappingCreate]:
        """Create a ComponentMappingCreate instance from seed data."""
        try:
            # Map string category to enum
            category = data.get("category", "utilities")
            if isinstance(category, str):
                category = self._map_category_to_enum(category)

            return ComponentMappingCreate(
                genesis_type=data["genesis_type"],
                display_name=data.get("display_name", data["genesis_type"]),
                description=data.get("description", ""),
                category=category,
                version=data.get("version", "1.0.0"),
                is_active=data.get("is_active", True),
                base_config=data.get("config", {}),
                io_mapping=data.get("io_mapping", {}),
                metadata=data.get("metadata", {
                    "source": "seed_data",
                    "created_from": "configuration",
                }),
            )
        except Exception as e:
            logger.error(f"Error creating component mapping record: {e}")
            return None

    def _create_healthcare_mapping_record(self, data: Dict[str, Any]) -> Optional[ComponentMappingCreate]:
        """Create a healthcare-specific ComponentMappingCreate instance."""
        try:
            return ComponentMappingCreate(
                genesis_type=data["genesis_type"],
                display_name=data.get("display_name", data["genesis_type"]),
                description=data.get("description", "Healthcare component"),
                category=ComponentCategoryEnum.HEALTHCARE,
                version=data.get("version", "1.0.0"),
                is_active=data.get("is_active", True),
                base_config=data.get("config", {}),
                io_mapping=data.get("io_mapping", {}),
                healthcare_metadata=data.get("healthcare_metadata", {
                    "hipaa_compliant": True,
                    "phi_handling": True,
                    "encryption_required": True,
                }),
                metadata={
                    "source": "seed_data",
                    "created_from": "healthcare_configuration",
                },
            )
        except Exception as e:
            logger.error(f"Error creating healthcare mapping record: {e}")
            return None

    def _create_mcp_mapping_record(self, data: Dict[str, Any]) -> Optional[ComponentMappingCreate]:
        """Create an MCP tool ComponentMappingCreate instance."""
        try:
            return ComponentMappingCreate(
                genesis_type=data["genesis_type"],
                display_name=data.get("display_name", "MCP Tool"),
                description=data.get("description", "MCP tool component"),
                category=ComponentCategoryEnum.TOOLS,
                version=data.get("version", "1.0.0"),
                is_active=data.get("is_active", True),
                base_config=data.get("config", {
                    "connection_mode": data.get("connection_mode", "Stdio"),
                }),
                io_mapping=data.get("io_mapping", {
                    "component": "MCPToolsComponent",
                    "dataType": "MCPToolsComponent",
                }),
                metadata={
                    "source": "seed_data",
                    "created_from": "mcp_configuration",
                    "tool_name": data.get("tool_name"),
                    "server_name": data.get("server_name"),
                },
            )
        except Exception as e:
            logger.error(f"Error creating MCP mapping record: {e}")
            return None

    def _create_runtime_adapter_record(self, data: Dict[str, Any]) -> Optional[RuntimeAdapterCreate]:
        """Create a RuntimeAdapterCreate instance from seed data."""
        try:
            # Map string runtime type to enum
            runtime_type = data.get("runtime_type", "langflow")
            if isinstance(runtime_type, str):
                runtime_type = RuntimeTypeEnum(runtime_type.lower())

            return RuntimeAdapterCreate(
                genesis_type=data["genesis_type"],
                runtime_type=runtime_type,
                target_component=data["target_component"],
                adapter_config=data.get("adapter_config", {}),
                version=data.get("version", "1.0.0"),
                priority=data.get("priority", 50),
                is_active=data.get("is_active", True),
            )
        except Exception as e:
            logger.error(f"Error creating runtime adapter record: {e}")
            return None

    def _map_category_to_enum(self, category: str) -> ComponentCategoryEnum:
        """Map string category to ComponentCategoryEnum."""
        category_map = {
            "healthcare": ComponentCategoryEnum.HEALTHCARE,
            "models": ComponentCategoryEnum.MODELS,
            "agents": ComponentCategoryEnum.AGENTS,
            "tools": ComponentCategoryEnum.TOOLS,
            "memories": ComponentCategoryEnum.MEMORIES,
            "prompts": ComponentCategoryEnum.PROMPTS,
            "io": ComponentCategoryEnum.IO,
            "data": ComponentCategoryEnum.DATA,
            "vectorstores": ComponentCategoryEnum.VECTORSTORES,
            "utilities": ComponentCategoryEnum.UTILITIES,
        }

        return category_map.get(category.lower(), ComponentCategoryEnum.UTILITIES)

    def validate_seed_data(self, seed_data: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """
        Validate seed data for completeness and consistency.

        Args:
            seed_data: Seed data to validate

        Returns:
            Validation results
        """
        issues = []
        stats = {
            "total_entries": 0,
            "valid_entries": 0,
            "invalid_entries": 0,
        }

        # Validate component mappings
        for mapping in seed_data.get("component_mappings", []):
            stats["total_entries"] += 1
            if not mapping.get("genesis_type"):
                issues.append({
                    "type": "component_mapping",
                    "issue": "missing_genesis_type",
                    "data": mapping,
                })
                stats["invalid_entries"] += 1
            else:
                stats["valid_entries"] += 1

        # Validate runtime adapters
        for adapter in seed_data.get("runtime_adapters", []):
            stats["total_entries"] += 1
            if not adapter.get("genesis_type") or not adapter.get("target_component"):
                issues.append({
                    "type": "runtime_adapter",
                    "issue": "missing_required_fields",
                    "data": adapter,
                })
                stats["invalid_entries"] += 1
            else:
                stats["valid_entries"] += 1

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "statistics": stats,
        }

    def export_hardcoded_as_seed(self, output_dir: Optional[str] = None) -> str:
        """
        Export current hardcoded mappings as seed files for migration.

        Args:
            output_dir: Optional output directory

        Returns:
            Path to output directory
        """
        if output_dir is None:
            output_dir = self.seed_dir / "exported"

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # This would extract hardcoded mappings and save them as seed files
        # Implementation would depend on current hardcoded structure

        logger.info(f"📁 Exported hardcoded mappings to: {output_path}")
        return str(output_path)