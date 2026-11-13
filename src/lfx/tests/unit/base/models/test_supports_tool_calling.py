"""``LCModelComponent.supports_tool_calling`` against the shapes ``bind_tools`` returns."""

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from lfx.base.models.model import LCModelComponent


def _messages():
    return iter([AIMessage(content="ok")])


class _BindingToolModel(GenericFakeChatModel):
    """Binds tools like ChatGoogleGenerativeAI and ChatAnthropic: a RunnableBinding with ``kwargs["tools"]``."""

    def bind_tools(self, tools, **kwargs):
        return self.bind(tools=[{"name": tool.__name__} for tool in tools], **kwargs)


class _AttributeToolModel(GenericFakeChatModel):
    """Returns a copy exposing the bound tools as a ``tools`` attribute."""

    tools: list = []

    def bind_tools(self, tools, **kwargs):  # noqa: ARG002
        return self.model_copy(update={"tools": list(tools)})


class _InheritedBindToolsModel(GenericFakeChatModel):
    """Keeps ``BaseChatModel.bind_tools``, which raises NotImplementedError."""


class _RefusingBindToolsModel(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):
        raise NotImplementedError


class _EmptyBindingModel(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):  # noqa: ARG002
        return self.bind(tools=[])


def _supports(model) -> bool:
    return LCModelComponent.supports_tool_calling(None, model)  # type: ignore[arg-type]


def test_should_support_tools_when_the_binding_keeps_them_in_kwargs():
    assert _supports(_BindingToolModel(messages=_messages())) is True


def test_should_support_tools_when_the_bound_model_exposes_them():
    assert _supports(_AttributeToolModel(messages=_messages())) is True


def test_should_not_support_tools_when_bind_tools_is_inherited():
    assert _supports(_InheritedBindToolsModel(messages=_messages())) is False


def test_should_not_support_tools_when_bind_tools_raises_not_implemented():
    assert _supports(_RefusingBindToolsModel(messages=_messages())) is False


def test_should_not_support_tools_when_the_binding_carries_none():
    assert _supports(_EmptyBindingModel(messages=_messages())) is False
