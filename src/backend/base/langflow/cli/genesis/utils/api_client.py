"""API client for communicating with AI Studio backend."""

import asyncio
import json
from typing import Dict, Any, Optional, List
from pathlib import Path

import httpx
import yaml

from ..config.manager import ConfigManager


class APIClient:
    """Client for AI Studio Genesis API endpoints."""

    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager.get_config()
        self.base_url = str(self.config.ai_studio.url).rstrip('/')
        self.api_key = self.config.ai_studio.api_key

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers with authentication."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        return headers

    async def validate_spec(self, spec_yaml: str, detailed: bool = True) -> Dict[str, Any]:
        """Validate a Genesis specification."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/spec/validate",
                json={
                    "spec_yaml": spec_yaml,
                    "detailed": detailed,
                    "format_report": True
                },
                headers=self._get_headers(),
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()

    async def convert_spec(self, spec_yaml: str, variables: Optional[Dict[str, Any]] = None,
                          tweaks: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Convert specification to flow JSON."""
        async with httpx.AsyncClient() as client:
            request_data = {"spec_yaml": spec_yaml}
            if variables:
                request_data["variables"] = variables
            if tweaks:
                request_data["tweaks"] = tweaks

            response = await client.post(
                f"{self.base_url}/api/v1/spec/convert",
                json=request_data,
                headers=self._get_headers(),
                timeout=60.0
            )
            response.raise_for_status()
            return response.json()

    async def get_available_components(self) -> Dict[str, Any]:
        """Get available Genesis components."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/spec/components",
                headers=self._get_headers(),
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()

    async def get_component_mapping(self, spec_type: str) -> Dict[str, Any]:
        """Get component mapping information."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/spec/component-mapping",
                json={"spec_type": spec_type},
                headers=self._get_headers(),
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()

    async def list_available_specifications(self) -> Dict[str, Any]:
        """List available specifications in the library."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/spec/available-specifications",
                headers=self._get_headers(),
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()

    async def create_flow_from_library(self, specification_file: str,
                                     folder_id: Optional[str] = None) -> Dict[str, Any]:
        """Create flow from specification library."""
        async with httpx.AsyncClient() as client:
            request_data = {"specification_file": specification_file}
            if folder_id:
                request_data["folder_id"] = folder_id

            response = await client.post(
                f"{self.base_url}/api/v1/spec/create-flow-from-library",
                json=request_data,
                headers=self._get_headers(),
                timeout=60.0
            )
            response.raise_for_status()
            return response.json()

    async def get_flows(self) -> Dict[str, Any]:
        """Get list of flows from AI Studio."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/flows/",
                headers=self._get_headers(),
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()

    async def create_flow(self, name: str, data: Dict[str, Any],
                         description: str = "", folder_id: Optional[str] = None) -> Dict[str, Any]:
        """Create a new flow in AI Studio."""
        async with httpx.AsyncClient() as client:
            request_data = {
                "name": name,
                "description": description,
                "data": data
            }
            if folder_id:
                request_data["folder_id"] = folder_id

            response = await client.post(
                f"{self.base_url}/api/v1/flows/",
                json=request_data,
                headers=self._get_headers(),
                timeout=60.0
            )
            response.raise_for_status()
            return response.json()

    async def delete_flow(self, flow_id: str) -> Dict[str, Any]:
        """Delete a flow from AI Studio."""
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.base_url}/api/v1/flows/{flow_id}",
                headers=self._get_headers(),
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()

    async def get_folders(self) -> Dict[str, Any]:
        """Get list of folders from AI Studio."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/folders/",
                headers=self._get_headers(),
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()

    async def health_check(self) -> bool:
        """Check if AI Studio is accessible."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/health",
                    timeout=10.0
                )
                return response.status_code == 200
        except Exception:
            return False

    # Synchronous wrappers for CLI usage
    def validate_spec_sync(self, spec_yaml: str, detailed: bool = True) -> Dict[str, Any]:
        """Synchronous wrapper for validate_spec."""
        return asyncio.run(self.validate_spec(spec_yaml, detailed))

    def convert_spec_sync(self, spec_yaml: str, variables: Optional[Dict[str, Any]] = None,
                         tweaks: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Synchronous wrapper for convert_spec."""
        return asyncio.run(self.convert_spec(spec_yaml, variables, tweaks))

    def get_available_components_sync(self) -> Dict[str, Any]:
        """Synchronous wrapper for get_available_components."""
        return asyncio.run(self.get_available_components())

    def get_component_mapping_sync(self, spec_type: str) -> Dict[str, Any]:
        """Synchronous wrapper for get_component_mapping."""
        return asyncio.run(self.get_component_mapping(spec_type))

    def list_available_specifications_sync(self) -> Dict[str, Any]:
        """Synchronous wrapper for list_available_specifications."""
        return asyncio.run(self.list_available_specifications())

    def create_flow_from_library_sync(self, specification_file: str,
                                    folder_id: Optional[str] = None) -> Dict[str, Any]:
        """Synchronous wrapper for create_flow_from_library."""
        return asyncio.run(self.create_flow_from_library(specification_file, folder_id))

    def get_flows_sync(self) -> Dict[str, Any]:
        """Synchronous wrapper for get_flows."""
        return asyncio.run(self.get_flows())

    def create_flow_sync(self, name: str, data: Dict[str, Any],
                        description: str = "", folder_id: Optional[str] = None) -> Dict[str, Any]:
        """Synchronous wrapper for create_flow."""
        return asyncio.run(self.create_flow(name, data, description, folder_id))

    def delete_flow_sync(self, flow_id: str) -> Dict[str, Any]:
        """Synchronous wrapper for delete_flow."""
        return asyncio.run(self.delete_flow(flow_id))

    def get_folders_sync(self) -> Dict[str, Any]:
        """Synchronous wrapper for get_folders."""
        return asyncio.run(self.get_folders())

    def health_check_sync(self) -> bool:
        """Synchronous wrapper for health_check."""
        return asyncio.run(self.health_check())