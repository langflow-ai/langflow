from lfx.base.models.aws_constants import AWS_REGIONS, AWS_MODEL_IDs
from lfx.base.models.model import LCModelComponent
from lfx.field_typing import LanguageModel
from lfx.inputs.inputs import BoolInput, FloatInput, IntInput, MessageTextInput, SecretStrInput
from lfx.io import DictInput, DropdownInput

# Providers whose Bedrock models document "top_k" as an inference parameter, in the
# range this component's default sits in. The Converse API only accepts
# additionalModelRequestFields the target model actually supports, so sending it
# anywhere else makes Bedrock reject the whole call: Meta takes only
# prompt/temperature/top_p/max_gen_len, Amazon Titan and AI21 have no top_k, and Cohere
# spells it "k". Mistral is excluded too, despite listing top_k for text completion:
# Mistral Large uses the chat-completion schema, which has no top_k at all, and the
# text-completion models cap it below this component's default of 250. Anything outside
# this set can still opt in explicitly through Additional Model Fields.
TOP_K_PROVIDERS = frozenset({"anthropic"})

# Inference profile ids are prefixed with the geography, e.g. "us.anthropic...";
# "global" is the worldwide-routing profile. Mirrors MODEL_ID_GEO_PREFIXES in
# langchain_aws.utils: ChatBedrockConverse strips exactly these before resolving the
# provider, so a shorter set here would drop top_k for models the library still
# resolves to Anthropic. Kept as a literal because the constant only exists in newer
# langchain-aws releases than this bundle's floor.
_INFERENCE_PROFILE_PREFIXES = frozenset({"us", "eu", "apac", "global", "us-gov", "sa", "amer", "jp", "au"})


def _model_provider(model_id: str) -> str:
    """Provider segment of a Bedrock model id, ignoring any cross-region prefix."""
    parts = str(model_id or "").split(".")
    if len(parts) > 1 and parts[0] in _INFERENCE_PROFILE_PREFIXES:
        parts = parts[1:]
    return parts[0] if parts else ""


class AmazonBedrockConverseComponent(LCModelComponent):
    display_name: str = "Amazon Bedrock Converse"
    description: str = (
        "Generate text using Amazon Bedrock LLMs with the modern Converse API for improved conversation handling."
    )
    icon = "Amazon"
    name = "AmazonBedrockConverseModel"
    beta = True

    inputs = [
        *LCModelComponent.get_base_inputs(),
        DropdownInput(
            name="model_id",
            display_name="Model ID",
            options=AWS_MODEL_IDs,
            value="anthropic.claude-3-5-sonnet-20241022-v2:0",
            info="List of available model IDs to choose from.",
        ),
        SecretStrInput(
            name="aws_access_key_id",
            display_name="AWS Access Key ID",
            info="The access key for your AWS account. "
            "Usually set in Python code as the environment variable 'AWS_ACCESS_KEY_ID'.",
            value="AWS_ACCESS_KEY_ID",
            required=True,
        ),
        SecretStrInput(
            name="aws_secret_access_key",
            display_name="AWS Secret Access Key",
            info="The secret key for your AWS account. "
            "Usually set in Python code as the environment variable 'AWS_SECRET_ACCESS_KEY'.",
            value="AWS_SECRET_ACCESS_KEY",
            required=True,
        ),
        SecretStrInput(
            name="aws_session_token",
            display_name="AWS Session Token",
            advanced=True,
            info="The session key for your AWS account. "
            "Only needed for temporary credentials. "
            "Usually set in Python code as the environment variable 'AWS_SESSION_TOKEN'.",
            load_from_db=False,
        ),
        SecretStrInput(
            name="credentials_profile_name",
            display_name="Credentials Profile Name",
            advanced=True,
            info="The name of the profile to use from your "
            "~/.aws/credentials file. "
            "If not provided, the default profile will be used.",
            load_from_db=False,
        ),
        DropdownInput(
            name="region_name",
            display_name="Region Name",
            value="us-east-1",
            options=AWS_REGIONS,
            info="The AWS region where your Bedrock resources are located.",
        ),
        MessageTextInput(
            name="endpoint_url",
            display_name="Endpoint URL",
            advanced=True,
            info="The URL of the Bedrock endpoint to use.",
        ),
        # Model-specific parameters for fine control
        FloatInput(
            name="temperature",
            display_name="Temperature",
            value=0.7,
            info="Controls randomness in output. Higher values make output more random.",
            advanced=True,
        ),
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            value=4096,
            info="Maximum number of tokens to generate.",
            advanced=True,
        ),
        FloatInput(
            name="top_p",
            display_name="Top P",
            value=0.9,
            info="Nucleus sampling parameter. Controls diversity of output.",
            advanced=True,
        ),
        IntInput(
            name="top_k",
            display_name="Top K",
            value=250,
            info="Limits the number of highest probability vocabulary tokens to consider. "
            "Only sent to Anthropic models, the ones that document it for the Converse API; it is "
            "ignored for the others. Use 'Additional Model Fields' to pass a provider's own equivalent.",
            advanced=True,
        ),
        BoolInput(
            name="disable_streaming",
            display_name="Disable Streaming",
            value=False,
            info="If True, disables streaming responses. Useful for batch processing.",
            advanced=True,
        ),
        DictInput(
            name="additional_model_fields",
            display_name="Additional Model Fields",
            advanced=True,
            is_list=True,
            info="Additional model-specific parameters for fine-tuning behavior.",
        ),
    ]

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        try:
            from langchain_aws.chat_models.bedrock_converse import ChatBedrockConverse
        except ImportError as e:
            msg = "langchain_aws is not installed. Please install it with `pip install langchain_aws`."
            raise ImportError(msg) from e

        # Prepare initialization parameters
        init_params = {
            "model": self.model_id,
            "region_name": self.region_name,
        }

        # Add AWS credentials if provided
        if self.aws_access_key_id:
            init_params["aws_access_key_id"] = self.aws_access_key_id
        if self.aws_secret_access_key:
            init_params["aws_secret_access_key"] = self.aws_secret_access_key
        if self.aws_session_token:
            init_params["aws_session_token"] = self.aws_session_token
        if self.credentials_profile_name:
            init_params["credentials_profile_name"] = self.credentials_profile_name
        if self.endpoint_url:
            init_params["endpoint_url"] = self.endpoint_url

        # Add model parameters directly as supported by ChatBedrockConverse
        if hasattr(self, "temperature") and self.temperature is not None:
            init_params["temperature"] = self.temperature
        if hasattr(self, "max_tokens") and self.max_tokens is not None:
            init_params["max_tokens"] = self.max_tokens
        if hasattr(self, "top_p") and self.top_p is not None:
            init_params["top_p"] = self.top_p

        # Handle streaming - only disable if explicitly requested
        if hasattr(self, "disable_streaming") and self.disable_streaming:
            init_params["disable_streaming"] = True

        # top_k is not part of the universal Converse API inferenceConfig, so it is
        # passed through additional_model_request_fields like other provider-specific fields.
        additional_model_request_fields = {}
        if hasattr(self, "top_k") and self.top_k is not None and _model_provider(self.model_id) in TOP_K_PROVIDERS:
            additional_model_request_fields["top_k"] = self.top_k

        # additional_model_fields lets users override or extend provider-specific fields,
        # including using a different key for providers that don't accept "top_k".
        if hasattr(self, "additional_model_fields") and self.additional_model_fields:
            for field in self.additional_model_fields:
                if isinstance(field, dict):
                    additional_model_request_fields.update(field)

        # Only add if we have actual additional fields
        if additional_model_request_fields:
            init_params["additional_model_request_fields"] = additional_model_request_fields

        try:
            output = ChatBedrockConverse(**init_params)
        except Exception as e:
            # Provide helpful error message with fallback suggestions
            error_details = str(e)
            if "validation error" in error_details.lower():
                msg = (
                    f"ChatBedrockConverse validation error: {error_details}. "
                    f"This may be due to incompatible parameters for model '{self.model_id}'. "
                    f"Consider adjusting the model parameters or trying the legacy Amazon Bedrock component."
                )
            elif "converse api" in error_details.lower():
                msg = (
                    f"Converse API error: {error_details}. "
                    f"The model '{self.model_id}' may not support the Converse API. "
                    f"Try using the legacy Amazon Bedrock component instead."
                )
            else:
                msg = f"Could not initialize ChatBedrockConverse: {error_details}"
            raise ValueError(msg) from e

        return output
