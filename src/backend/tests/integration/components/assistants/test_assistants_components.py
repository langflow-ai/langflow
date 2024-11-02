import pytest

from tests.integration.utils import run_single_component


@pytest.mark.api_key_required
async def test_list_assistants():
    from langflow.components.astra_assistants import AssistantsListAssistants

    results = await run_single_component(
        AssistantsListAssistants,
        inputs={},
    )
    assert results["assistants"].text is not None


@pytest.mark.api_key_required
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
    await test_list_assistants()
    await get_assistant_name(assistant_id)
    thread_id = await test_create_thread()
    await run_assistant(assistant_id, thread_id)


@pytest.mark.api_key_required
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
