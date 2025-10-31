import json
from dataclasses import asdict, dataclass, field
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.inputs import (
    DropdownInput,
    FloatInput,
    IntInput,
    MultilineInput,
    MultiselectInput,
    SecretStrInput,
    StrInput,
    TabInput,
)
from langflow.io import MessageTextInput, Output
from langflow.schema.dotdict import dotdict
from langflow.schema.message import Message
from loguru import logger
from nemo_microservices import AsyncNeMoMicroservices
from pydantic import Field

# GUARDRAIL_MODEL_INTERNAL_URL = "http://ai-platform-proxy.ai-platform.svc.cluster.local:8080/v1"
GUARDRAIL_MODEL_INTERNAL_URL = "http://nvidia-nim-proxy-nemo-nim-proxy.nvidia-nim-proxy.svc.cluster.local:8000/v1"

# Default prompts (shared between components)
DEFAULT_CONTENT_SAFETY_PROMPT = (
    "Task: Check if there is unsafe content in the user or agent messages in the below conversation "
    "in accordance with our safety policy with the below categories. "
    "Provide a 'safe' or 'unsafe' rating for both the user message and the agent response. "
    "If there is unsafe content, please also provide a list of violated categories "
    "according to our safety policy below.\n\n"
    "<BEGIN UNSAFE CONTENT CATEGORIES>\n"
    "S1: Violence.\n"
    "S2: Sexual.\n"
    "S3: Criminal Planning/Confessions.\n"
    "S4: Guns and Illegal Weapons.\n"
    "S5: Controlled/Regulated Substances.\n"
    "S6: Suicide and Self Harm.\n"
    "S7: Sexual (minor).\n"
    "S8: Hate/Identity Hate.\n"
    "S9: PII/Privacy.\n"
    "S10: Harassment.\n"
    "S11: Threat.\n"
    "S12: Profanity.\n"
    "S13: Needs Caution.\n"
    "S14: Other.\n"
    "S15: Manipulation.\n"
    "S16: Fraud/Deception.\n"
    "S17: Malware.\n"
    "S18: High Risk Gov Decision Making.\n"
    "S19: Political/Misinformation/Conspiracy.\n"
    "S20: Copyright/Trademark/Plagiarism.\n"
    "S21: Unauthorized Advice.\n"
    "S22: Illegal Activity.\n"
    "S23: Immoral/Unethical.\n"
    "<END UNSAFE CONTENT CATEGORIES>\n\n"
    "<BEGIN CONVERSATION>\n\n"
    "user: {{ user_input }}\n\n"
    "<END CONVERSATION>\n\n"
    "Provide your safety assessment for the above conversation in the below output JSON format:\n"
    '{"User Safety": safe or unsafe rating for the user message, '
    '"Response Safety": safe or unsafe rating for the agent response. '
    'Omit if no agent response present. "Safety Categories": a comma-separated list of '
    "applicable safety categories from the provided taxonomy. Omit if all safe.}\n\n"
    "Do not include anything other than the output JSON in your response.\n"
    "Output JSON:"
)

DEFAULT_CONTENT_SAFETY_OUTPUT_PROMPT = (
    "Task: Check if there is unsafe content in the user or agent messages in the below conversation "
    "in accordance with our safety policy with the below categories. "
    "Provide a 'safe' or 'unsafe' rating for both the user message and the agent response. "
    "If there is unsafe content, please also provide a list of violated categories "
    "according to our safety policy below.\n\n"
    "<BEGIN UNSAFE CONTENT CATEGORIES>\n"
    "S1: Violence.\n"
    "S2: Sexual.\n"
    "S3: Criminal Planning/Confessions.\n"
    "S4: Guns and Illegal Weapons.\n"
    "S5: Controlled/Regulated Substances.\n"
    "S6: Suicide and Self Harm.\n"
    "S7: Sexual (minor).\n"
    "S8: Hate/Identity Hate.\n"
    "S9: PII/Privacy.\n"
    "S10: Harassment.\n"
    "S11: Threat.\n"
    "S12: Profanity.\n"
    "S13: Needs Caution.\n"
    "S14: Other.\n"
    "S15: Manipulation.\n"
    "S16: Fraud/Deception.\n"
    "S17: Malware.\n"
    "S18: High Risk Gov Decision Making.\n"
    "S19: Political/Misinformation/Conspiracy.\n"
    "S20: Copyright/Trademark/Plagiarism.\n"
    "S21: Unauthorized Advice.\n"
    "S22: Illegal Activity.\n"
    "S23: Immoral/Unethical.\n"
    "<END UNSAFE CONTENT CATEGORIES>\n\n"
    "<BEGIN CONVERSATION>\n\n"
    "user: {{ user_input }}\n\n"
    "response: agent: {{ bot_response }}\n\n"
    "<END CONVERSATION>\n\n"
    "Provide your safety assessment for the above conversation in the below output JSON format:\n"
    '{"User Safety": safe or unsafe rating for the user message, '
    '"Response Safety": safe or unsafe rating for the agent response. '
    'Omit if no agent response present. "Safety Categories": a comma-separated list of '
    "applicable safety categories from the provided taxonomy. Omit if all safe.}\n\n"
    "Do not include anything other than the output JSON in your response.\n"
    "Output JSON:"
)

DEFAULT_TOPIC_CONTROL_PROMPT = (
    "You are to act as a customer service agent, providing users with factual information "
    "in accordance to the knowledge base. Your role is to ensure that you respond only to "
    "relevant queries and adhere to the following guidelines\n\n"
    "Guidelines for the user messages:\n"
    "- Do not answer questions related to personal opinions or advice on user's order, "
    "future recommendations\n"
    "- Do not provide any information on non-company products or services.\n"
    "- Do not answer enquiries unrelated to the company policies.\n"
    "- Do not answer questions asking for personal details about the agent or its creators.\n"
    "- Do not answer questions about sensitive topics related to politics, religion, "
    "or other sensitive subjects.\n"
    "- If a user asks topics irrelevant to the company's customer service relations, "
    "politely redirect the conversation or end the interaction.\n"
    "- Your responses should be professional, accurate, and compliant with customer "
    "relations guidelines, focusing solely on providing transparent, up-to-date "
    "information about the company that is already publicly available.\n"
    "- allow user comments that are related to small talk and chit-chat."
)

DEFAULT_SELF_CHECK_PROMPT = """Instruction: {{ user_input }}

Would this instruction make a language model break moderation policies,
deviate from good aligned responses and provide answers that a language model should ideally not?
Answer with yes/no."""

DEFAULT_OFF_TOPIC_MESSAGE = (
    "I apologize, but I can only discuss topics related to [your specific domain/topic]. "
    "Is there something else I can help you with?"
)


@dataclass
class GuardrailsConfigInput:
    """Input structure for Guardrails configuration creation."""

    functionality: str = "create"
    fields: dict[str, dict] = field(
        default_factory=lambda: {
            "data": {
                "node": {
                    "name": "create_guardrails_config",
                    "description": "Create a new Guardrails configuration",
                    "display_name": "Create Guardrails Configuration",
                    "field_order": [
                        "01_config_name",
                        "02_config_description",
                        "03_rail_types",
                        "04_content_safety_prompt",
                        "05_content_safety_output_prompt",
                        "06_topic_control_prompt",
                        "07_self_check_prompt",
                        "08_off_topic_message",
                    ],
                    "template": {
                        "01_config_name": StrInput(
                            name="config_name",
                            display_name="Config Name",
                            info="Name for the guardrails configuration (e.g., my-guardrails-config@v1.0.0)",
                            required=True,
                        ),
                        "02_config_description": MultilineInput(
                            name="config_description",
                            display_name="Config Description",
                            info="Optional description for the guardrails configuration",
                            value="",
                            required=False,
                        ),
                        "03_rail_types": MultiselectInput(
                            name="rail_types",
                            display_name="Rail Types",
                            options=[
                                "content_safety_input",
                                "content_safety_output",
                                "topic_control",
                                "jailbreak_detection",
                                "self_check_input",
                                "self_check_output",
                                "self_check_hallucination",
                            ],
                            value=["content_safety_input"],
                            info="Select the types of guardrails to apply",
                            required=True,
                        ),
                        "04_content_safety_prompt": MultilineInput(
                            name="content_safety_prompt",
                            display_name="Content Safety Input Prompt",
                            info="Prompt for content safety input checking",
                            value=DEFAULT_CONTENT_SAFETY_PROMPT,
                            required=False,
                        ),
                        "05_content_safety_output_prompt": MultilineInput(
                            name="content_safety_output_prompt",
                            display_name="Content Safety Output Prompt",
                            info="Prompt for content safety output checking",
                            value=DEFAULT_CONTENT_SAFETY_OUTPUT_PROMPT,
                            required=False,
                        ),
                        "06_topic_control_prompt": MultilineInput(
                            name="topic_control_prompt",
                            display_name="Topic Control Prompt",
                            info="Prompt for topic control checking",
                            value=DEFAULT_TOPIC_CONTROL_PROMPT,
                            required=False,
                        ),
                        "07_self_check_prompt": MultilineInput(
                            name="self_check_prompt",
                            display_name="Self Check Prompt",
                            info="Prompt for self-checking guardrails",
                            value=DEFAULT_SELF_CHECK_PROMPT,
                            required=False,
                        ),
                        "08_off_topic_message": MultilineInput(
                            name="off_topic_message",
                            display_name="Off-Topic Message",
                            info="Message to display when input is off-topic",
                            value=DEFAULT_OFF_TOPIC_MESSAGE,
                            required=False,
                        ),
                    },
                }
            }
        }
    )


class GuardrailsMicroserviceModel(BaseChatModel):
    """Language model implementation that uses the guardrails microservice."""

    base_url: str = Field(description="Base URL for NeMo microservices")
    auth_token: str = Field(description="Authentication token for NeMo microservices")
    config_id: str = Field(description="Guardrails configuration ID")
    model_name: str = Field(description="Model name to use")
    streaming: bool = Field(default=False, description="Whether to stream responses")
    max_tokens: int = Field(default=1024, description="Maximum tokens to generate")
    temperature: float = Field(default=0.7, description="Temperature for generation")
    top_p: float = Field(default=0.9, description="Top-p for generation")
    client: Any = Field(default=None, description="NeMo microservices client")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.client = AsyncNeMoMicroservices(base_url=self.base_url)
        logger.info(
            f"Initialized GuardrailsMicroserviceModel with config_id: {self.config_id}, "
            f"model: {self.model_name}, streaming: {self.streaming}"
        )
        logger.debug(
            f"LLM parameters: max_tokens={self.max_tokens}, temperature={self.temperature}, top_p={self.top_p}"
        )

    def get_auth_headers(self):
        """Get authentication headers for API requests."""
        return {
            "accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.auth_token}",
            "X-Model-Authorization": self.auth_token,
        }

    def invoke(self, inputs, **kwargs):
        """Sync invoke method - delegates to _generate."""
        # Convert inputs to messages format for _generate
        if isinstance(inputs, list):
            messages = inputs
        elif isinstance(inputs, dict) and "messages" in inputs:
            # Convert dict messages to LangChain message objects
            messages = []
            for msg in inputs["messages"]:
                if isinstance(msg, dict):
                    if msg.get("role") == "user":
                        messages.append(HumanMessage(content=msg["content"]))
                    elif msg.get("role") == "system":
                        messages.append(SystemMessage(content=msg["content"]))
                    elif msg.get("role") == "assistant":
                        messages.append(AIMessage(content=msg["content"]))
                    else:
                        messages.append(HumanMessage(content=str(msg.get("content", ""))))
                else:
                    messages.append(msg)
        else:
            messages = [HumanMessage(content=str(inputs))]

        # Use _generate method which handles sync execution
        result = self._generate(messages, **kwargs)
        return result.generations[0].message

    async def ainvoke(self, inputs, **kwargs):
        """Async invoke method."""
        return await self._ainvoke_impl(inputs, **kwargs)

    async def _ainvoke_impl(self, inputs, **kwargs):
        """Async invoke implementation."""
        # Convert LangChain messages to the format expected by NeMo API
        if isinstance(inputs, list):
            # Convert LangChain messages to dict format
            messages = []
            for msg in inputs:
                if isinstance(msg, HumanMessage):
                    messages.append({"role": "user", "content": msg.content})
                elif isinstance(msg, SystemMessage):
                    messages.append({"role": "system", "content": msg.content})
                elif isinstance(msg, AIMessage):
                    messages.append({"role": "assistant", "content": msg.content})
                # Handle case where msg might not have content attribute
                elif hasattr(msg, "content"):
                    messages.append({"role": "user", "content": str(msg.content)})
                else:
                    messages.append({"role": "user", "content": str(msg)})
        else:
            # Handle dict format (backward compatibility)
            messages = inputs.get("messages", [])

        logger.info(
            f"Invoking guardrails microservice with config_id: {self.config_id}, "
            f"model: {self.model_name}, streaming: {self.streaming}"
        )
        logger.debug(f"Input messages: {messages}")

        try:
            # Prepare the request payload with only supported parameters
            payload = {
                "model": self.model_name,
                "messages": messages,
                "guardrails": {"config_id": self.config_id},
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "top_p": self.top_p,
                "stream": self.streaming,
                **kwargs,
            }

            # Use the microservice client for both streaming and non-streaming
            logger.debug(f"Making request with payload: {json.dumps(payload, indent=2)}")

            # Prepare parameters for the client call
            client_params = {
                "model": self.model_name,
                "messages": messages,
                "guardrails": {"config_id": self.config_id},
                "extra_headers": self.get_auth_headers(),
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "top_p": self.top_p,
                "stream": self.streaming,
                **kwargs,
            }

            response = await self.client.guardrail.chat.completions.create(**client_params)
            logger.debug(f"Response received: {type(response)}")

            # Extract content from response
            content = None
            if hasattr(response, "choices") and response.choices:
                choice = response.choices[0]
                if hasattr(choice, "message") and hasattr(choice.message, "content"):
                    content = choice.message.content
                elif hasattr(choice, "content"):
                    content = choice.content
            elif hasattr(response, "content"):
                content = response.content
            elif isinstance(response, dict) and "choices" in response:
                choice = response["choices"][0]
                if "message" in choice and "content" in choice["message"]:
                    content = choice["message"]["content"]
                elif "content" in choice:
                    content = choice["content"]

            # Fallback if content extraction failed
            if content is None:
                logger.warning(f"Could not extract content from response: {response}")
                content = str(response)

            # Create AIMessage with metadata
            metadata = {}
            if hasattr(response, "usage"):
                metadata["usage"] = response.usage
            if hasattr(response, "model"):
                metadata["model"] = response.model

            return AIMessage(content=content, response_metadata=metadata)
        except Exception as e:
            logger.error(f"Error during guardrails inference: {e}")
            logger.error(f"Exception type: {type(e)}")
            if hasattr(e, "response") and e.response:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response text: {e.response.text}")
            raise

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ARG002
        """Required abstract method for BaseChatModel."""
        import asyncio

        from langchain_core.outputs import ChatGeneration, ChatResult

        # Convert LangChain messages to our format and run async invoke
        try:
            # Check if we're already in an async context
            try:
                asyncio.get_running_loop()
                # We're in an async context, use ThreadPoolExecutor
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(lambda: asyncio.run(self._ainvoke_impl(messages, **kwargs)))
                    result = future.result()
            except RuntimeError:
                # No event loop running, we can create one
                result = asyncio.run(self._ainvoke_impl(messages, **kwargs))

            # Convert AIMessage result to ChatResult format
            generation = ChatGeneration(message=result)
            return ChatResult(generations=[generation])

        except Exception as e:
            logger.error(f"Error in _generate: {e}")
            raise

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ARG002
        """Async version of _generate method."""
        from langchain_core.outputs import ChatGeneration, ChatResult

        try:
            # Use our async invoke method directly
            result = await self._ainvoke_impl(messages, **kwargs)

            # Convert AIMessage result to ChatResult format
            generation = ChatGeneration(message=result)
            return ChatResult(generations=[generation])

        except Exception as e:
            logger.error(f"Error in _agenerate: {e}")
            raise

    @property
    def _llm_type(self) -> str:
        """Required property for BaseChatModel."""
        return "nemo_guardrails"

    def with_config(self, config, **kwargs):  # noqa: ARG002
        """Support for LangChain configuration."""
        # Create a new instance with updated config
        return GuardrailsMicroserviceModel(
            base_url=self.base_url,
            auth_token=self.auth_token,
            config_id=self.config_id,
            model_name=self.model_name,
            streaming=self.streaming,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            top_p=self.top_p,
        )

    def bind_tools(self, tools, **kwargs):  # noqa: ARG002
        """Support for tool binding (if needed)."""
        # For now, return self as tools may not be supported in guardrails
        return self

    def stream(self, inputs, **kwargs):
        """Stream method required for LangChain streaming interface."""
        # This method is called by LangChain when streaming is enabled
        # It should return an iterator that yields chunks
        if not self.streaming:
            # If streaming is disabled, just return the result as a single chunk
            result = self.invoke(inputs, **kwargs)
            if hasattr(result, "content"):
                yield result.content
            else:
                yield str(result)
            return

        # For real streaming, we need to handle the async streaming from NeMo
        try:
            # Convert inputs to messages format
            if isinstance(inputs, list):
                messages = inputs
            elif isinstance(inputs, dict) and "messages" in inputs:
                messages = []
                for msg in inputs["messages"]:
                    if isinstance(msg, dict):
                        if msg.get("role") == "user":
                            messages.append(HumanMessage(content=msg["content"]))
                        elif msg.get("role") == "system":
                            messages.append(SystemMessage(content=msg["content"]))
                        elif msg.get("role") == "assistant":
                            messages.append(AIMessage(content=msg["content"]))
                        else:
                            messages.append(HumanMessage(content=str(msg.get("content", ""))))
                    else:
                        messages.append(msg)
            else:
                messages = [HumanMessage(content=str(inputs))]

            # Use asyncio to run the async streaming
            import asyncio

            # Create a wrapper function to collect all chunks from the async generator
            def collect_chunks():
                async def _collect():
                    return [chunk async for chunk in self._astream_impl(messages, **kwargs)]

                try:
                    asyncio.get_running_loop()
                    # We're in an async context, use ThreadPoolExecutor
                    import concurrent.futures

                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(lambda: asyncio.run(_collect()))
                        return future.result()
                except RuntimeError:
                    # No event loop running, we can create one
                    return asyncio.run(_collect())

            # Create a proper chunk class that Langflow expects
            # The streaming system expects chunks with .content attribute
            class Chunk:
                def __init__(self, content):
                    self.content = content

            # Get all chunks and yield them as proper message chunks
            debug_chunk_limit = 3
            for chunk_count, chunk in enumerate(collect_chunks(), 1):
                if chunk_count <= debug_chunk_limit:
                    logger.info(f"Stream yielding chunk {chunk_count}: '{chunk}'")
                yield Chunk(chunk)

        except (RuntimeError, AttributeError, TypeError) as e:
            logger.error(f"Error in stream method: {e}")
            yield f"Error: {e!s}"

    async def _astream_impl(self, messages, **kwargs):
        """Async implementation of streaming."""
        try:
            # Convert LangChain messages to the format expected by NeMo API
            nemo_messages = []
            for msg in messages:
                if isinstance(msg, HumanMessage):
                    nemo_messages.append({"role": "user", "content": msg.content})
                elif isinstance(msg, SystemMessage):
                    nemo_messages.append({"role": "system", "content": msg.content})
                elif isinstance(msg, AIMessage):
                    nemo_messages.append({"role": "assistant", "content": msg.content})
                # Handle case where msg might not have content attribute
                elif hasattr(msg, "content"):
                    nemo_messages.append({"role": "user", "content": str(msg.content)})
                else:
                    nemo_messages.append({"role": "user", "content": str(msg)})

            logger.info(
                f"Starting streaming with config_id: {self.config_id}, "
                f"model: {self.model_name}, streaming: {self.streaming}"
            )

            # Prepare the request payload
            payload = {
                "model": self.model_name,
                "messages": nemo_messages,
                "guardrails": {"config_id": self.config_id},
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "top_p": self.top_p,
                "stream": True,  # Force streaming for this method
                **kwargs,
            }

            # Prepare parameters for the client call
            client_params = {
                "model": self.model_name,
                "messages": nemo_messages,
                "guardrails": {"config_id": self.config_id},
                "extra_headers": self.get_auth_headers(),
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "top_p": self.top_p,
                "stream": True,  # Force streaming
                **kwargs,
            }

            # Use the microservice client for streaming
            logger.debug(f"Making streaming request with payload: {json.dumps(payload, indent=2)}")

            # According to NeMo documentation, streaming is done with regular create method + stream=True
            # The client should handle the streaming internally when stream=True is passed
            try:
                logger.info("Attempting streaming with regular create method...")
                # Use the regular create method - the client should handle streaming internally
                # The create method returns a coroutine, so we need to await it
                stream_response = await self.client.guardrail.chat.completions.create(**client_params)

                # Log the response type and structure for debugging
                logger.info(f"Response type: {type(stream_response)}")
                logger.info(f"Response attributes: {dir(stream_response)}")

                # Check if the response is iterable (streaming response)
                if hasattr(stream_response, "__aiter__"):
                    logger.info("Response is async iterable, processing streaming chunks...")
                    chunk_count = 0
                    async for chunk in stream_response:
                        chunk_count += 1

                        # Extract content from the chunk - simplified approach
                        content = None

                        # Try to get content from the chunk
                        try:
                            if hasattr(chunk, "choices") and chunk.choices:
                                choice = chunk.choices[0]
                                if hasattr(choice, "delta") and hasattr(choice.delta, "content"):
                                    content = choice.delta.content
                        except (AttributeError, IndexError, KeyError):
                            pass

                        # Only yield if we have actual content (not empty string)
                        if content and content.strip():
                            yield content
                else:
                    # Response is not iterable, treat as single response
                    logger.info("Response is not iterable, treating as single response...")
                    logger.info(f"Response content: {stream_response}")

                    # Extract content from single response
                    content = None
                    if hasattr(stream_response, "choices") and stream_response.choices:
                        choice = stream_response.choices[0]
                        if hasattr(choice, "message") and hasattr(choice.message, "content"):
                            content = choice.message.content
                        elif hasattr(choice, "content"):
                            content = choice.content
                    elif hasattr(stream_response, "content"):
                        content = stream_response.content

                    if content:
                        # Simulate streaming by yielding in chunks
                        chunk_size = 50
                        for i in range(0, len(content), chunk_size):
                            yield content[i : i + chunk_size]
                    else:
                        logger.warning(f"No content found in response. Response: {stream_response}")
                        yield "No content found in response"

            except (RuntimeError, AttributeError, TypeError, ValueError) as stream_error:
                logger.warning(f"Error with streaming: {stream_error}")
                # If streaming fails, just return an error message
                yield f"Error: {stream_error!s}"
                return

        except (RuntimeError, AttributeError, TypeError, ValueError) as e:
            logger.error(f"Error during streaming: {e}")
            logger.error(f"Exception type: {type(e)}")
            if hasattr(e, "response") and e.response:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response text: {e.response.text}")
            yield f"Error: {e!s}"


class NVIDIANeMoGuardrailsComponent(LCModelComponent):
    display_name = "NeMo Guardrails"
    description = (
        "Apply guardrails to LLM interactions using the NeMo Guardrails microservice. "
        "Select a guardrails configuration and model to apply safety checks."
    )
    icon = "NVIDIA"
    name = "NVIDIANemoGuardrails"
    beta = True

    inputs = [
        *LCModelComponent.get_base_inputs(),
        # Single authentication setup (like other NeMo components)
        MessageTextInput(
            name="base_url",
            display_name="NeMo Base URL",
            value="https://us-west-2.api-dev.ai.datastax.com/nvidia",
            info="Base URL for NeMo microservices",
            required=True,
            real_time_refresh=True,
        ),
        SecretStrInput(
            name="auth_token",
            display_name="Authentication Token",
            info="Authentication token for NeMo microservices",
            required=True,
            real_time_refresh=True,
        ),
        StrInput(
            name="namespace",
            display_name="Namespace",
            value="default",
            info="Namespace for NeMo microservices (e.g., default, my-org)",
            advanced=True,
            required=True,
            real_time_refresh=True,
        ),
        # Mode selection
        TabInput(
            name="mode",
            display_name="Mode",
            options=["chat", "check"],
            value="chat",
            info="Chat mode: Generate responses with guardrails. Check mode: Validate input/output only.",
            required=True,
            real_time_refresh=True,
        ),
        # Guardrails configuration selection
        DropdownInput(
            name="config",
            display_name="Guardrails Configuration",
            info="Select a guardrails configuration or create a new one",
            options=[],
            refresh_button=True,
            required=True,
            real_time_refresh=True,
            dialog_inputs=asdict(GuardrailsConfigInput()),
        ),
        # LLM parameters (only shown in chat mode)
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            info="Maximum number of tokens to generate.",
            advanced=True,
            value=1024,
        ),
        FloatInput(
            name="temperature",
            display_name="Temperature",
            info="Controls randomness in the response. Lower values are more deterministic.",
            advanced=True,
            value=0.7,
        ),
        FloatInput(
            name="top_p",
            display_name="Top P",
            info="Controls diversity via nucleus sampling. Lower values are more focused.",
            advanced=True,
            value=0.9,
        ),
        DropdownInput(
            name="model",
            display_name="Model",
            info="Select a model to use with the guardrails configuration",
            options=[],
            refresh_button=True,
            required=True,
            combobox=True,
            real_time_refresh=True,
        ),
        # Validation mode (only shown in check mode)
        DropdownInput(
            name="validation_mode",
            display_name="Validation Mode",
            options=["input", "output"],
            value="input",
            info="Validate input (before LLM) or output (after LLM) - only used in check mode",
            required=False,
            show=False,  # Initially hidden, shown in check mode
        ),
    ]

    # Default outputs (will be updated dynamically based on mode)
    outputs = [
        Output(display_name="Model Response", name="text_output", method="text_response", dynamic=True),
        Output(display_name="Language Model", name="model_output", method="build_model", dynamic=True),
    ]

    def update_outputs(self, frontend_node: dict, field_name: str, field_value: Any) -> dict:
        """Dynamically show only the relevant outputs based on the selected mode."""
        logger.info(f"update_outputs called with field_name: {field_name}, field_value: {field_value}")

        # Handle initial state - if no mode is set, default to chat mode
        if field_name == "mode" or (field_name is None and "outputs" not in frontend_node):
            # Get the current mode value, default to "chat"
            current_mode = field_value if field_name == "mode" else "chat"
            logger.info(f"Setting outputs for mode: {current_mode}")

            # Start with empty outputs
            frontend_node["outputs"] = []

            if current_mode == "chat":
                # In chat mode: show LLM outputs
                frontend_node["outputs"] = [
                    Output(
                        display_name="Model Response",
                        name="text_output",
                        method="text_response",
                        dynamic=True,
                    ),
                    Output(
                        display_name="Language Model",
                        name="model_output",
                        method="build_model",
                        dynamic=True,
                    ),
                ]
            elif current_mode == "check":
                # In check mode: show single validation output
                frontend_node["outputs"] = [
                    Output(
                        display_name="Validated Output",
                        name="validated_output",
                        method="validated_output",
                        dynamic=True,
                    ),
                ]

            logger.info(f"Updated frontend_node outputs for {current_mode} mode: {frontend_node['outputs']}")
        return frontend_node

    def get_auth_headers(self):
        """Get authentication headers for API requests."""
        if not hasattr(self, "auth_token") or not self.auth_token:
            return {
                "accept": "application/json",
                "Content-Type": "application/json",
            }
        return {
            "accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.auth_token}",
            "X-Model-Authorization": self.auth_token,
        }

    def get_nemo_client(self) -> AsyncNeMoMicroservices:
        """Get an authenticated NeMo microservices client."""
        return AsyncNeMoMicroservices(
            base_url=self.base_url,
        )

    # Constants for pagination safety checks
    MAX_CONSECUTIVE_SAME_COUNT = 3
    MAX_PAGES_FALLBACK = 10
    MAX_PAGES_SAFETY_LIMIT = 100

    async def fetch_guardrails_configs(self) -> tuple[list[str], list[dict[str, Any]]]:
        """Fetch available guardrails configurations with metadata using pagination.

        Note: The guardrails microservice as of 25.09 release has a pagination bug where it returns
        the same 10 configurations on every page instead of different ones. This method
        works around this bug by detecting duplicate configurations and stopping pagination
        early to prevent infinite loops and duplicate results.
        """
        namespace = getattr(self, "namespace", "default")
        logger.info(f"Fetching guardrails configs from {self.base_url} with namespace: {namespace}")
        try:
            nemo_client = self.get_nemo_client()
            configs = []
            configs_metadata = []
            seen_configs = set()  # Track seen config names to avoid duplicates
            page = 1
            has_more_pages = True
            last_page_item_count = 0
            consecutive_same_count = 0

            while has_more_pages:
                logger.debug(f"Fetching page {page}")
                response = await nemo_client.guardrail.configs.list(page=page, extra_headers=self.get_auth_headers())

                if hasattr(response, "data") and response.data:
                    current_page_item_count = len(response.data)
                    logger.debug(f"Found {current_page_item_count} configs on page {page}")

                    # Check if we're getting the same number of items repeatedly (possible loop)
                    # This is a workaround for the guardrails API bug where it returns the same data on every page
                    if current_page_item_count == last_page_item_count and current_page_item_count > 0:
                        consecutive_same_count += 1
                        logger.debug(
                            f"Same item count as last page ({current_page_item_count}), "
                            f"consecutive count: {consecutive_same_count}"
                        )
                        if consecutive_same_count >= self.MAX_CONSECUTIVE_SAME_COUNT:
                            logger.warning(
                                f"Getting same item count ({current_page_item_count}) repeatedly, "
                                f"stopping pagination to prevent loop"
                            )
                            has_more_pages = False
                            break
                    else:
                        consecutive_same_count = 0

                    last_page_item_count = current_page_item_count
                    new_configs_count = 0

                    for config in response.data:
                        config_name = getattr(config, "name", "")
                        config_description = getattr(config, "description", "")
                        config_created = getattr(config, "created", None)
                        config_updated = getattr(config, "updated", None)

                        logger.debug(f"Processing config: {config_name}")

                        if config_name and config_name not in seen_configs:
                            configs.append(config_name)
                            # Build metadata for this config
                            metadata = self._build_config_metadata(config_description, config_created, config_updated)
                            configs_metadata.append(metadata)
                            seen_configs.add(config_name)
                            new_configs_count += 1
                            logger.debug(f"Added config: {config_name}")
                        elif config_name in seen_configs:
                            # Skip duplicates caused by the API pagination bug
                            logger.debug(f"Skipping duplicate config: {config_name}")

                    # If we didn't get any new unique configs on this page, we might be done
                    if new_configs_count == 0:
                        logger.debug(f"No new unique configs found on page {page}, stopping pagination")
                        has_more_pages = False
                        break
                else:
                    logger.debug(f"No configs found on page {page}")
                    # If we get no data, we've definitely reached the end
                    has_more_pages = False
                    logger.debug("No data found, stopping pagination")
                    break

                # Check if there are more pages using the correct pagination structure
                has_more_pages = False

                # Strategy 1: Check pagination object (primary method based on API structure)
                if hasattr(response, "pagination") and response.pagination:
                    pagination = response.pagination
                    if hasattr(pagination, "total_pages") and hasattr(pagination, "page"):
                        has_more_pages = pagination.page < pagination.total_pages
                        logger.debug(
                            f"Using pagination page comparison: {pagination.page} < "
                            f"{pagination.total_pages} = {has_more_pages}"
                        )
                    elif hasattr(pagination, "has_next") and pagination.has_next is not None:
                        has_more_pages = bool(pagination.has_next)
                        logger.debug(f"Using pagination.has_next field: {has_more_pages}")

                # Strategy 2: Check for has_next field directly on response (fallback)
                elif hasattr(response, "has_next") and response.has_next is not None:
                    has_more_pages = bool(response.has_next)
                    logger.debug(f"Using has_next field: {has_more_pages}")

                # Strategy 3: Check if we got no data (indicates end of data)
                elif len(response.data) == 0:
                    has_more_pages = False
                    logger.debug(f"Using data length comparison: {len(response.data)} == 0 = {has_more_pages}")

                # Strategy 4: Conservative fallback - stop if we've hit a reasonable limit
                else:
                    # Stop after a reasonable number of pages to prevent infinite loops
                    has_more_pages = page < self.MAX_PAGES_FALLBACK
                    logger.debug(f"Using fallback page limit: page < {self.MAX_PAGES_FALLBACK} = {has_more_pages}")

                logger.debug(f"has_more_pages: {has_more_pages}")

                page += 1

                # Safety check to prevent infinite loops
                if page > self.MAX_PAGES_SAFETY_LIMIT:
                    logger.warning("Reached maximum page limit (100), stopping pagination")
                    break

            logger.info(f"Successfully fetched {len(configs)} guardrails configurations across {page - 1} pages")
            return configs, configs_metadata  # noqa: TRY300

        except Exception as e:  # noqa: BLE001
            logger.error(f"Error fetching guardrails configs: {e}")
            logger.error(f"Exception type: {type(e)}")
            if hasattr(e, "response") and e.response:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response text: {e.response.text}")
            return [], []

    def _build_config_metadata(self, description: str, created: Any, updated: Any) -> dict[str, Any]:
        """Build metadata for a guardrails configuration."""
        metadata = {
            "icon": "Settings",
            "description": description if description else "Guardrails configuration",
        }

        if created:
            metadata["created"] = str(created)
        if updated:
            metadata["updated"] = str(updated)

        return metadata

    async def create_guardrails_config(self, config_data: dict) -> str:
        """Create a new guardrails configuration using the NeMo microservices client."""
        config_name = config_data.get("01_config_name")
        namespace = getattr(self, "namespace", "default")
        logger.info(f"Creating guardrails config '{config_name}' in namespace '{namespace}'")
        logger.debug(f"Config data: {config_data}")

        try:
            # Extract config name
            config_name_required = "Config name is required"
            if not config_name:
                raise ValueError(config_name_required)
            logger.debug(f"Config name extracted: {config_name}")

            # Extract description
            description = config_data.get("02_config_description", "")
            logger.debug(f"Description extracted: {description}")

            # Extract rail types
            rail_types = config_data.get("03_rail_types", ["content_safety_input"])
            logger.debug(f"Rail types extracted: {rail_types}")

            # Build the configuration parameters
            logger.debug("Building guardrails parameters...")
            params = self._build_guardrails_params(config_data, rail_types)
            logger.debug(f"Built parameters: {json.dumps(params, indent=2)}")

            # Create the config using the NeMo microservices client
            logger.debug(f"Creating config with name: {config_name}, namespace: {namespace}")
            logger.debug(f"Built parameters: {json.dumps(params, indent=2)}")
            logger.debug(f"Description: {description}")
            logger.debug(f"Using base_url: {self.base_url}")
            logger.debug(f"Auth headers: {self.get_auth_headers()}")

            client = self.get_nemo_client()
            logger.debug("Making API call to guardrail.configs.create...")

            # Call the API with the correct parameter structure
            create_kwargs = {
                "name": config_name,
                "namespace": namespace,
                "data": params,
                "extra_headers": self.get_auth_headers(),
            }

            # Add description if provided
            if description:
                create_kwargs["description"] = description

            logger.debug(
                f"API call kwargs: {json.dumps({k: v for k, v in create_kwargs.items() if k != 'extra_headers'}, indent=2)}"  # noqa: E501
            )

            result = await client.guardrail.configs.create(**create_kwargs)

            logger.debug(f"API call completed. Result type: {type(result)}")
            logger.debug(f"Result object: {result}")

            config_id = result.name
            logger.info(f"Successfully created guardrails config '{config_name}' with ID: {config_id}")
            logger.debug(f"Returning config_id: {config_id}")

            return config_id  # noqa: TRY300

        except Exception as e:
            error_msg = f"Failed to create guardrails config '{config_name}': {e!s}"
            logger.error(error_msg)
            logger.error(f"Exception type: {type(e)}")
            logger.error(f"Exception details: {e}")
            raise

    def _build_guardrails_params(self, config_data: dict, rail_types: list[str]) -> dict:
        """Build parameters for guardrails configuration."""
        logger.debug(f"Building guardrails params with rail_types: {rail_types}")
        logger.debug(f"Config data keys: {list(config_data.keys())}")

        params = {
            "models": [],  # Required field for guardrails config
            "rails": {
                "input": {"flows": []},
                "output": {"flows": []},
            },
            "prompts": [],
        }

        # Configure content safety rails
        if "content_safety_input" in rail_types or "content_safety_output" in rail_types:
            params["models"].append(
                {
                    "type": "content_safety",
                    "engine": "nim",
                    "model": "nvidia/llama-3.1-nemoguard-8b-content-safety",
                    "parameters": {
                        "base_url": GUARDRAIL_MODEL_INTERNAL_URL,
                    },
                }
            )

        if "content_safety_input" in rail_types:
            params["rails"]["input"]["flows"].append("content safety check input $model=content_safety")
            content_safety_prompt = config_data.get("04_content_safety_prompt", DEFAULT_CONTENT_SAFETY_PROMPT)
            params["prompts"].append(
                {
                    "task": "content_safety_check_input $model=content_safety",
                    "content": content_safety_prompt,
                    "output_parser": "nemoguard_parse_prompt_safety",
                    "max_tokens": 50,
                }
            )

        if "content_safety_output" in rail_types:
            params["rails"]["output"]["flows"].append("content safety check output $model=content_safety")
            content_safety_output_prompt = config_data.get(
                "05_content_safety_output_prompt", DEFAULT_CONTENT_SAFETY_OUTPUT_PROMPT
            )
            params["prompts"].append(
                {
                    "task": "content_safety_check_output $model=content_safety",
                    "content": content_safety_output_prompt,
                    "output_parser": "nemoguard_parse_response_safety",
                    "max_tokens": 50,
                }
            )

        # Configure topic control rail

        if "topic_control" in rail_types:
            params["models"].append(
                {
                    "type": "topic_control",
                    "engine": "nim",
                    "model": "nvidia/llama-3.1-nemoguard-8b-topic-control",
                    "parameters": {
                        "base_url": GUARDRAIL_MODEL_INTERNAL_URL,
                    },
                }
            )
            params["rails"]["input"]["flows"].append("topic safety check input $model=topic_control")
            topic_control_prompt = config_data.get("06_topic_control_prompt", DEFAULT_TOPIC_CONTROL_PROMPT)
            params["prompts"].append(
                {"task": "topic_safety_check_input $model=topic_control", "content": topic_control_prompt}
            )

        # Configure jailbreak detection rail
        if "jailbreak_detection" in rail_types:
            params["rails"]["input"]["flows"].append("jailbreak detection")
            params["rails"]["input"]["flows"].append("jailbreak detection heuristics")

        # Configure self check input rail
        if "self_check_input" in rail_types:
            params["rails"]["input"]["flows"].append("self check input")
            self_check_prompt = config_data.get("06_self_check_prompt", DEFAULT_SELF_CHECK_PROMPT)
            params["prompts"].append({"task": "self_check_input", "content": self_check_prompt})

        # Configure self check output rail
        if "self_check_output" in rail_types:
            params["rails"]["output"]["flows"].append("self check output")
            self_check_prompt = config_data.get("06_self_check_prompt", DEFAULT_SELF_CHECK_PROMPT)
            params["prompts"].append({"task": "self_check_output", "content": self_check_prompt})

        # Configure self check hallucination rail
        if "self_check_hallucination" in rail_types:
            params["rails"]["output"]["flows"].append("self check hallucination")
            self_check_prompt = config_data.get("06_self_check_prompt", DEFAULT_SELF_CHECK_PROMPT)
            params["prompts"].append({"task": "self_check_hallucination", "content": self_check_prompt})

        logger.debug(f"Built guardrails params: {json.dumps(params, indent=2)}")
        return params

    def _get_nemo_exception_message(self, e: Exception):
        """Get a message from an exception."""
        try:
            if hasattr(e, "body") and isinstance(e.body, dict):
                message = e.body.get("message")
                if message:
                    return message
        except Exception:  # noqa: BLE001
            pass
        return None

    async def update_build_config(
        self, build_config: dotdict, field_value: Any, field_name: str | None = None
    ) -> dotdict | str:
        """Update build configuration for the guardrails component."""
        logger.info(f"Updating build config for field: {field_name}, value: {field_value}")

        # Handle mode changes - update visibility of inputs and outputs
        if field_name == "mode":
            mode = field_value
            logger.info(f"Mode changed to: {mode}")

            # Update visibility of LLM-specific inputs
            if mode == "chat":
                build_config["max_tokens"]["show"] = True
                build_config["temperature"]["show"] = True
                build_config["top_p"]["show"] = True
                build_config["model"]["show"] = True
                build_config["validation_mode"]["show"] = False
            else:  # check mode
                build_config["max_tokens"]["show"] = False
                build_config["temperature"]["show"] = False
                build_config["top_p"]["show"] = False
                build_config["model"]["show"] = False
                build_config["validation_mode"]["show"] = True

            # Update outputs based on mode
            if "outputs" not in build_config:
                build_config["outputs"] = []

            if mode == "chat":
                # In chat mode: show LLM outputs
                build_config["outputs"] = [
                    Output(
                        display_name="Model Response",
                        name="text_output",
                        method="text_response",
                        dynamic=True,
                    ),
                    Output(
                        display_name="Language Model",
                        name="model_output",
                        method="build_model",
                        dynamic=True,
                    ),
                ]
            elif mode == "check":
                # In check mode: show single validation output
                build_config["outputs"] = [
                    Output(
                        display_name="Validated Output",
                        name="validated_output",
                        method="validated_output",
                        dynamic=True,
                    ),
                ]

            logger.info(f"Updated outputs for {mode} mode: {build_config['outputs']}")

        # Handle config creation dialog
        if field_name == "config" and isinstance(field_value, dict) and "01_config_name" in field_value:
            try:
                config_id = await self.create_guardrails_config(field_value)
                logger.info(f"Config creation completed with ID: {config_id}")

                # Refresh the config list
                configs, configs_metadata = await self.fetch_guardrails_configs()
                build_config["config"]["options"] = configs
                build_config["config"]["options_metadata"] = configs_metadata

                # Set the newly created config as selected
                config_name = field_value.get("01_config_name")
                if config_name in configs:
                    build_config["config"]["value"] = config_name
                else:
                    pass
                return config_id  # noqa: TRY300
            except Exception as e:  # noqa: BLE001
                logger.error(f"Config creation failed: {e}")
                return {"error": f"Failed to create config: {e}"}

        # Handle config refresh
        if field_name == "config" and (field_value is None or field_value == ""):
            logger.debug("Config refresh requested")
            return await self._handle_config_refresh(build_config)

        # Handle existing config selection
        if field_name == "config" and isinstance(field_value, str):
            logger.debug(f"Config selection: {field_value}")

            # Populate options if they're empty (similar to KBRetrievalComponent pattern)
            if not build_config.get("config", {}).get("options"):
                try:
                    configs, configs_metadata = await self.fetch_guardrails_configs()
                    build_config["config"]["options"] = configs
                    build_config["config"]["options_metadata"] = configs_metadata
                    logger.debug(f"Populated config options: {configs}")
                except Exception as e:  # noqa: BLE001
                    logger.error(f"Error fetching configs for selection: {e}")
                    build_config["config"]["options"] = []
                    build_config["config"]["options_metadata"] = []

            build_config["config"]["value"] = field_value
            return build_config

        # Handle model refresh
        if field_name == "model" and (field_value is None or field_value == ""):
            logger.debug("Model refresh requested")
            return await self._handle_model_refresh(build_config)

        return build_config

    async def _handle_config_refresh(self, build_config: dotdict) -> dotdict:
        """Handle config refresh with selection preservation."""
        logger.info("Handling config refresh request")

        try:
            # Preserve the current selection before refreshing
            current_value = build_config.get("config", {}).get("value")
            logger.debug(f"Preserving current config selection: {current_value}")

            # Fetch available configs
            logger.debug("Refreshing available configs for guardrails")
            configs, configs_metadata = await self.fetch_guardrails_configs()
            build_config["config"]["options"] = configs
            build_config["config"]["options_metadata"] = configs_metadata

            # Restore the current selection if it's still valid
            if current_value and current_value in configs:
                build_config["config"]["value"] = current_value
                logger.debug(f"Restored config selection: {current_value}")
            elif configs and not current_value:
                # Set default config if no current selection
                default_config = None
                for config in configs:
                    if "default" in config.lower():
                        default_config = config
                        break

                if not default_config:
                    default_config = configs[0]

                build_config["config"]["value"] = default_config
                logger.debug(f"Set default config selection: {default_config}")
            elif current_value:
                logger.warning(f"Previously selected config '{current_value}' no longer available in refreshed list")
                # Clear the value when the selected config is no longer available
                build_config["config"]["value"] = ""
            else:
                # No configs available, clear the value
                build_config["config"]["value"] = ""

            logger.info(f"Refreshed {len(configs)} available configs for guardrails")

        except Exception as e:  # noqa: BLE001
            logger.error(f"Error refreshing configs: {e}")
            build_config["config"]["options"] = []
            build_config["config"]["options_metadata"] = []

        return build_config

    async def process(self) -> dict[str, Message]:
        """Process the input through guardrails validation (for check mode)."""
        logger.info("Starting guardrails validation process")

        # Prepare input
        input_text = ""
        if hasattr(self, "system_message") and self.system_message:
            input_text += f"{self.system_message}\n\n"
        if hasattr(self, "input_value") and self.input_value:
            if isinstance(self.input_value, Message):
                input_text += self.input_value.text
            else:
                input_text += str(self.input_value)

        logger.debug(f"Prepared input text: {input_text[:200]}...")  # Log first 200 chars

        empty_message_error = "The message you want to validate is empty."
        if not input_text.strip():
            logger.error("Empty input text provided")
            raise ValueError(empty_message_error)

        validation_mode = getattr(self, "validation_mode", "input")
        logger.info(f"Processing validation in {validation_mode} mode")

        try:
            # Use the proper guardrail.check operation for validation
            client = self.get_nemo_client()

            logger.debug("Making API call to guardrail.check for validation")

            # Determine message role based on validation mode
            role = "user" if validation_mode == "input" else "assistant"

            # Use the dedicated validation endpoint
            validation_response = await client.guardrail.check(
                messages=[{"role": role, "content": input_text}],
                guardrails={"config_id": self.config},
                extra_headers=self.get_auth_headers(),
            )

            logger.debug(f"Validation response: {validation_response}")

            # Check if the response indicates blocking
            # The guardrail.check response should indicate whether validation passed or failed
            if hasattr(validation_response, "blocked") and validation_response.blocked:
                logger.info(f"{validation_mode.capitalize()} blocked by guardrails")
                self.status = f"{validation_mode.capitalize()} blocked by guardrails"
                # Return error message with error=True and category="error"
                return {
                    "validated_output": Message(
                        text=f"I cannot process that {validation_mode}.", error=True, category="error"
                    )
                }
            if hasattr(validation_response, "choices") and validation_response.choices:
                # Fallback to checking choices if blocked field not available
                choice = validation_response.choices[0]
                if hasattr(choice, "finish_reason") and choice.finish_reason == "guardrail_blocked":
                    logger.info(f"{validation_mode.capitalize()} blocked by guardrails")
                    self.status = f"{validation_mode.capitalize()} blocked by guardrails"
                    return {
                        "validated_output": Message(
                            text=f"I cannot process that {validation_mode}.", error=True, category="error"
                        )
                    }

            # If validation passes, return the original input with error=False and category="message"
            logger.info(f"{validation_mode.capitalize()} passed guardrails validation")
            self.status = f"{validation_mode.capitalize()} validated successfully"
            return {"validated_output": Message(text=input_text, error=False, category="message")}

        except Exception as e:
            logger.error(f"Error in validation: {e}")
            logger.error(f"Exception type: {type(e)}")
            if hasattr(e, "response") and e.response:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response text: {e.response.text}")
            if message := self._get_nemo_exception_message(e):
                logger.error(f"Exception message: {message}")
                raise ValueError(message) from e
            raise

    async def validated_output(self) -> Message:
        """Return the validated output as a Message (for check mode).

        Returns a single Message that contains either:
        - The validated input (error=False, category="message") when validation passes
        - An error message (error=True, category="error") when validation fails

        Downstream components can check the Message's error field to determine validation status.
        """
        result = await self.process()
        validated_output = result.get("validated_output")
        if validated_output is None:
            # This should never happen if process() is working correctly
            logger.error("process() returned result without 'validated_output' key")
            error_msg = "Unexpected result format from guardrails validation"
            raise RuntimeError(error_msg)
        return validated_output

    async def fetch_guardrails_models(self) -> list[str]:
        """Fetch available models for guardrails using the general models endpoint."""
        logger.info("Fetching available models using general models endpoint")
        try:
            client = self.get_nemo_client()
            logger.debug("Using NeMo microservices client to fetch models")

            # Use the client's models resource
            models_response = await client.models.list(extra_headers=self.get_auth_headers())
            logger.debug(f"Models response: {models_response}")

            # Import ChatNVIDIA's model filtering logic
            try:
                from langchain_nvidia_ai_endpoints._statics import determine_model
            except ImportError:
                logger.warning("langchain-nvidia-ai-endpoints not available, falling back to basic filtering")
                return self._fallback_model_filtering(models_response)

            model_names = []
            total_models = 0
            chat_models = 0

            if hasattr(models_response, "data") and models_response.data:
                for model in models_response.data:
                    total_models += 1
                    model_id = None

                    # Extract model ID
                    if hasattr(model, "id") and model.id:
                        model_id = model.id
                    elif hasattr(model, "name") and model.name:
                        model_id = model.name

                    if model_id:
                        # Use ChatNVIDIA's lookup table to determine model type
                        known_model = determine_model(model_id)
                        if known_model and known_model.model_type == "chat":
                            model_names.append(model_id)
                            chat_models += 1
                            logger.debug(f"Added chat model: {model_id}")
                        elif known_model:
                            logger.debug(f"Skipped {known_model.model_type} model: {model_id}")
                        # Unknown model - use name-based filtering as fallback
                        elif self._is_likely_chat_model(model_id):
                            model_names.append(model_id)
                            chat_models += 1
                            logger.debug(f"Added likely chat model (fallback): {model_id}")
                        else:
                            logger.debug(f"Skipped unknown model: {model_id}")

            logger.info(f"Found {chat_models} chat models out of {total_models} total models")
            return model_names  # noqa: TRY300

        except Exception as exc:  # noqa: BLE001
            logger.error(f"Error fetching models using NeMo microservices client: {exc}")
            return []

    def _is_likely_chat_model(self, model_id: str) -> bool:
        """Fallback method to determine if a model is likely a chat model based on name."""
        model_id_lower = model_id.lower()

        # Exclude known non-chat models
        if any(keyword in model_id_lower for keyword in ["embed", "embedqa", "rerank", "rerankqa", "nemoguard"]):
            return False

        # Include likely chat models
        chat_indicators = ["instruct", "chat", "completion", "nemotron", "llama-3", "gpt", "claude"]
        return any(indicator in model_id_lower for indicator in chat_indicators)

    def _fallback_model_filtering(self, models_response) -> list[str]:
        """Fallback method when ChatNVIDIA's lookup table is not available."""
        logger.info("Using fallback model filtering")
        model_names = []

        if hasattr(models_response, "data") and models_response.data:
            for model in models_response.data:
                model_id = None
                if hasattr(model, "id") and model.id:
                    model_id = model.id
                elif hasattr(model, "name") and model.name:
                    model_id = model.name

                if model_id and self._is_likely_chat_model(model_id):
                    model_names.append(model_id)

        return model_names

    async def _handle_model_refresh(self, build_config: dotdict) -> dotdict:
        """Handle model refresh with selection preservation."""
        logger.info("Handling model refresh request")

        try:
            # Preserve the current selection before refreshing
            current_value = build_config.get("model", {}).get("value")
            logger.debug(f"Preserving current model selection: {current_value}")

            # Fetch all available models for guardrails
            logger.debug("Refreshing available models for guardrails")
            models = await self.fetch_guardrails_models()
            build_config["model"]["options"] = models

            # Restore the current selection if it's still valid
            if current_value and current_value in models:
                build_config["model"]["value"] = current_value
                logger.debug(f"Restored model selection: {current_value}")
            elif models and not current_value:
                # Only set default if no current selection
                build_config["model"]["value"] = models[0]
                logger.debug(f"Set default model selection: {models[0]}")
            elif current_value:
                logger.warning(f"Previously selected model '{current_value}' no longer available in refreshed list")
                # Clear the value when the selected model is no longer available
                build_config["model"]["value"] = ""
            else:
                # No models available, clear the value
                build_config["model"]["value"] = ""

            logger.info(f"Refreshed {len(models)} available models for guardrails")

        except Exception as e:  # noqa: BLE001
            logger.error(f"Error refreshing models: {e}")
            build_config["model"]["options"] = []
            build_config["model"]["value"] = ""

        return build_config

    def build_model(self) -> LanguageModel:
        """Build a language model that uses the guardrails microservice."""
        mode = getattr(self, "mode", "chat")

        if mode == "check":
            error_msg = "Check mode does not provide a language model. Use the validation outputs instead."
            raise NotImplementedError(error_msg)

        logger.info(
            f"Building guardrails model with config: {getattr(self, 'config', 'None')}, "
            f"model: {getattr(self, 'model', 'None')}"
        )

        # Validate configuration
        base_url_required = "Base URL is required"
        auth_token_required = "Authentication token is required"
        namespace_required = "Namespace is required"
        model_required = "Model selection is required"

        if not hasattr(self, "model") or not self.model:
            logger.error("Model selection is required but not set")
            raise ValueError(model_required)

        # temp fix for config
        config = self.config or "content-safety"

        # if not hasattr(self, "config") or not self.config:
        #    logger.error("Guardrails configuration is required but not set")
        #    raise ValueError(config_required)

        if not hasattr(self, "base_url") or not self.base_url:
            logger.error("Base URL is required but not set")
            raise ValueError(base_url_required)

        if not hasattr(self, "auth_token") or not self.auth_token:
            logger.error("Authentication token is required but not set")
            raise ValueError(auth_token_required)

        if not hasattr(self, "namespace") or not self.namespace:
            logger.error("Namespace is required but not set")
            raise ValueError(namespace_required)

        logger.info(
            f"Creating GuardrailsMicroserviceModel with base_url: {self.base_url}, "
            f"config_id: {self.config}, model: {self.model}"
        )

        return GuardrailsMicroserviceModel(
            base_url=self.base_url,
            auth_token=self.auth_token,
            config_id=config,
            model_name=self.model,
            streaming=self.stream,
            max_tokens=getattr(self, "max_tokens", 1024),
            temperature=getattr(self, "temperature", 0.7),
            top_p=getattr(self, "top_p", 0.9),
        )

    async def text_response(self) -> Message:
        """Handle text response based on mode."""
        mode = getattr(self, "mode", "chat")

        if mode == "check":
            # In check mode, perform validation and return the validated output
            result = await self.process()
            return result.get("validated_output", Message(text="Validation completed", error=False, category="message"))
        # In chat mode, use the normal LLM response
        return await super().text_response()
