"""Knowledge Hub Component for loading files from Knowledge Hub."""

from __future__ import annotations

from typing import Any

from langflow.custom import Component
from langflow.io import BoolInput, DropdownInput, Output
from langflow.schema.data import Data
from langflow.custom.genesis.services.deps import get_knowledge_service
from loguru import logger


class KnowledgeHub(Component):
    """Component for loading files from Knowledge Hub."""

    display_name = "Knowledge Hub"
    description = "Load files from Knowledge Hub"
    documentation = "http://docs.langflow.org/components/custom"
    icon = "Autonomize"
    name = "KnowledgeHub"

    FILE_PATH_FIELD = "file_path"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._hub_list: list[dict[str, str]] = []
        self._file_list: list[str] = []

    async def _ensure_hub_data(self) -> None:
        """Ensure hub data is loaded."""
        if not self._hub_list:
            logger.debug("Hub list is empty, retrieving from service...")
            try:
                service = get_knowledge_service()
                if not service.ready:
                    logger.error("KnowledgeHub service is not ready")
                    return
                self._hub_list = await service.get_knowledge_hubs()
                logger.debug(f"Retrieved hub data: {self._hub_list}")
            except Exception as e:
                logger.error(f"Error getting knowledge service: {e!s}")
                return

    inputs = [
        DropdownInput(
            name="selected_hub",
            display_name="Data Source",
            info="Select a knowledge hub",
            required=False,
            refresh_button=True,
            real_time_refresh=True,
        ),
        DropdownInput(
            name="file_name",
            display_name="File",
            info="Select a file from the knowledge hub",
            required=False,
            refresh_button=True,
            real_time_refresh=True,
        ),
        BoolInput(
            name="return_all_files",
            display_name="Return All Files",
            info="If true and no specific file is selected, returns all files in the hub",
            value=True,
        ),
    ]

    outputs = [
        Output(
            name="file_path",
            display_name="File Path",
            method="get_file_paths",
        ),
    ]

    async def update_build_config(
        self, build_config: dict, field_value: Any, field_name: str | None = None
    ):
        """Update the build configuration based on field changes."""
        logger.info(f"update_build_config called with field_name: {field_name}")

        await self._ensure_hub_data()
        selected_hub = getattr(self, "selected_hub", None)
        logger.debug(f"selected_hub: {selected_hub}")
        logger.debug(f"hub list count: {len(self._hub_list)}")

        if field_name == "selected_hub":
            try:
                options = [hub["name"] for hub in self._hub_list]
                logger.info(f"Extracted hub options: {options}")
                build_config["selected_hub"]["options"] = options

                if field_value:
                    self.selected_hub = field_value
                    # Trigger file list update
                    hub_id = next(
                        (
                            hub["id"]
                            for hub in self._hub_list
                            if hub["name"] == field_value
                        ),
                        None,
                    )
                    if hub_id:
                        try:
                            service = get_knowledge_service()
                            if not service.ready:
                                logger.error("KnowledgeHub service is not ready")
                                return build_config
                            files = await service.get_knowledge_hub_documents(hub_id)
                            self._file_list = [
                                file["name"]
                                for file in files
                                if file.get("documentType") != "DS_Store"
                            ]
                            self._file_list.sort()
                            build_config["file_name"]["options"] = self._file_list
                        except Exception as e:
                            logger.error(f"Error getting files: {e!s}")
                            return build_config

            except Exception as e:
                logger.exception(f"Error updating hub list: {e!s}")
                raise

        elif field_name == "file_name" and self.selected_hub:
            try:
                # Get the hub ID for the selected hub
                hub_id = next(
                    (
                        hub["id"]
                        for hub in self._hub_list
                        if hub["name"] == selected_hub
                    ),
                    None,
                )

                if hub_id:
                    # Load the file options when the field is refreshed
                    try:
                        service = get_knowledge_service()
                        if not service.ready:
                            logger.error("KnowledgeHub service is not ready")
                            return build_config
                        files = await service.get_knowledge_hub_documents(hub_id)

                        # Use full path as the file name
                        self._file_list = [
                            file["name"]
                            for file in files
                            if file.get("documentType") != "DS_Store"
                        ]
                        self._file_list.sort()

                        build_config["file_name"]["options"] = self._file_list
                    except Exception as e:
                        logger.error(f"Error getting files: {e!s}")
                        return build_config

            except Exception as e:
                logger.exception(f"Error updating file list: {e!s}")
                raise

        return build_config

    async def get_file_paths(self) -> list[Data]:
        """Get file paths for the FileComponent to process."""
        try:
            await self._ensure_hub_data()

            if not self.selected_hub:
                logger.warning("Knowledge hub selection is required.")
                return []

            # Get the hub ID for the selected hub
            hub_id = next(
                (
                    hub["id"]
                    for hub in self._hub_list
                    if hub["name"] == self.selected_hub
                ),
                None,
            )

            if not hub_id:
                logger.warning("Invalid hub selection.")
                return []

            try:
                service = get_knowledge_service()
                if not service.ready:
                    logger.error("KnowledgeHub service is not ready")
                    return []
                file_paths = []

                # If a specific file is selected
                if self.file_name:
                    signed_url = await service.get_document_signed_url(
                        hub_id, self.file_name
                    )
                    if signed_url:
                        file_paths = [Data(data={self.FILE_PATH_FIELD: signed_url})]
                        logger.debug(f"Generated signed URL for {self.file_name}")

                # If no specific file is selected and return_all_files is True
                elif self.return_all_files:
                    files = await service.get_knowledge_hub_documents(hub_id)
                    for file in files:
                        if file.get("documentType") != "DS_Store":
                            signed_url = await service.get_document_signed_url(
                                hub_id, file["name"]
                            )
                            if signed_url:
                                file_paths.append(
                                    Data(data={self.FILE_PATH_FIELD: signed_url})
                                )

                if file_paths:
                    self.status = file_paths
                    logger.info(f"Generated {len(file_paths)} file paths")
                    for path in file_paths:
                        logger.debug(
                            f"File path: {path.data.get(self.FILE_PATH_FIELD)}"
                        )
                else:
                    logger.warning("No file paths generated")
                    self.status = "No files found"

                return file_paths
            except Exception as e:
                logger.error(f"Error getting file paths: {e!s}")
                return []

        except Exception as e:
            logger.exception(f"Error in get_file_paths: {e!s}")
            return []
