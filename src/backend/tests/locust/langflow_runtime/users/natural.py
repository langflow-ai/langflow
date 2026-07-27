"""Natural suite Locust user — uniform random pick among starter-derived shapes."""

from __future__ import annotations

import random

from locust import task

from tests.locust.langflow_runtime.flows.defaults import DEFAULT_KB_QUERY, DEFAULT_OUTBOUND_PROMPT
from tests.locust.langflow_runtime.users.base import PerfBaseUser
from tests.locust.langflow_runtime.users.natural_correctness import check_natural_correctness

NATURAL_SHAPES = (
    "basic_prompting",
    "simple_agent",
    "memory_chatbot",
    "vector_store_rag",
    "file_parser_agent",
)


class NaturalUser(PerfBaseUser):
    """Pick one Natural fixture uniformly at random each task."""

    weight = 1
    workload_name = "natural"
    flow_class = "natural"

    def on_start(self) -> None:
        super().on_start()
        # Assign stable per-environment ordinals so paired stubbed/live runs with
        # the same seed and population select the same shape sequences.
        user_idx = int(getattr(self.environment, "natural_user_counter", 0))
        self.environment.natural_user_counter = user_idx + 1
        overrides = getattr(self.run_context, "overrides", {}) if self.run_context is not None else {}
        seed = int((overrides or {}).get("seed", 0))
        self._rng = random.Random(f"{seed}:{user_idx}")  # noqa: S311

    def _external_apis(self) -> str:
        if self.run_context is None:
            return "stubbed"
        overrides = getattr(self.run_context, "overrides", {}) or {}
        if overrides.get("external_apis") in {"stubbed", "live"}:
            return str(overrides["external_apis"])
        return getattr(self.run_context.profile, "external_apis", None) or "stubbed"

    def _fixture_id(self, shape: str) -> str:
        return f"natural_{shape}__external_{self._external_apis()}"

    def _input_for(self, shape: str) -> str:
        if shape == "vector_store_rag":
            return DEFAULT_KB_QUERY
        if shape == "file_parser_agent":
            return "perf-natural-file"
        return DEFAULT_OUTBOUND_PROMPT

    def _fire_correctness(self, name: str, exc: Exception | None) -> None:
        self.environment.events.request.fire(
            request_type="CORRECTNESS",
            name=name,
            response_time=0,
            response_length=0,
            exception=exc,
            context={},
        )

    def _check_correctness(self, shape: str, fixture_id: str, result: object) -> None:
        check_natural_correctness(
            shape=shape,
            fixture_id=fixture_id,
            result=result,
            external_apis=self._external_apis(),
            fire=self._fire_correctness,
        )

    @task
    def natural_step(self) -> None:
        if self.run_context is None or self.stop_new_arrivals():
            return
        shape = self._rng.choice(NATURAL_SHAPES)
        fixture_id = self._fixture_id(shape)
        flow = self.require_flow_or_fail(fixture_id)
        workflows = self.require_workflows_client(workload="natural", flow_class=shape)
        result = workflows.run_sync(
            flow_id=str(flow["flow_id"]),
            input_value=self._input_for(shape),
            session_id=self.session_id,
        )
        self._check_correctness(shape, fixture_id, result)
