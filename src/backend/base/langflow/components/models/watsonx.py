from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.inputs import DropdownInput, IntInput, SecretStrInput, StrInput, FloatInput, SliderInput
from langflow.field_typing.range_spec import RangeSpec
from langflow.schema.dotdict import dotdict

from pydantic.v1 import SecretStr
from typing import List, Any

from ibm_watsonx_ai.foundation_models import ModelInference
from ibm_watsonx_ai.metanames import GenTextParamsMetaNames
from ibm_watsonx_ai import Credentials
from langchain_ibm import WatsonxLLM

import logging
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WatsonxAIComponent(LCModelComponent):
    display_name = "IBM watsonx.ai"
    description = "Generate text using IBM watsonx.ai foundation models"
    icon = "WatsonxAI"
    name = "IBMwatsonxModel"
    beta = False
    _previous_url = ""

    _default_models = ["ibm/granite-3-2b-instruct",
                       "ibm/granite-3-8b-instruct",
                       "ibm/granite-13b-instruct-v2"]

    inputs = [
        *LCModelComponent._base_inputs,
        DropdownInput(
            name="url",
            display_name="watsonx API Endpoint",
            info="The base URL of the API.",
            value=None,
            options=["https://us-south.ml.cloud.ibm.com",
                     "https://eu-de.ml.cloud.ibm.com",
                     "https://eu-gb.ml.cloud.ibm.com",
                     "https://au-syd.ml.cloud.ibm.com",
                     "https://jp-tok.ml.cloud.ibm.com",
                     "https://ca-tor.ml.cloud.ibm.com"
                     ],
            real_time_refresh=True
        ),
        StrInput(
            name="project_id",
            display_name="watsonx project id",
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="The API Key to use for the model.",
            required=True,
        ),
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            options=[],
            value=None,
            dynamic=True,
            required=True,
        ),
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            advanced=True,
            info="The maximum number of tokens to generate.",
            range_spec=RangeSpec(min=1, max=4096),
        ),
        IntInput(
            name="min_tokens",
            display_name="Min Tokens",
            advanced=True,
            info="The minimum number of tokens to generate.",
            range_spec=RangeSpec(min=0, max=2048),
        ),
        DropdownInput(
            name="decoding_method",
            display_name="Decoding method",
            advanced=True,
            options=["greedy", "sample"],
            value="greedy",
        ),
        FloatInput(
            name="repetition_penalty",
            display_name="Repetition Penalty",
            advanced=True,
            info="Penalty for repetition in generation.",
            range_spec=RangeSpec(min=1.0, max=2.0),
        ),
        IntInput(
            name="random_seed",
            display_name="Random Seed",
            advanced=True,
            info="The random seed for the model.",
        ),
        SliderInput(
            name="top_p",
            display_name="Top P",
            advanced=True,
            info="The cumulative probability cutoff for token selection. Lower values mean sampling from a smaller, more top-weighted nucleus.",
            range_spec=RangeSpec(min=0, max=1),
            field_type="float",
        ),
        SliderInput(
            name="top_k",
            display_name="Top K",
            advanced=True,
            info="Sample from the k most likely next tokens at each step. Lower k focuses on higher probability tokens.",
            range_spec=RangeSpec(min=1, max=100),
            field_type="int",
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            advanced=True,
            info="Controls randomness, higher values increase diversity.",
            range_spec=RangeSpec(min=0, max=2),
            field_type="float",
        ),
        StrInput(
            name="stop_sequence",
            display_name="Stop Sequence",
            advanced=True,
            info="A sequence where the generation should stop.",
            field_type="str",
        ),
    ]

    @staticmethod
    def fetch_models(base_url: str) -> List[str]:
        """Fetch available models from the watsonx.ai API"""
        try:
            endpoint = f"{base_url}/ml/v1/foundation_model_specs"
            params = {
                "version": "2024-09-16",
                "filters": "function_text_generation,!lifecycle_withdrawn:and"
            }

            response = requests.get(endpoint, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                models = [model['model_id']
                          for model in data.get('resources', [])]
                return sorted(models) if models else WatsonxAIComponent._default_models
            else:
                return WatsonxAIComponent._default_models
        except Exception as e:
            print(f"Error fetching models: {e}")
            return WatsonxAIComponent._default_models

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None):
        """Update model options when URL or API key changes."""
        logger.info(
            "Updating build config. Field name: %s, Field value: %s", field_name, field_value)

        if field_name == "url" and field_value:
            try:
                models = self.fetch_models(base_url=build_config.url.value)
                build_config.model_name.options = models
                if build_config.model_name.value:
                    build_config.model_name.value = models[0]
                logger.info(
                    f"Updated model options: {len(models)} models found in {build_config.url.value}")
            except Exception as e:
                logger.error(f"Error updating model options: {e}")

    def build_model(self) -> LanguageModel:
        creds = Credentials(
            api_key=SecretStr(
                self.api_key).get_secret_value(),
            url=self.url,
        )

        generate_params = {
            GenTextParamsMetaNames.MAX_NEW_TOKENS: self.max_tokens or 200,
            GenTextParamsMetaNames.MIN_NEW_TOKENS: self.min_tokens or 0,
            GenTextParamsMetaNames.DECODING_METHOD: self.decoding_method or "greedy",
            GenTextParamsMetaNames.REPETITION_PENALTY: self.repetition_penalty or 1.0,
            GenTextParamsMetaNames.RANDOM_SEED: self.random_seed or 33,
            GenTextParamsMetaNames.STOP_SEQUENCES: [self.stop_sequence] if self.stop_sequence else [],
        }

        if generate_params[GenTextParamsMetaNames.DECODING_METHOD] == "sample":
            generate_params.update(
                {
                    GenTextParamsMetaNames.TEMPERATURE: self.temperature or 0.5,
                    GenTextParamsMetaNames.TOP_K: self.top_k or 1,
                    GenTextParamsMetaNames.TOP_P: self.top_p or 0.2,
                }
            )

        model = ModelInference(
            model_id=self.model_name,
            params=generate_params,
            credentials=creds,
            project_id=self.project_id,
        )

        return WatsonxLLM(watsonx_model=model, streaming=self.stream)
