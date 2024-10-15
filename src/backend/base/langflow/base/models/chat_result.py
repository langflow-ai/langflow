import warnings

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from langflow.field_typing.constants import LanguageModel
from langflow.schema.message import Message


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
                    messages.append(input_value.to_lc_message())
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
):
    if not input_value and not system_message:
        msg = "The message you want to send to the model is empty."
        raise ValueError(msg)

    messages, runnable = build_messages_and_runnable(
        input_value=input_value, system_message=system_message, original_runnable=runnable
    )

    inputs: list | dict = messages or {}
    try:
        if config and config.get("output_parser") is not None:
            runnable = runnable | config["output_parser"]

        if config:
            runnable = runnable.with_config(
                {
                    "run_name": config.get("display_name", ""),
                    "project_name": config.get("get_project_name", lambda: "")(),
                    "callbacks": config.get("get_langchain_callbacks", list)(),
                }
            )
        if stream:
            return runnable.stream(inputs)
        message = runnable.invoke(inputs)
        return message.content if hasattr(message, "content") else message
    except Exception as e:
        if config and config.get("_get_exception_message") and (message := config["_get_exception_message"](e)):
            raise ValueError(message) from e
        raise
