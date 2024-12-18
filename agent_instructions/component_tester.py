"""Module for testing OpenAI components with various parameters."""

import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from loguru import logger

# Load environment variables from .env file
repo_root = Path(__file__).parent.parent.parent.parent.parent
load_dotenv(repo_root / ".env")


class OpenAITester:
    """A minimal tester for OpenAI components."""

    def __init__(self):
        """Initialize OpenAI tester with API key from environment."""
        self.api_key = os.getenv("OPENAI_API_KEY")
        api_key_error = "OPENAI_API_KEY not found in .env file"
        if not self.api_key:
            raise ValueError(api_key_error)

    def test_with_parameters(self, params=None):
        """Test OpenAI with given parameters.

        Args:
            params (dict, optional): Custom parameters for testing. Defaults to None.
        """
        if params is None:
            params = {}

        # Default parameters
        default_params = {
            "model_name": "gpt-3.5-turbo",  # Using a real OpenAI model
            "temperature": 0.7,
            "max_tokens": 100,
            "openai_api_key": self.api_key,
            "presence_penalty": 0.5,
            "seed": 42,
        }

        # Update defaults with provided params
        test_params = {**default_params, **params}

        logger.info("Testing with parameters:")
        for param_name, param_value in test_params.items():
            if param_name == "openai_api_key":
                logger.info(f"{param_name}: {'*' * 8}")
            else:
                logger.info(f"{param_name}: {param_value}")

        try:
            # Initialize ChatOpenAI
            logger.info("Initializing ChatOpenAI...")
            model = ChatOpenAI(**test_params)

            # Enable JSON mode
            model = model.bind(response_format={"type": "json_object"})

            logger.info("Model Configuration:")
            logger.info(f"Model Name: {model.model_name}")
            logger.info(f"Temperature: {model.temperature}")
            logger.info(f"Max Tokens: {model.max_tokens}")
            logger.info(f"Presence Penalty: {model.presence_penalty}")
            logger.info("JSON Mode: Enabled")
            logger.info(f"Seed: {model.seed}")

            # Test with a prompt
            prompt = "Tell me a short joke about programming in JSON format"
            logger.info(f"Testing with prompt: {prompt}")

            response = model.invoke(prompt)
            logger.info("Model Response:")
            logger.info(response.content)

        except Exception as e:
            logger.error(f"An error occurred: {e!s}")
            raise


def main():
    """Run the OpenAI tester with default parameters."""
    # Create tester
    tester = OpenAITester()

    # Test with default parameters
    tester.test_with_parameters()


if __name__ == "__main__":
    main()
