from __future__ import annotations

import traceback
from pathlib import Path
from typing import TYPE_CHECKING, Any

from langflow.custom import Component
from langflow.base.langchain_utilities.model import LCToolComponent
from loguru import logger

from langflow.custom.genesis.services.deps import get_modelhub_service
from langflow.custom.genesis.services.modelhub.model_endpoint import ModelEndpoint

if TYPE_CHECKING:
    from langflow.custom.genesis.services.modelhub.service import ModelHubService


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

        logger.info("🔍 ATModelComponent.predict called")
        logger.info(f"🔍 Input kwargs: {kwargs}")

        try:
            # Log component state
            logger.info(f"🔍 Component model endpoint: {self._model_name}")

            # Get resolved model name
            try:
                resolved_model_name = self.model_name
                logger.info(f"✅ Model name resolved: {resolved_model_name}")
            except Exception as e:
                logger.error(f"❌ Failed to resolve model name: {e}")
                logger.error(f"❌ Model endpoint: {self._model_name}")
                raise

            # Get ModelHub service
            logger.info("🔍 Getting ModelHub service...")
            try:
                service = self._get_modelhub_service()
                logger.info(f"✅ ModelHub service obtained: {type(service).__name__}")
                logger.info(f"✅ Service ready: {service.ready}")
                logger.info(f"✅ Service URI: {service.settings.URI}")
            except Exception as e:
                logger.error(f"❌ Failed to get ModelHub service: {e}")
                logger.error(f"❌ Error type: {type(e).__name__}")
                logger.error(f"❌ Full traceback: {traceback.format_exc()}")
                raise

            # Determine inference type and make API call
            if "file_path" in kwargs:
                # File-based inference
                file_path = kwargs.pop("file_path")
                content_type = kwargs.pop("content_type", "application/octet-stream")

                # Convert to Path object if it's a string
                if isinstance(file_path, str):
                    file_path = Path(file_path)

                # Get the file name safely
                if hasattr(file_path, 'name'):
                    file_name = file_path.name
                else:
                    # Fallback to extracting from path string
                    file_name = str(file_path).split('/')[-1]

                logger.info("🔍 Making file inference call...")
                logger.info(f"🔍 File path: {file_path}")
                logger.info(f"🔍 File name: {file_name}")
                logger.info(f"🔍 Content type: {content_type}")
                logger.info(f"🔍 Model: {resolved_model_name}")

                try:
                    response = await service.file_inference(
                        resolved_model_name,
                        file_path=str(file_path),
                        file_name=file_name,
                        content_type=content_type,
                    )
                    logger.info(f"✅ File inference successful")
                except Exception as e:
                    logger.error(f"❌ File inference failed: {e}")
                    logger.error(f"❌ Error type: {type(e).__name__}")
                    logger.error(f"❌ Full traceback: {traceback.format_exc()}")
                    raise
            else:
                # Text-based inference
                text = kwargs.get("text")
                logger.info("🔍 Making text inference call...")
                logger.info(f"🔍 Text input: {text[:100] + '...' if text and len(text) > 100 else text}")
                logger.info(f"🔍 Model: {resolved_model_name}")

                try:
                    response = await service.text_inference(resolved_model_name, text)
                    logger.info(f"✅ Text inference successful")
                except Exception as e:
                    logger.error(f"❌ Text inference failed: {e}")
                    logger.error(f"❌ Error type: {type(e).__name__}")
                    logger.error(f"❌ Full traceback: {traceback.format_exc()}")
                    raise

            # Process response
            logger.info(f"🔍 Raw response: {response}")

            if response is None:
                logger.warning("⚠️ Response is None")
                return {}

            if not isinstance(response, dict):
                logger.warning(f"⚠️ Response is not a dict: {type(response)}")
                return {}

            result = response.get("result", {})
            logger.info(f"✅ Final result: {result}")
            return result

        except Exception as e:
            # Comprehensive error logging
            logger.error(f"❌ Critical error in ATModelComponent.predict: {e}")
            logger.error(f"❌ Error type: {type(e).__name__}")
            logger.error(f"❌ Error args: {e.args}")
            logger.error(f"❌ Full traceback: {traceback.format_exc()}")

            # Re-raise with more context
            raise RuntimeError(f"Error processing with {resolved_model_name if 'resolved_model_name' in locals() else 'unknown model'}: {e}") from e

    def _get_modelhub_service(self) -> ModelHubService:
        """Get the ModelHub service instance using dependency injection."""
        if self._modelhub_service is None:
            logger.info("🔍 Getting ModelHub service from dependency injection...")
            try:
                self._modelhub_service = get_modelhub_service()
                logger.info(f"✅ Service obtained: {type(self._modelhub_service).__name__}")
                logger.info(f"✅ Service ready state: {self._modelhub_service.ready}")
                logger.info(f"✅ Service settings URI: {self._modelhub_service.settings.URI}")
                logger.info(f"✅ Service settings configured: {self._modelhub_service.settings.is_configured()}")
            except Exception as e:
                logger.error(f"❌ Failed to get ModelHub service from dependency injection: {e}")
                logger.error(f"❌ Error type: {type(e).__name__}")
                logger.error(f"❌ Full traceback: {traceback.format_exc()}")
                raise
        return self._modelhub_service
