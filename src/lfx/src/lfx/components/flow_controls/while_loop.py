"""While Loop component: runs a loop body on a state until the body returns an answer.

The state is a DataFrame of message rows (`lfx.base.agents.loop_rows`). Each iteration hands the state to the body
through the `loop` output, and the rows the body feeds back to the `loop` input are the new state. The body runs
through the same single-iteration runner as Loop (`run_loop_iteration`).

Flow pattern (agent example):
history rows -> WhileLoop.initial_state, the current message -> WhileLoop.input_value
WhileLoop.loop -> model call (the history plus the model's message)
               -> tool calls (that history plus the tool results) -> WhileLoop.loop (feedback)
WhileLoop.last_message -> the answer
"""

from __future__ import annotations

import json
import math
from typing import Any

from langchain_core.messages import AIMessage, message_to_dict

from lfx.base.agents.loop_rows import HARNESS_LOOP_KEY, LC_MESSAGE, is_answer, messages_to_rows, row_to_message
from lfx.base.flow_controls.loop_utils import (
    get_loop_body_start_edge,
    get_loop_body_vertices,
    resolve_item_injections,
    run_loop_iteration,
)
from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import HandleInput, IntInput
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message
from lfx.template.field.base import Output


def _json_rows(df: DataFrame) -> list[dict]:
    """The rows of `df` as plain JSON values, floats unchanged, so the body's node data can be checkpointed.

    A missing cell (NaN) becomes None.
    """
    rows = [
        {key: None if isinstance(value, float) and math.isnan(value) else value for key, value in row.items()}
        for row in df.to_dict(orient="records")
    ]
    return json.loads(json.dumps(rows, default=str))


class WhileLoopComponent(Component):
    """Runs the loop body on the state until it ends, and returns the final state.

    The rows the body feeds back to `loop` replace the state. The loop ends when they end in an answer (an AI
    message that asks for no tools), when the harness runtime in the graph context has stopped (a middleware ended
    the run, or a `return_direct` tool ran), or when the body feeds nothing back (its branch to `loop` stopped).

    `max_iterations` is a safety cap of at least 1. Under a harness, reaching it ends the state with the limit message
    the Agent's own limit gives, so the Agent finishes its run. Without one it raises instead of returning a state
    that holds no answer, so a consumer never takes an earlier turn's answer for this one.
    """

    display_name = "While Loop"
    description = "Executes loop body repeatedly with state accumulation until termination."
    icon = "repeat"

    inputs = [
        HandleInput(
            name="initial_state",
            display_name="Initial State",
            info="Optional base state (DataFrame) to prepend to input_value. For agents, connect MessageHistory here.",
            input_types=["DataFrame"],
            required=False,
        ),
        HandleInput(
            name="input_value",
            display_name="Input",
            info="The input for the first iteration. Combined with initial_state.",
            input_types=["DataFrame", "Data", "Message"],
        ),
        IntInput(
            name="max_iterations",
            display_name="Max Iterations",
            info="Maximum number of iterations to prevent infinite loops.",
            value=10,
            required=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Loop",
            name="loop",
            method="loop_output",
            allows_loop=True,
            loop_types=["DataFrame"],
            info="Connect to the loop body. Receives the new state from the end of the body.",
            group_outputs=True,
        ),
        Output(
            display_name="Done",
            name="done",
            method="done_output",
            info="Outputs the final state when the loop ends.",
            group_outputs=True,
        ),
        Output(
            display_name="Last Message",
            name="last_message",
            method="last_message_output",
            info="The last row of the final state as a Message. Uses the same run as Done.",
            group_outputs=True,
        ),
    ]

    def _to_dataframe(self, value: Any) -> DataFrame:
        """Convert input value to DataFrame. A Message becomes one message row, its files included."""
        if value is None:
            return DataFrame([])
        if isinstance(value, DataFrame):
            return value
        if isinstance(value, list):
            return DataFrame(value)
        if isinstance(value, Message):
            return DataFrame(messages_to_rows([value.to_lc_message()]))
        if isinstance(value, Data):
            return DataFrame([value])
        if isinstance(value, dict):
            return DataFrame([Data(data=value)])
        return DataFrame([Data(text=str(value))])

    def get_loop_body_vertices(self) -> set[str]:
        """Vertices between this loop's `loop` output and the vertex that feeds back into `loop`."""
        if self._vertex is None:
            return set()
        return get_loop_body_vertices(
            vertex=self._vertex,
            graph=self.graph,
            get_incoming_edge_by_target_param_fn=self.get_incoming_edge_by_target_param,
            loop_output_name="loop",
            feedback_input_name="loop",
        )

    def _build_initial_state(self) -> DataFrame:
        """The `initial_state` rows (history), then the `input_value` rows (current input)."""
        input_df = self._to_dataframe(self.input_value)
        if isinstance(self.initial_state, DataFrame) and not self.initial_state.empty:
            return self.initial_state.add_rows(input_df.to_dict(orient="records"))
        return input_df

    def _fed_back(self, results: list) -> DataFrame | None:
        """The value of the output wired to the `loop` input, or None when the body did not build it."""
        edge = next(edge for edge in self._vertex.incoming_edges if edge.target_param == "loop")
        for result in results:
            vertex = getattr(result, "vertex", None)  # the stream ends with a marker that has none
            if vertex is not None and vertex.id == edge.source_id:
                value = vertex.results.get(edge.source_handle.name)
                return None if value is None else self._to_dataframe(value)
        return None

    def _ended(self, rows: list[dict]) -> bool:
        runtime = self.ctx.get(HARNESS_LOOP_KEY)
        return (runtime is not None and runtime.stopped) or (bool(rows) and is_answer(row_to_message(rows[-1])))

    def _pre_run_setup(self):
        super()._pre_run_setup()
        self._final_state = None

    async def _iterate(self) -> DataFrame:
        """Run the loop to its end once. Every output of this build reads that run."""
        if getattr(self, "_final_state", None) is None:
            self._final_state = DataFrame(await self._run_iterations())
        return self._final_state

    async def _run_iterations(self) -> list[dict]:
        rows = _json_rows(self._build_initial_state())
        body_ids = self.get_loop_body_vertices()
        if not body_ids:
            return rows
        start_edge = get_loop_body_start_edge(self._vertex, loop_output_name="loop")
        injections, list_sources = resolve_item_injections(self.graph, body_ids, start_edge.target_id, start_edge)
        limit = max(1, int(self.max_iterations))
        for _ in range(limit):
            results = await run_loop_iteration(
                self.graph,
                DataFrame(rows),
                body_ids,
                injections,
                list_sources,
                self._event_manager,
                user_id=self.user_id,
                node_value=rows,
            )
            fed_back = self._fed_back(results)
            if fed_back is None:
                return rows
            rows = _json_rows(fed_back)
            if self._ended(rows):
                return rows
        if self.ctx.get(HARNESS_LOOP_KEY) is None:
            msg = (
                f"While Loop reached max_iterations ({limit}) while the loop body was still feeding back. "
                "Raise Max Iterations, or check why the body does not stop."
            )
            raise RuntimeError(msg)
        # The text ModelCallLimitMiddleware ends an Agent's run with when it reaches the same limit.
        limit_message = AIMessage(content=f"Model call limits exceeded: run limit ({limit}/{limit})")
        return [*rows, *messages_to_rows([limit_message])]

    async def loop_output(self) -> DataFrame:
        """Stop the `loop` branch, because the body runs inside `_iterate`, not in the outer graph.

        Like Loop's `item`, this also runs the iteration, so it runs when nothing reads the other outputs.
        """
        self.stop("loop")
        await self._iterate()
        return self._build_initial_state()

    async def done_output(self) -> DataFrame:
        """Run the loop (once) and return the final state."""
        return await self._iterate()

    async def last_message_output(self) -> Message:
        """The last row of the final state: its text, and the whole LangChain message in `data`."""
        rows = (await self._iterate()).to_dict(orient="records")
        if not rows:
            return Message(text="")
        last = row_to_message(rows[-1])
        message = Message(text=last.text)
        message.data[LC_MESSAGE] = message_to_dict(last)
        return message
