"""Module for manual testing of OpenAI model components."""

import os
import sys
from pathlib import Path

from langflow.components.models.openai import OpenAIModelComponent
from loguru import logger

# Add the langflow directory to Python path
repo_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.append(str(repo_root))


def test_openai_component():
    """Test the OpenAI model component with custom parameters."""
    # Initialize the component
    component = OpenAIModelComponent()

    # Set the parameters using the set method
    params = {
        "model_name": "gpt-4o-mini",
        "temperature": 0.7,
        "max_tokens": 100,
        "api_key": os.getenv("OPENAI_API_KEY"),  # Make sure this env var is set
        "json_mode": True,
        "model_kwargs": {"presence_penalty": 0.5},
        "seed": 42,
    }

    # Set each parameter
    for param_name, param_value in params.items():
        setattr(component, param_name, param_value)

    # Build and test the model
    try:
        model = component.build_model()
        logger.info("Model Configuration:")
        logger.info(f"Model Name: {model.model}")
        logger.info(f"Temperature: {model.temperature}")
        logger.info(f"Max Tokens: {model.max_tokens}")
        logger.info(f"Model kwargs: {model.model_kwargs}")
        logger.info(f"Base URL: {model.base_url}")
        logger.info("JSON Mode: Enabled")
        logger.info(f"Seed: {model.seed}")

        # Test the model with a simple prompt
        response = model.invoke("Tell me a short joke about programming")
        logger.info("Model Response:")
        logger.info(response.content)

    except Exception as e:
        logger.error(f"Error occurred: {e!s}")
        raise


if __name__ == "__main__":
    logger.info("Testing OpenAI Component...")
    test_openai_component()
