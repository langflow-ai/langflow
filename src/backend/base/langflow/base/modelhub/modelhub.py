from __future__ import annotations

import base64
from io import BytesIO
import traceback
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict

import aiohttp
from loguru import logger

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.services.deps import get_modelhub_service

if TYPE_CHECKING:
    from langflow.services.modelhub.model_endpoint import ModelEndpoint
    from langflow.services.modelhub.service import ModelHubService


class ATModelComponent(LCToolComponent):
    """Base class for ModelHub components."""

    _model_name: ModelEndpoint

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._modelhub_service = None
        self._modelhub_service: ModelHubService | None = None

    @property
    def model_name(self) -> str:
        """Get the model name from the ModelEndpoint."""
        return self._model_name.get_model()

    def _get_direct_model_endpoint(self, model_name: str) -> str | None:
        """Get direct model endpoint for file inference to bypass ModelHub service issues."""
        # Mapping of model names to their direct endpoints (matching user's working curl commands)
        direct_endpoints = {
            "tolstoy-model": "https://tolstoy-v2.modelhub.sprint.autonomize.dev/v1/models/extraction:predict",
            "tolstoy-identification": "https://tolstoy-v2.modelhub.sprint.autonomize.dev/v1/models/identification:predict",
            # Add common SRF model names that might be used
            "extraction": "https://tolstoy-v2.modelhub.sprint.autonomize.dev/v1/models/extraction:predict",
            "identification": "https://tolstoy-v2.modelhub.sprint.autonomize.dev/v1/models/identification:predict",
            "srf-extraction": "https://tolstoy-v2.modelhub.sprint.autonomize.dev/v1/models/extraction:predict",
            "srf-identification": "https://tolstoy-v2.modelhub.sprint.autonomize.dev/v1/models/identification:predict",
            "hedis-ccs-object-detection": "https://solution.uat.genesis.autonomize.ai/genesis-platform/modelhub-bff/modelhub/api/v1/client/1/copilot/68db7fb4816140e17622484f/model-card/hedis-ccs-object-detection/infer",
            "hedis-ccs-slm-validation": "https://solution.uat.genesis.autonomize.ai/genesis-platform/modelhub-bff/modelhub/api/v1/client/1/copilot/68db7fb4816140e17622484f/model-card/hedis-ccs-slm-validation/infer",
        }
        return direct_endpoints.get(model_name)

    async def _direct_file_inference(self, endpoint: str, file_path: Path, content_type: str) -> Any:
        """Make direct file inference call to bypass ModelHub service issues."""
        try:
            # Use the modelhub client's credential directly to get the proper token
            from langflow.services.deps import get_modelhub_service
            service = get_modelhub_service()

            # Access the credential and get token directly from the modelhub client
            credential = service.client.credential
            auth_token = credential.get_token()

            # Read file content as raw binary data
            file_content = file_path.read_bytes()

            # Prepare headers for direct endpoint (matching working curl)
            headers = {
                "Content-Type": "application/octet-stream",
                "Authorization": f"Bearer {auth_token}"
            }

            logger.debug(f"Making direct request to: {endpoint}")
            logger.debug(f"Content length: {len(file_content)} bytes")

            # Make request with raw binary data
            async with aiohttp.ClientSession() as session:
                async with session.post(endpoint, data=file_content, headers=headers) as response:
                    response.raise_for_status()
                    result = await response.json()
                    logger.debug(f"Direct endpoint response: {result}")
                    return result

        except Exception as e:
            logger.error(f"Direct file inference failed: {e}")
            raise

    async def _direct_text_inference(
        self, endpoint: str, text: Path, parameters: Dict |None=None
    ) -> Any:
        """Make direct text inference call to bypass ModelHub service issues."""
        try:
            # Use the modelhub client's credential directly to get the proper token
            from langflow.services.deps import get_modelhub_service

            service = get_modelhub_service()

            # Access the credential and get token directly from the modelhub client
            credential = service.client.credential
            auth_token = credential.get_token()

            # Prepare headers for direct endpoint (matching working curl)
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {auth_token}",
            }

            logger.debug(f"Making direct request to: {endpoint}")
            logger.debug(f"text: {text}")

            # Make request with raw binary data
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    endpoint, json={"text":text}, headers=headers
                ) as response:
                    response.raise_for_status()
                    result = await response.json()
                    logger.debug(f"Direct endpoint response: {result}")
                    return result

        except Exception as e:
            logger.error(f"Direct text inference failed: {e}")
            raise

    async def _direct_infer_call_for_object_detection(self, endpoint: str, file_path: Path) -> Any:
        """Make direct file inference call to bypass ModelHub service issues."""
        try:
            # Use the modelhub client's credential directly to get the proper token
            from langflow.services.deps import get_modelhub_service
            service = get_modelhub_service()

            # Access the credential and get token directly from the modelhub client
            credential = service.client.credential
            auth_token = credential.get_token()

            file_content = file_path.read_bytes()
            bytes_io = BytesIO(file_content)
            base64_content = base64.b64encode(bytes_io.read()).decode("utf-8")

            # Prepare headers for direct endpoint (matching working curl)
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {auth_token}"
            }

            logger.debug(f"Making direct request to: {endpoint}")

            # Make request with raw binary data
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    endpoint, json={"data": {"image": base64_content}}, headers=headers
                ) as response:
                    response.raise_for_status()
                    result = await response.json()
                    logger.debug(f"Direct endpoint response for hedis: {result}")
                    return result.get('result',{}).get('data',None)

        except Exception as e:
            logger.error(f"Direct file inference failed for hedis: {e}")
            raise

    async def predict(self, **kwargs) -> Any:
        """Make a prediction using the ModelHub service."""
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
                file_name = file_path.name if hasattr(file_path, "name") else str(file_path).split("/")[-1]

                logger.info("🔍 Making file inference call...")
                logger.info(f"🔍 File path: {file_path}")
                logger.info(f"🔍 File name: {file_name}")
                logger.info(f"🔍 Content type: {content_type}")
                logger.info(f"🔍 Model: {resolved_model_name}")

                try:
                    # Check if we have a direct endpoint for this model (to bypass ModelHub service issues)
                    direct_endpoint = self._get_direct_model_endpoint(resolved_model_name)
                    if direct_endpoint and any(key in resolved_model_name for key in ["object-detection"]):
                        logger.info(f"🔄 Using direct endpoint for hedis models: {direct_endpoint}")
                        response = await self._direct_infer_call_for_object_detection(direct_endpoint,file_path)
                    elif direct_endpoint:
                        logger.info(f"🔄 Using direct endpoint for file inference: {direct_endpoint}")
                        response = await self._direct_file_inference(direct_endpoint, file_path, content_type)
                    else:
                        # Fallback to ModelHub service
                        logger.info("🔄 Using ModelHub service for file inference")
                        response = await service.file_inference(
                            resolved_model_name,
                            file_path=str(file_path),
                            file_name=file_name,
                            content_type=content_type,
                        )
                    logger.info("✅ File inference successful")
                except Exception as e:
                    logger.error(f"❌ File inference failed: {e}")
                    logger.error(f"❌ Error type: {type(e).__name__}")
                    logger.error(f"❌ Full traceback: {traceback.format_exc()}")
                    raise
            else:
                # Text-based inference
                text = kwargs.get("text")
                direct_endpoint = self._get_direct_model_endpoint(resolved_model_name)
                logger.info("🔍 Making text inference call...")
                logger.info(f"🔍 Text input: {text[:100] + '...' if text and len(text) > 100 else text}")
                logger.info(f"🔍 Model: {resolved_model_name}")

                try:
                    if direct_endpoint:
                        response = await self._direct_text_inference(direct_endpoint, text)
                    else: 
                        response = await service.text_inference(resolved_model_name, text)
                        logger.info("✅ Text inference successful")
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

            # Handle different response formats
            result = response.get("result", {}) if "result" in response else response

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
