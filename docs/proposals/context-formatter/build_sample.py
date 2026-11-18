# ruff: noqa: INP001
"""Export a credential-free, executable Context Formatter demonstration."""

from pathlib import Path

from lfx.components.input_output.chat import ChatInput
from lfx.components.input_output.chat_output import ChatOutput
from lfx.components.utilities.context_formatter import ContextFormatterComponent
from lfx.graph import Graph


def build_graph():
    request = ChatInput().set(input_value="Explain the refund policy.", should_store_message=False)
    formatter = ContextFormatterComponent().set(
        request=request.message_response,
        facts_json='[{"key":"refund-policy","text":"Refund proposals require a settled payment of at most 100."}]',
    )
    output = ChatOutput().set(input_value=formatter.format_context, should_store_message=False)
    return Graph(start=request, end=output)


if __name__ == "__main__":
    Path(__file__).with_name("sample-flow.json").write_text(
        build_graph().dumps(name="Context Formatter Preview", description="Preview formatted context without a model."),
        encoding="utf-8",
    )
