"""A complex chat flow example with multiple chained components.

This script demonstrates a more complex conversational flow using multiple
components chained together.

Features:
- ChatInput -> TextInput -> TextOutput -> ChatOutput chain
- Tests graph loading with multiple component types
- Verifies chained connections work properly

Usage:
    python complex_chat_flow.py
"""

from lfx.components.input_output import ChatInput, ChatOutput, TextInputComponent, TextOutputComponent
from lfx.graph import Graph

# Create components
chat_input = ChatInput()
text_input = TextInputComponent()
text_output = TextOutputComponent()
chat_output = ChatOutput()

# Connect components in a chain
text_input.set(input_value=chat_input.message_response)
text_output.set(input_value=text_input.text_response)
chat_output.set(input_value=text_output.text_response)

# Create graph with chain of components
graph = Graph(start=chat_input, end=chat_output)
