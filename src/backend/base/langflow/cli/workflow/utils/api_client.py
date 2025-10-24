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
        self.api_key = config_manager.get_api_key()  # Use the new method to get API key from environment

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

    async def export_flow(self, flow_data: Dict[str, Any],
                         preserve_variables: bool = True,
                         include_metadata: bool = False,
                         name_override: Optional[str] = None,
                         description_override: Optional[str] = None,
                         domain_override: Optional[str] = None) -> Dict[str, Any]:
        """Export Langflow flow to Genesis specification."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/spec/export",
                json={
                    "flow_data": flow_data,
                    "preserve_variables": preserve_variables,
                    "include_metadata": include_metadata,
                    "name_override": name_override,
                    "description_override": description_override,
                    "domain_override": domain_override
                },
                headers=self._get_headers(),
                timeout=60.0
            )
            response.raise_for_status()
            return response.json()

    async def export_flows_batch(self, flows: List[Dict[str, Any]],
                                preserve_variables: bool = True,
                                include_metadata: bool = False,
                                domain_override: Optional[str] = None) -> Dict[str, Any]:
        """Export multiple Langflow flows to Genesis specifications."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/spec/export-batch",
                json={
                    "flows": flows,
                    "preserve_variables": preserve_variables,
                    "include_metadata": include_metadata,
                    "domain_override": domain_override
                },
                headers=self._get_headers(),
                timeout=120.0
            )
            response.raise_for_status()
            return response.json()

    async def validate_flow_for_export(self, flow_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Langflow flow for export to Genesis specification."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/spec/validate-for-export",
                json={
                    "flow_data": flow_data
                },
                headers=self._get_headers(),
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()

    # Synchronous wrappers for CLI usage
    def _run_async_safely(self, coro):
        """Safely run an async coroutine, handling event loop conflicts."""
        try:
            # Check if there's already an event loop running
            loop = asyncio.get_running_loop()
            # If we have a running loop, use a thread executor
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result()
        except RuntimeError:
            # No running event loop, use asyncio.run normally
            return asyncio.run(coro)

    def validate_spec_sync(self, spec_yaml: str, detailed: bool = True) -> Dict[str, Any]:
        """Synchronous wrapper for validate_spec."""
        return self._run_async_safely(self.validate_spec(spec_yaml, detailed))

    def convert_spec_sync(self, spec_yaml: str, variables: Optional[Dict[str, Any]] = None,
                         tweaks: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Synchronous wrapper for convert_spec."""
        return self._run_async_safely(self.convert_spec(spec_yaml, variables, tweaks))

    def get_available_components_sync(self) -> Dict[str, Any]:
        """Synchronous wrapper for get_available_components."""
        return self._run_async_safely(self.get_available_components())

    def get_component_mapping_sync(self, spec_type: str) -> Dict[str, Any]:
        """Synchronous wrapper for get_component_mapping."""
        return self._run_async_safely(self.get_component_mapping(spec_type))

    def list_available_specifications_sync(self) -> Dict[str, Any]:
        """Synchronous wrapper for list_available_specifications."""
        return self._run_async_safely(self.list_available_specifications())

    def create_flow_from_library_sync(self, specification_file: str,
                                    folder_id: Optional[str] = None) -> Dict[str, Any]:
        """Synchronous wrapper for create_flow_from_library."""
        return self._run_async_safely(self.create_flow_from_library(specification_file, folder_id))

    def get_flows_sync(self) -> Dict[str, Any]:
        """Synchronous wrapper for get_flows."""
        return self._run_async_safely(self.get_flows())

    def create_flow_sync(self, name: str, data: Dict[str, Any],
                        description: str = "", folder_id: Optional[str] = None) -> Dict[str, Any]:
        """Synchronous wrapper for create_flow."""
        return self._run_async_safely(self.create_flow(name, data, description, folder_id))

    def delete_flow_sync(self, flow_id: str) -> Dict[str, Any]:
        """Synchronous wrapper for delete_flow."""
        return self._run_async_safely(self.delete_flow(flow_id))

    def get_folders_sync(self) -> Dict[str, Any]:
        """Synchronous wrapper for get_folders."""
        return self._run_async_safely(self.get_folders())

    def health_check_sync(self) -> bool:
        """Synchronous wrapper for health_check."""
        return self._run_async_safely(self.health_check())

    def export_flow_sync(self, flow_data: Dict[str, Any],
                        preserve_variables: bool = True,
                        include_metadata: bool = False,
                        name_override: Optional[str] = None,
                        description_override: Optional[str] = None,
                        domain_override: Optional[str] = None) -> Dict[str, Any]:
        """Synchronous wrapper for export_flow."""
        return self._run_async_safely(self.export_flow(
            flow_data=flow_data,
            preserve_variables=preserve_variables,
            include_metadata=include_metadata,
            name_override=name_override,
            description_override=description_override,
            domain_override=domain_override
        ))

    def export_flows_batch_sync(self, flows: List[Dict[str, Any]],
                               preserve_variables: bool = True,
                               include_metadata: bool = False,
                               domain_override: Optional[str] = None) -> Dict[str, Any]:
        """Synchronous wrapper for export_flows_batch."""
        return self._run_async_safely(self.export_flows_batch(
            flows=flows,
            preserve_variables=preserve_variables,
            include_metadata=include_metadata,
            domain_override=domain_override
        ))

    def validate_flow_for_export_sync(self, flow_data: Dict[str, Any]) -> Dict[str, Any]:
        """Synchronous wrapper for validate_flow_for_export."""
        return self._run_async_safely(self.validate_flow_for_export(flow_data))