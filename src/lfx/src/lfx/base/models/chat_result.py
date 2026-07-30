import warnings
from collections.abc import Callable
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from lfx.field_typing.constants import LanguageModel
from lfx.schema.message import Message


def _as_user_turn(message: BaseMessage) -> BaseMessage:
    """Send the component's input as a user turn even when it came from an upstream model.

    A Language Model chained after an Agent receives that agent's response
    (sender=Machine → AIMessage) as its input. Sending it unchanged makes the request
    end on a model turn, which Gemini rejects with 400 "Requests ending with a model
    turn are not supported".
    """
    if isinstance(message, AIMessage):
        return HumanMessage(content=message.content)
    return message


def _remediate(error: Exception, runnable: Any, applied: set[str]) -> bool:
    """Clear a model constraint the provider only reports at call time; True means retry.

    Mirrors ``LCModelComponent._remediate_model_error`` for the components that reach a
    model over a connection (Structured Output, LLM Selector) rather than building it.
    """
    from lfx.base.models.model_remediation import apply_overrides_to_model, find_remediation

    error_text = f"{error} {getattr(error, '__cause__', '') or ''}"
    remediation = find_remediation(error_text, provider=None, already_applied=applied)
    if remediation is None or not apply_overrides_to_model(runnable, remediation.overrides):
        return False
    applied.add(remediation.name)
    return True


def build_messages_and_runnable(
    input_value: str | Message, system_message: str | None, original_runnable: LanguageModel
) -> tuple[list[BaseMessage], LanguageModel]:
    messages: list[BaseMessage] = []
    system_message_added = False
    runnable = original_runnable

    if input_value:
        if isinstance(input_value, Message):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                if "prompt" in input_value:
                    prompt = input_value.load_lc_prompt()
                    if system_message:
                        prompt.messages = [
                            SystemMessage(content=system_message),
                            *prompt.messages,  # type: ignore[has-type]
                        ]
                        system_message_added = True
                    runnable = prompt | runnable
                else:
                    messages.append(_as_user_turn(input_value.to_lc_message()))
        else:
            messages.append(HumanMessage(content=input_value))

    if system_message and not system_message_added:
        messages.insert(0, SystemMessage(content=system_message))

    return messages, runnable


def get_chat_result(
    runnable: LanguageModel,
    input_value: str | Message,
    system_message: str | None = None,
    config: dict | None = None,
    *,
    stream: bool = False,
    token_usage_callback: Callable[[Any], None] | None = None,
):
    if not input_value and not system_message:
        msg = "The message you want to send to the model is empty."
        raise ValueError(msg)

    # A Prompt input turns ``runnable`` into a chain; remediation has to target the
    # chat model itself, which that chain keeps a reference to.
    chat_model = runnable
    messages, runnable = build_messages_and_runnable(
        input_value=input_value, system_message=system_message, original_runnable=runnable
    )

    inputs: list | dict = messages or {}
    applied_remediations: set[str] = set()
    while True:
        try:
            active: Any = runnable
            if config and config.get("output_parser") is not None:
                active |= config["output_parser"]

            if config:
                active = active.with_config(
                    {
                        "run_name": config.get("display_name", ""),
                        "project_name": config.get("get_project_name", lambda: "")(),
                        "callbacks": config.get("get_langchain_callbacks", list)(),
                    }
                )
            if stream:
                return active.stream(inputs)
            message = active.invoke(inputs)
            if token_usage_callback is not None and hasattr(message, "content"):
                token_usage_callback(message)
            return message.content if hasattr(message, "content") else message
        except Exception as e:
            if _remediate(e, chat_model, applied_remediations):
                continue
            if config and config.get("_get_exception_message") and (message := config["_get_exception_message"](e)):
                raise ValueError(message) from e
            raise
