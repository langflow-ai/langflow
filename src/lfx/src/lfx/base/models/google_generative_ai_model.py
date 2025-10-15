from langchain_google_genai import ChatGoogleGenerativeAI


class ChatGoogleGenerativeAIFixed(ChatGoogleGenerativeAI):
    """Custom ChatGoogleGenerativeAI that fixes function response name issues for Gemini."""

    def __init__(self, *args, **kwargs):
        """Initialize with fix for empty function response names in ToolMessage and FunctionMessage."""
        if ChatGoogleGenerativeAI is None:
            msg = "The 'langchain_google_genai' package is required to use the Google Generative AI model."
            raise ImportError(msg)

        # Initialize the parent class
        super().__init__(*args, **kwargs)

    def _prepare_request(self, messages, **kwargs):
        """Override request preparation to fix empty function response names."""
        from langchain_core.messages import FunctionMessage, ToolMessage

        # Pre-process messages to ensure tool/function messages have names
        fixed_messages = []
        for message in messages:
            fixed_message = message
            if isinstance(message, ToolMessage) and not message.name:
                # Create a new ToolMessage with a default name
                fixed_message = ToolMessage(
                    content=message.content,
                    name="tool_response",
                    tool_call_id=getattr(message, "tool_call_id", None),
                    artifact=getattr(message, "artifact", None),
                )
            elif isinstance(message, FunctionMessage) and not message.name:
                # Create a new FunctionMessage with a default name
                fixed_message = FunctionMessage(content=message.content, name="function_response")
            fixed_messages.append(fixed_message)

        # Call the parent's method with fixed messages
        return super()._prepare_request(fixed_messages, **kwargs)
