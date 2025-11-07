from dotenv import load_dotenv

from lfx.base.io.text import TextComponent
from lfx.io import Output, StrInput
from lfx.schema.message import Message
import time

load_dotenv()


class LangfusePromptComponent(TextComponent):
    display_name = "Langfuse Prompt"
    description = "Fetches a prompt from Langfuse by name and auto-refreshes when changes are detected."
    documentation: str = "https://docs.langflow.org/components-io#langfuse-prompt"
    icon = "type"
    name = "LangfusePrompt"

    inputs = [
        StrInput(
            name="prompt_name",
            display_name="Prompt Name",
            info="The name of the prompt in Langfuse (e.g., 'translator_system-prompt').",
            required=True,
        ),
        StrInput(
            name="label",
            display_name="Label",
            info="The label of the prompt in Langfuse (e.g., 'production', 'latest').",
            required=False,
            value="latest",
        ),
        StrInput(
            name="refresh_interval",
            display_name="Refresh Interval (seconds)",
            info="How often to check for prompt updates. Set to 0 to disable auto-refresh.",
            required=False,
            value="5",
        ),
    ]

    outputs = [
        Output(display_name="Prompt", name="prompt", method="fetch_prompt"),
    ]

    def fetch_prompt(self) -> Message:
        """Fetch the prompt from Langfuse and return as a Message."""
        try:
            from langfuse import Langfuse
        except ImportError as e:
            msg = "Langfuse is not installed. Please install it with: pip install langfuse"
            raise ImportError(msg) from e

        # Initialize Langfuse client (uses env vars: LANGFUSE_SECRET_KEY, LANGFUSE_PUBLIC_KEY, LANGFUSE_HOST)
        try:
            langfuse = Langfuse()
        except Exception as e:
            msg = (
                f"Failed to initialize Langfuse client. "
                f"Ensure LANGFUSE_SECRET_KEY, LANGFUSE_PUBLIC_KEY, and LANGFUSE_HOST "
                f"environment variables are set: {e}"
            )
            raise ConnectionError(msg) from e

        # Fetch the prompt
        try:
            langfuse_prompt = langfuse.get_prompt(self.prompt_name, label=self.label)
        except Exception as e:
            msg = f"Failed to fetch prompt '{self.prompt_name}' from Langfuse: {e}"
            raise ValueError(msg) from e

        # Extract prompt text
        try:
            # Get LangChain-compatible prompt
            prompt_text = str(langfuse_prompt.get_langchain_prompt())
        except Exception as e:
            msg = f"Failed to extract prompt text from Langfuse response: {e}"
            raise ValueError(msg) from e

        self.status = f"Fetched prompt: {self.prompt_name}"
        return Message(text=prompt_text)
