"""Run the GenMagic components through Langflow's own execution paths (graph, output building, agent tools).

Only the HTTP boundary is mocked. These tests guard what a paid API needs most: one request per
run however many outputs are connected, and one tool, with only the prompt, for an agent.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph import Graph
from lfx_bundles.genmagic.genmagic_image_generation import GenMagicImageGenerationComponent
from lfx_bundles.genmagic.genmagic_text_to_speech import GenMagicTextToSpeechComponent
from lfx_bundles.genmagic.genmagic_video_generation import GenMagicVideoGenerationComponent

from .conftest import API_KEY, response

IMAGE_URL = "https://genmagic.co/media/image-1.png"
VIDEO_URL = "https://genmagic.co/media/video-1.mp4"


def _image_reply():
    return response(json_body={"data": [{"url": IMAGE_URL}]}, headers={"X-Cost-Cents": "3"})


def _speech_reply():
    return response(content=b"audio", headers={"Content-Type": "audio/mpeg", "X-Media-Url": "https://x/a.mp3"})


@pytest.mark.unit
async def test_image_component_runs_in_a_flow() -> None:
    chat_input = ChatInput()
    chat_input.set(input_value="a red fox")
    image = GenMagicImageGenerationComponent()
    image.set(api_key=API_KEY, prompt=chat_input.message_response)
    chat_output = ChatOutput()
    chat_output.set(input_value=image.build_image)
    graph = Graph(chat_input, chat_output)

    with patch("httpx.Client.request", return_value=_image_reply()) as request:
        results = [result async for result in graph.async_start()]

    assert request.call_count == 1
    assert request.call_args.kwargs["json"]["prompt"] == "a red fox"
    built = [result for result in results if hasattr(result, "result_dict")]
    final = built[-1].result_dict.results["message"]
    assert final.text == f"![a red fox]({IMAGE_URL})"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("component_class", "values", "reply", "outputs"),
    [
        (GenMagicImageGenerationComponent, {"prompt": "a red fox"}, _image_reply, {"image", "image_url", "result"}),
        (GenMagicTextToSpeechComponent, {"text": "Hello."}, _speech_reply, {"audio_url", "result"}),
    ],
    ids=["image", "speech"],
)
async def test_building_every_output_makes_one_paid_request(component_class, values, reply, outputs) -> None:
    component = component_class()
    component.set(api_key=API_KEY, **values)

    with patch("httpx.Client.request", return_value=reply()) as request:
        results, _ = await component._build_results()

    assert request.call_count == 1
    assert outputs <= set(results)


@pytest.mark.unit
async def test_building_every_video_output_starts_one_job() -> None:
    created = response(202, json_body={"id": "vid_1", "status": "queued"})
    done = response(json_body={"id": "vid_1", "status": "completed", "url": VIDEO_URL})
    component = GenMagicVideoGenerationComponent()
    component.set(api_key=API_KEY, prompt="waves")

    with patch("httpx.Client.request", side_effect=[created, done]) as request, patch("time.sleep"):
        results, _ = await component._build_results()

    assert [call.args[0] for call in request.call_args_list] == ["POST", "GET"]
    assert {"video_url", "result"} <= set(results)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("component_class", "argument", "reply"),
    [
        (GenMagicImageGenerationComponent, "prompt", _image_reply),
        (GenMagicTextToSpeechComponent, "text", _speech_reply),
    ],
    ids=["image", "speech"],
)
async def test_an_agent_gets_one_tool_that_takes_only_the_prompt(component_class, argument, reply) -> None:
    component = component_class()
    component.set(api_key=API_KEY)

    tools = await component.to_toolkit()

    assert len(tools) == 1
    assert set(tools[0].args_schema.model_json_schema()["properties"]) == {argument}
    with patch("httpx.Client.request", return_value=reply()) as request:
        output: Any = await tools[0].ainvoke({argument: "something new"})

    assert request.call_count == 1
    assert output
