"""Blob Storage Component for loading files from Azure Blob Storage."""

from __future__ import annotations

from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import BoolInput, DropdownInput, Output, StrInput
from lfx.schema.data import Data
from lfx.services.manager import get_service_manager
from loguru import logger


class BlobStorageComponent(Component):
    display_name = "Blob Storage"
    category: str = "input_output"
    description = "Load files from Azure Blob Storage"
    documentation = "http://docs.langflow.org/components/storage"
    icon = "Autonomize"
    name = "BlobStorage"

    # Match the property name expected by FileComponent
    FILE_PATH_FIELD = "file_path"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._container_list: list[str] = []
        self._file_list: list[str] = []

    inputs = [
        StrInput(
            name="storage_account",
            display_name="Storage Account",
            required=False,
            info="Storage Account name",
            advanced=True,
        ),
        DropdownInput(
            name="container_name",
            display_name="Container",
            info="Select a container from the storage account",
            required=True,
            refresh_button=True,
        ),
        DropdownInput(
            name="file_name",
            display_name="File",
            info="Select a file from the container",
            required=True,
            refresh_button=True,
        ),
        BoolInput(
            name="return_all_files",
            display_name="Return All Files",
            info="If true and no specific file is selected, returns all files in the container",
            value=True,
        ),
    ]

    outputs = [
        Output(
            name="file_path",  # Match the property name expected by FileComponent
            display_name="File Path",
            method="get_file_paths",
        ),
    ]

    async def update_build_config(
        self, build_config: dict, field_value: Any, field_name: str | None = None
    ):
        """Update the build configuration based on field changes."""
        logger.info(f"update_build_config called with field_name: {field_name}")

        storage_account = getattr(self, "storage_account", None)
        container_name = getattr(self, "container_name", None)

        if field_name == "container_name":
            try:
                # Load the container options when the field is refreshed
                service = get_service_manager().get("flexstore_service")
                self._container_list = await service.get_containers(storage_account)

                build_config["container_name"]["options"] = self._container_list
                return build_config

            except Exception as e:
                logger.exception(f"Error updating container list: {e!s}")
                raise

        elif field_name == "file_name" and container_name:
            try:
                # Load the file options when the field is refreshed
                service = get_service_manager().get("flexstore_service")
                self._file_list = await service.get_files(
                    storage_account, container_name
                )

                build_config["file_name"]["options"] = self._file_list
                return build_config

            except Exception as e:
                logger.exception(f"Error updating file list: {e!s}")
                raise

        return build_config

    async def get_file_paths(self) -> list[Data]:
        """Get file paths for the FileComponent to process."""
        try:
            if not self.container_name:
                logger.warning("Container name is required.")
                return []

            service = get_service_manager().get("flexstore_service")
            file_paths = []

            # If a specific file is selected
            if self.file_name:
                signed_url = await service.get_signed_url(
                    self.storage_account, self.container_name, self.file_name
                )
                if signed_url:
                    file_paths = [Data(data={self.FILE_PATH_FIELD: signed_url})]
            # If no specific file is selected and return_all_files is True
            elif self.return_all_files:
                files = await service.get_files(
                    self.storage_account, self.container_name
                )
                for file in files:
                    signed_url = await service.get_signed_url(
                        self.storage_account, self.container_name, file
                    )
                    if signed_url:
                        file_paths.append(Data(data={self.FILE_PATH_FIELD: signed_url}))

            if file_paths:
                self.status = file_paths
                logger.info(f"Generated {len(file_paths)} file paths")
                for path in file_paths:
                    logger.debug(f"File path: {path.data.get(self.FILE_PATH_FIELD)}")
            else:
                logger.warning("No file paths generated")

            return file_paths

        except Exception as e:
            logger.error(f"Error in get_file_paths: {e!s}")
            return []
