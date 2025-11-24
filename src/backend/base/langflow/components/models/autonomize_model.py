"""Autonomize Model Component - Unified text-based model component with dropdown selection."""

import ast
import json
from typing import Any

from langflow.services.modelhub.model_endpoint import ModelEndpoint
from loguru import logger

from langflow.base.modelhub import ATModelComponent
from langflow.inputs.inputs import FieldTypes
from langflow.io import DropdownInput, MultilineInput, Output
from langflow.schema.data import Data


class AutonomizeModelComponent(ATModelComponent):
    """Unified component for Autonomize text-based models with dropdown selection."""

    display_name: str = "Autonomize Model"
    description: str = (
        "Unified interface for Autonomize text-based AI models with dropdown selection"
    )
    documentation: str = "https://docs.example.com/autonomize-models"
    icon: str = "Autonomize"
    name: str = "AutonomizeModel"
    category: str = "models"
    priority: int = 1  # High priority to appear near top

    # Model mapping for dropdown options
    MODEL_OPTIONS = {
        "Clinical LLM": ModelEndpoint.CLINICAL_LLM,
        "Clinical Note Classifier": ModelEndpoint.CLINICAL_NOTE_CLASSIFIER,
        "Combined Entity Linking": ModelEndpoint.COMBINED_ENTITY_LINKING,
        "CPT Code": ModelEndpoint.CPT_CODE,
        "ICD-10 Code": ModelEndpoint.ICD_10,
        "RxNorm Code": ModelEndpoint.RXNORM,
        "Hedis Object Detection CCS": ModelEndpoint.HEDIS_OBJECT_DETECTION_CCS,
        "Hedis SLM Validation CCS": ModelEndpoint.HEDIS_SLM_VALIDATION_CCS,
    }

    # Model descriptions for UI
    MODEL_DESCRIPTIONS = {
        "Clinical LLM": "Extract clinical entities from medical text",
        "Clinical Note Classifier": "Classify clinical notes by type",
        "Combined Entity Linking": "Link extracted entities to standard vocabularies",
        "CPT Code": "Extract CPT codes from medical text",
        "ICD-10 Code": "Extract ICD-10 codes from medical text",
        "RxNorm Code": "Extract RxNorm codes for medications",
        "Hedis Object Detection CCS": "hedis object extraction",
        "Hedis SLM Validation CCS": "hedis validation",
    }

    inputs = [
        DropdownInput(
            name="selected_model",
            display_name="Model",
            options=list(MODEL_OPTIONS.keys()),
            value=next(iter(MODEL_OPTIONS.keys())),
            info="Select the Autonomize document model to use",
            real_time_refresh=True,
            tool_mode=True,
        ),
        MultilineInput(
            name="search_query",
            display_name="Text Input",
            field_type=FieldTypes.TEXT,
            multiline=True,
            tool_mode=True,
            info="Input text to process with the selected model",
        ),
    ]

    outputs = [
        Output(name="prediction", display_name="Model Output", method="build_output"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._current_model_endpoint = None
        # Initialize _model_name with the default model endpoint (required by ATModelComponent)
        self._model_name = self.MODEL_OPTIONS[next(iter(self.MODEL_OPTIONS.keys()))]

    @property
    def model_endpoint(self) -> ModelEndpoint:
        """Get the current model endpoint based on selection."""
        return self.MODEL_OPTIONS[self.selected_model]

    @property
    def model_name_from_endpoint(self) -> str:
        """Get the model name from the ModelEndpoint."""
        return self.model_endpoint.get_model()

    async def extract_entities(self, text: Any) -> dict:
        """Extract entities using the selected model."""
        # Handle different input formats
        if isinstance(text, str) and text.strip().startswith("{"):
            try:
                text_dict = json.loads(text)
                text = text_dict
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON string: {e}")
                # If JSON parsing fails, use the original text

        # Handle the case where input is a dictionary with result structure
        if isinstance(text, dict) and "result" in text:
            result = text["result"]
            if isinstance(result, list) and len(result) > 0:
                # Extract text from the first result item
                first_result = result[0]
                if isinstance(first_result, dict) and "text" in first_result:
                    extracted_text = first_result["text"]
                    text = extracted_text
                else:
                    msg = "First result item does not contain 'text' key"
                    raise ValueError(msg)
            else:
                msg = "Result list is empty or not a list"
                raise ValueError(msg)
        elif isinstance(text, dict) and "text" in text:
            text = text["text"]
        elif hasattr(text, "text"):
            text = text.text

        try:
            # Use the standard predict method from ATModelComponent
            # Set the _model_name based on current selection
            self._model_name = self.model_endpoint

            response = await self.predict(text=text)

            # Handle string responses
            if isinstance(response, str):
                try:
                    response = ast.literal_eval(response)
                except (ValueError, SyntaxError):
                    # If it's not a valid Python literal, try JSON
                    try:
                        response = json.loads(response)
                    except json.JSONDecodeError:
                        # If neither works, wrap in a dict
                        response = {"result": response}
            else:
                return response
        except Exception as e:
            msg = f"Error processing with {self.model_name}: {e!s}"
            logger.error(f"API call failed: {msg}")
            raise ValueError(msg) from e

    async def build_output(self) -> Data:
        """Generate the output based on selected model."""
        query_results = await self.extract_entities(self.search_query)

        # Create standardized output format
        output_data = {
            "model": self.selected_model,
            "model_description": self.MODEL_DESCRIPTIONS.get(self.selected_model, ""),
            "data": query_results,
        }

        data = Data(value=output_data)
        self.status = f"Processed with {self.selected_model}"
        return data

    def build(self):
        """Return the main build function for Langflow framework."""
        return self.build_output
