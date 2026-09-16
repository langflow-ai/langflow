"""A branch stopped by ``Component.stop()`` stays stopped while a sibling completes (#14966).

The /build driver runs sibling vertices concurrently and, after every vertex completes, used
to reset the graph-wide ``inactivated_vertices`` set. When one component had called
``self.stop()`` and was still running, an unrelated sibling finishing first reactivated the
stopped branch, and the stopped vertex then ran with the blocked output's value.

The components below make the interleaving deterministic instead of relying on sleeps:
the sibling finishes only after the stop is in place, and the stopper returns only after the
sibling's completion (and its reset) has run.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from httpx import codes
from lfx.custom.eval import eval_custom_component_code
from lfx.graph.graph.base import Graph

from tests.unit.build_utils import build_flow, create_flow, get_build_events

START_ID = "RaceStart-a1b2c"
STOPPER_ID = "RaceStopper-d3e4f"
TRIGGER_ID = "RaceTrigger-g5h6i"
VICTIM_ID = "RaceVictim-j7k8l"
GOAL_ID = "RaceGoal-m9n0p"

START_CODE = """
from lfx.custom.custom_component.component import Component
from lfx.io import Output
from lfx.schema.data import Data


class RaceStart(Component):
    display_name = "Race Start"
    outputs = [Output(name="start", display_name="Start", method="emit")]

    def emit(self) -> Data:
        return Data(data={"start": True})
"""

STOPPER_CODE = f"""
import asyncio

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, Output
from lfx.schema.data import Data


class RaceStopper(Component):
    display_name = "Race Stopper"
    inputs = [DataInput(name="start", display_name="Start")]
    outputs = [
        Output(name="blocked", display_name="Blocked", method="blocked_output", group_outputs=True),
        Output(name="done", display_name="Done", method="done_output", group_outputs=True),
    ]

    def blocked_output(self) -> Data:
        return Data(data={{"stopped_branch_value": True}})

    async def done_output(self) -> Data:
        self.stop("blocked")
        # Stay running until the sibling has completed; its completion path is what used to
        # reset every inactivated vertex in the graph.
        for _ in range(200):
            if "{TRIGGER_ID}" in self.graph.run_manager.ran_at_least_once:
                break
            await asyncio.sleep(0.05)
        await asyncio.sleep(0.5)
        return Data(data={{"stopper_done": True}})
"""

TRIGGER_CODE = f"""
import asyncio

from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, Output
from lfx.schema.data import Data


class RaceTrigger(Component):
    display_name = "Race Trigger"
    inputs = [DataInput(name="start", display_name="Start")]
    outputs = [Output(name="trigger", display_name="Trigger", method="emit")]

    async def emit(self) -> Data:
        # Complete only once the stopper's stop is in place.
        for _ in range(200):
            if "{VICTIM_ID}" in self.graph.inactivated_vertices:
                break
            await asyncio.sleep(0.05)
        return Data(data={{"trigger_done": True}})
"""

VICTIM_CODE = """
from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, Output
from lfx.schema.data import Data


class RaceVictim(Component):
    display_name = "Race Victim"
    inputs = [DataInput(name="value", display_name="Value")]
    outputs = [Output(name="result", display_name="Result", method="run")]

    def run(self) -> Data:
        msg = "a branch stopped by Component.stop() was executed"
        raise ValueError(msg)
"""

GOAL_CODE = """
from lfx.custom.custom_component.component import Component
from lfx.io import DataInput, Output
from lfx.schema.data import Data


class RaceGoal(Component):
    display_name = "Race Goal"
    inputs = [
        DataInput(name="stopper_done", display_name="Stopper Done"),
        DataInput(name="trigger_done", display_name="Trigger Done"),
    ]
    outputs = [Output(name="result", display_name="Result", method="run")]

    def run(self) -> Data:
        return Data(data={"goal": True})
"""


@pytest.fixture(autouse=True)
def allow_custom_components(monkeypatch):
    monkeypatch.setenv("LANGFLOW_ALLOW_CUSTOM_COMPONENTS", "true")


def _race_flow() -> str:
    graph = Graph()
    for vertex_id, code in (
        (START_ID, START_CODE),
        (STOPPER_ID, STOPPER_CODE),
        (TRIGGER_ID, TRIGGER_CODE),
        (VICTIM_ID, VICTIM_CODE),
        (GOAL_ID, GOAL_CODE),
    ):
        component = eval_custom_component_code(code)(_id=vertex_id, _code=code)
        graph.add_component(component, vertex_id)
    graph.add_component_edge(START_ID, ("start", "start"), STOPPER_ID)
    graph.add_component_edge(START_ID, ("start", "start"), TRIGGER_ID)
    graph.add_component_edge(STOPPER_ID, ("blocked", "value"), VICTIM_ID)
    graph.add_component_edge(STOPPER_ID, ("done", "stopper_done"), GOAL_ID)
    graph.add_component_edge(TRIGGER_ID, ("trigger", "trigger_done"), GOAL_ID)
    graph.prepare()
    return json.dumps(graph.dump(name="Stopped branch race"))


async def _end_vertex_events(response) -> list[dict]:
    async def collect() -> list[dict]:
        events = []
        async for line in response.aiter_lines():
            if line:
                event = json.loads(line)
                if event.get("event") == "end_vertex":
                    events.append(event["data"]["build_data"])
        return events

    return await asyncio.wait_for(collect(), timeout=30)


async def test_sibling_completion_does_not_reactivate_a_stopped_branch(client, logged_in_headers):
    flow_id = await create_flow(client, _race_flow(), logged_in_headers)
    job_id = (await build_flow(client, flow_id, logged_in_headers))["job_id"]
    response = await get_build_events(client, job_id, logged_in_headers)
    assert response.status_code == codes.OK

    built = await _end_vertex_events(response)
    built_by_id = {build_data["id"]: build_data for build_data in built}

    assert VICTIM_ID not in built_by_id, "the stopped branch was reactivated and executed"
    assert VICTIM_ID in built_by_id[STOPPER_ID]["inactivated_vertices"]
    assert built_by_id[GOAL_ID]["valid"]
