from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langchain_ibm import WatsonxLLM
from pydantic.v1 import SecretStr


from ibm_watsonx_ai.foundation_models import ModelInference
from ibm_watsonx_ai.metanames import GenTextParamsMetaNames
from ibm_watsonx_ai import Credentials
from langflow.inputs import DropdownInput, IntInput, SecretStrInput, StrInput, FloatInput, SliderInput
from langflow.field_typing.range_spec import RangeSpec



class WatsonxAIComponent(LCModelComponent):
    display_name = "IBM watsonx.ai"
    description = "Generate text using IBM watsonx.ai foundation models"
    icon = "WatsonxAI"
    name = "IBMwatsonxModel"
    beta = False
    inputs = [
        *LCModelComponent._base_inputs,
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            advanced=False,
            options=[
                "codellama/codellama-34b-instruct-hf",
                "google/flan-ul2",
                "ibm/granite-13b-instruct-v2",
                "ibm/granite-20b-code-instruct",
                "ibm/granite-20b-multilingual",
                "ibm/granite-3-2-8b-instruct",
                "ibm/granite-3-2b-instruct",
                "ibm/granite-3-8b-instruct",
                "ibm/granite-34b-code-instruct",
                "ibm/granite-3b-code-instruct",
                "meta-llama/llama-3-2-11b-vision-instruct",
                "meta-llama/llama-3-2-1b-instruct",
                "meta-llama/llama-3-2-3b-instruct",
                "meta-llama/llama-3-2-90b-vision-instruct",
                "meta-llama/llama-3-3-70b-instruct",
                "meta-llama/llama-3-405b-instruct",
            ],
            value="meta-llama/llama-3-3-70b-instruct",
        ),
        StrInput(
            name="url",
            display_name="watsonx API Endpoint",
            advanced=True,
            info="The base URL of the API.",
            value="https://us-south.ml.cloud.ibm.com",
        ),
        StrInput(
            name="project_id",
            display_name="watsonx project id",
            advanced=False,
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="The API Key to use for the model.",
            advanced=False,
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

        return WatsonxLLM(watsonx_model=model)