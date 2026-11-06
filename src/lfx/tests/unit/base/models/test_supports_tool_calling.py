"""Regression tests for ``LCModelComponent.supports_tool_calling``.

Providers implement ``bind_tools`` as ``self.bind(tools=...)``, which returns a
``RunnableBinding`` that keeps the tools in ``.kwargs["tools"]`` and has no ``.tools``
attribute. The check must still report tool support for those models.
"""

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from lfx.base.models.model import LCModelComponent


def _fake_messages():
    return iter([AIMessage(content="ok")])


class _BindingToolModel(GenericFakeChatModel):
    """bind_tools returns a RunnableBinding, like ChatAnthropic and ChatGoogleGenerativeAI."""

    def bind_tools(self, tools, **kwargs):
        return self.bind(tools=[{"name": tool.__name__} for tool in tools], **kwargs)


class _AttributeToolModel(GenericFakeChatModel):
    """bind_tools returns a model exposing the tools as an attribute."""

    tools: list = []

    def bind_tools(self, tools, **kwargs):  # noqa: ARG002
        return self.model_copy(update={"tools": list(tools)})


class _NoToolModel(GenericFakeChatModel):
    """Inherits BaseChatModel.bind_tools, which is not implemented."""


class _EmptyToolsModel(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):  # noqa: ARG002
        return self.bind(tools=[])


def _supports(model) -> bool:
    return LCModelComponent.supports_tool_calling(None, model)  # type: ignore[arg-type]


def test_binding_with_tools_in_kwargs_is_supported():
    assert _supports(_BindingToolModel(messages=_fake_messages())) is True


def test_tools_exposed_as_attribute_is_supported():
    assert _supports(_AttributeToolModel(messages=_fake_messages())) is True


def test_default_bind_tools_is_not_supported():
    assert _supports(_NoToolModel(messages=_fake_messages())) is False


def test_binding_with_no_tools_is_not_supported():
    assert _supports(_EmptyToolsModel(messages=_fake_messages())) is False
