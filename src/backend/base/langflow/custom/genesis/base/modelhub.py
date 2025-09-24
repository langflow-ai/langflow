from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.custom.custom_component.component import Component
from langflow.base.langchain_utilities.model import LCToolComponent

from src.backend.base.langflow.custom.genesis.services.deps import get_modelhub_service
from src.backend.base.langflow.custom.genesis.services.modelhub.model_endpoint import ModelEndpoint

if TYPE_CHECKING:
    from src.backend.base.langflow.custom.genesis.services.modelhub.service import ModelHubService


class ATModelComponent(LCToolComponent):
    """Base class for ModelHub components"""

    _model_name: ModelEndpoint

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._modelhub_service = None
        self._modelhub_service: ModelHubService | None = None

    @property
    def model_name(self) -> str:
        """Get the model name from the ModelEndpoint."""
        return self._model_name.get_model()

    async def predict(self, **kwargs) -> Any:
        """Make a prediction using the ModelHub service"""

        if "file_path" in kwargs:
            file_path = kwargs.pop("file_path")
            content_type = kwargs.pop("content_type", "application/octet-stream")

            # Call the binary endpoint with proper headers
            response = self._get_modelhub_service().file_inference(
                self.model_name,
                file_path=str(file_path),
                file_name=file_path.name,
                content_type=content_type,
            )
        else:
            # Get text from kwargs
            text = kwargs.get("text")
            response = self._get_modelhub_service().text_inference(
                self.model_name, text
            )
        response = response.get("result", {})
        return response

    def _get_modelhub_service(self) -> ModelHubService:
        """Get the ModelHub service instance using dependency injection."""
        if self._modelhub_service is None:
            self._modelhub_service = get_modelhub_service()
        return self._modelhub_service
