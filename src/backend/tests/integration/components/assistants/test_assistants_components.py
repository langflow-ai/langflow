import pytest

from langflow.components.astra_assistants import AstraAssistantManager
from tests.integration.utils import run_single_component


@pytest.mark.api_key_required
@pytest.mark.asyncio
async def test_manager():
    system_prompt = "you're a very detailed ascii artist"
    user_message = "draw a cat eating ice cream"
    results = await iterate(system_prompt, user_message)
    is_complete = bool(results["tool_output"].data["text"])
    i = 0
    while not is_complete and i < 10:
        user_message = "continue"
        results = await iterate(system_prompt, user_message)
        is_complete = bool(results["tool_output"].data["text"])
        i += 1


async def iterate(system_prompt, user_message):
    results = await run_single_component(
        AstraAssistantManager,
        inputs={
            "instructions": system_prompt,
            "model_name": "gpt-4o-mini",
            "user_message": user_message,
            "tool": "ReActThoughtTool",
        },
    )
    assert results["assistant_response"].text is not None
    print(results["assistant_response"].text)
    thread_id = results["output_thread_id"].text
    results = await run_single_component(
        AstraAssistantManager,
        inputs={
            "instructions": system_prompt,
            "model_name": "gpt-4o-mini",
            "user_message": "check to see if you are finished, do at least a few iterations",
            "tool": "ReActDeciderTool",
            "input_thread_id": thread_id,
        },
    )
    assert results["assistant_response"].text is not None
    print(results["assistant_response"].text)
    return results


async def list_assistants():
    from langflow.components.astra_assistants import AssistantsListAssistants

    results = await run_single_component(
        AssistantsListAssistants,
        inputs={},
    )
    assert results["assistants"].text is not None


@pytest.mark.api_key_required
@pytest.mark.asyncio
async def test_create_assistants():
    from langflow.components.astra_assistants import AssistantsCreateAssistant

    results = await run_single_component(
        AssistantsCreateAssistant,
        inputs={
            "assistant_name": "artist-bot",
            "instructions": "reply only with ascii art",
            "model": "gpt-4o-mini",
        },
    )
    assistant_id = results["assistant_id"].text
    assert assistant_id is not None
    await list_assistants()
    await get_assistant_name(assistant_id)
    thread_id = await test_create_thread()
    await run_assistant(assistant_id, thread_id)


@pytest.mark.api_key_required
@pytest.mark.asyncio
async def test_create_thread():
    from langflow.components.astra_assistants import AssistantsCreateThread

    results = await run_single_component(
        AssistantsCreateThread,
        inputs={},
    )
    thread_id = results["thread_id"].text
    assert thread_id is not None
    return thread_id


async def get_assistant_name(assistant_id):
    from langflow.components.astra_assistants import AssistantsGetAssistantName

    results = await run_single_component(
        AssistantsGetAssistantName,
        inputs={
            "assistant_id": assistant_id,
        },
    )
    assert results["assistant_name"].text is not None


async def run_assistant(assistant_id, thread_id):
    from langflow.components.astra_assistants import AssistantsRun

    results = await run_single_component(
        AssistantsRun,
        inputs={
            "assistant_id": assistant_id,
            "user_message": "hello",
            "thread_id": thread_id,
        },
    )
    assert results["assistant_response"].text is not None
