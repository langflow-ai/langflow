"""End-to-end coverage for the assistant_report.txt fixes.

These exercise the REAL pipeline (real TranslationFlow / FlowBuilder agent
LLM calls via the OPENAI_API_KEY loaded from the repo .env, and the real
component registry / runtime validation — no mocks) so each item the QA
report raised is proven against the actual system, not a stubbed one.

Run: ``uv run pytest tests/unit/agentic/test_assistant_report_e2e.py``
(LLM classes skip automatically when no key is available).

Report → scenario map:
  #1/#4 hallucination / fake success ........ TestNoFakeSuccessRealAgent
  #3/#4/#8 follow-up routing ................ TestIntentRoutingRealLLM
  #7 false off-topic / language ............. TestIntentRoutingRealLLM
  #2 invalid component passes ............... TestRuntimeValidationReal
  #6 legacy components ...................... TestLegacyFilterReal
  #3 user component usable in build ......... TestUserComponentOverlayReal
"""

from __future__ import annotations

import pytest
from langflow.agentic.services.conversation_buffer import ConversationTurn
from langflow.agentic.services.helpers.intent_classification import classify_intent
from langflow.agentic.services.helpers.intent_context import build_intent_context

from tests.api_keys import has_api_key

_OPENAI = pytest.mark.skipif(
    not has_api_key("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY required for real-LLM e2e",
)
_PROVIDER = "OpenAI"
_MODEL = "gpt-4o-mini"
_KEY = "OPENAI_API_KEY"


@_OPENAI
class TestIntentRoutingRealLLM:
    """RC-1 — real TranslationFlow routes follow-ups correctly given session/canvas context (report #3/#4/#7/#8)."""

    async def test_followup_add_agent_with_context_routes_to_build_flow(self):
        # Foto 7/8: prior build turn + "add a second agent" must act, not chat.
        context = build_intent_context(
            turns=[ConversationTurn(user="build a chatbot with an agent", assistant="Built it.")],
            canvas_summary="nodes: ChatInput-a1, Agent-b2, ChatOutput-c3",
        )
        result = await classify_intent(
            text="adicione um segundo agente para avaliar a resposta do primeiro",
            global_variables={},
            provider=_PROVIDER,
            model_name=_MODEL,
            api_key_var=_KEY,
            context=context,
        )
        assert result.intent == "build_flow", f"expected build_flow, got {result.intent}"

    async def test_pt_canvas_question_is_not_false_off_topic(self):
        # Foto 3: "você não consegue add esse componente no canva?" was wrongly
        # refused as off_topic. With canvas context it must NOT be off_topic.
        context = build_intent_context(
            turns=[ConversationTurn(user="crie um componente que soma a e b", assistant="Done, SumComponent.")],
            canvas_summary="nodes: Agent-1",
        )
        result = await classify_intent(
            text="você não consegue adicionar esse componente no canvas?",
            global_variables={},
            provider=_PROVIDER,
            model_name=_MODEL,
            api_key_var=_KEY,
            context=context,
        )
        assert result.intent != "off_topic", f"Langflow-related request misrouted to off_topic ({result.intent})"

    async def test_genuinely_off_topic_still_off_topic(self):
        # Guard: the WS-1 changes must not over-correct real off-topic asks.
        result = await classify_intent(
            text="como funciona o n8n?",
            global_variables={},
            provider=_PROVIDER,
            model_name=_MODEL,
            api_key_var=_KEY,
        )
        assert result.intent == "off_topic", f"expected off_topic, got {result.intent}"

    async def test_fresh_build_request_routes_to_build_flow(self):
        result = await classify_intent(
            text="monte um flow com ChatInput conectado a um Agent e um ChatOutput",
            global_variables={},
            provider=_PROVIDER,
            model_name=_MODEL,
            api_key_var=_KEY,
        )
        assert result.intent == "build_flow", f"expected build_flow, got {result.intent}"


@_OPENAI
class TestNoFakeSuccessRealAgent:
    """RC-2 — a real build_flow run drives the canvas or errors loudly, never a silent text complete (report #1/#4)."""

    async def test_real_build_emits_flow_activity_not_silent_text(self):
        from langflow.agentic.services.assistant_service import (
            execute_flow_with_validation_streaming,
        )

        events: list[str] = [
            line
            async for line in execute_flow_with_validation_streaming(
                flow_filename="flow_builder_assistant.py",
                input_value="build a simple flow: ChatInput connected to an Agent connected to ChatOutput",
                global_variables={},
                max_retries=1,
                user_id="e2e-user",
                session_id="agentic_e2e_nofake",
                provider=_PROVIDER,
                model_name=_MODEL,
                api_key_var=_KEY,
            )
        ]

        blob = "\n".join(events)
        acted = any(
            tok in blob
            for tok in ('"event": "flow_update"', '"event": "flow_preview"', "propose_plan", "flow_proposal_ready")
        )
        errored = '"event": "error"' in blob
        # The structural guarantee: a build either acts on the canvas or
        # fails loudly — never a silent text-only "complete".
        assert acted or errored, (
            "build_flow run produced neither canvas activity nor an explicit error "
            f"(the fake-success bug). Events: {blob[:1500]}"
        )
        if not acted:
            assert errored


class TestLegacyFilterReal:
    """RC-5 — real index: search hides LEGACY (not beta); describe still resolves it (report #6).

    Spec change (2026-05-18): beta components are allowed in search; only
    legacy is hidden.
    """

    def test_real_registry_search_excludes_legacy_but_describe_resolves(self):
        from lfx.graph.flow_builder.builder import load_local_registry
        from lfx.mcp.registry import describe_component, search_registry

        registry = load_local_registry()
        # Strictly legacy (and NOT beta-only) — beta is now allowed in search.
        legacy_name = next(
            (n for n, t in registry.items() if t.get("legacy")),
            None,
        )
        assert legacy_name is not None, "expected at least one legacy type in the real index"

        search_names = {r["type"] for r in search_registry(registry)}
        assert legacy_name not in search_names, f"{legacy_name} (legacy) leaked into default search"

        # Non-legacy staples are still discoverable.
        assert any(n in search_names for n in ("ChatInput", "ChatOutput", "Agent"))

        described = describe_component(registry, legacy_name)
        assert described["type"] == legacy_name
        assert described.get("legacy") is True

    def test_real_registry_search_includes_beta(self):
        from lfx.graph.flow_builder.builder import load_local_registry
        from lfx.mcp.registry import search_registry

        registry = load_local_registry()
        beta_name = next(
            (n for n, t in registry.items() if t.get("beta") and not t.get("legacy")),
            None,
        )
        if beta_name is None:
            pytest.skip("no beta-only component in the real index to assert on")
        search_names = {r["type"] for r in search_registry(registry)}
        assert beta_name in search_names, f"beta component {beta_name} must be visible in search"


class TestRuntimeValidationReal:
    """RC-4 — real runtime validation rejects the screenshot-4 bug class and accepts valid components (report #2)."""

    async def test_rejects_output_returning_non_dict_from_input(self):
        from textwrap import dedent

        from langflow.agentic.helpers.validation import validate_component_runtime

        buggy = dedent(
            """
            from lfx.custom import Component
            from lfx.io import MessageTextInput, Output
            from lfx.schema.data import Data


            class AnimalOnomatopoeia(Component):
                display_name = "Animal Onomatopoeia"
                description = "Generates an animal sound"

                inputs = [MessageTextInput(name="animal_name", display_name="Animal Name", required=True)]
                outputs = [Output(display_name="Sound", name="sound", method="make")]

                def make(self) -> Data:
                    return Data(data=self.animal_name[:3])
            """
        ).strip()
        assert await validate_component_runtime(buggy) is not None

    async def test_accepts_valid_component(self):
        from textwrap import dedent

        from langflow.agentic.helpers.validation import validate_component_runtime

        good = dedent(
            """
            from lfx.custom import Component
            from lfx.io import MessageTextInput, Output
            from lfx.schema.data import Data


            class AnimalEcho(Component):
                display_name = "Animal Echo"
                description = "Echoes the animal name in a Data dict"

                inputs = [MessageTextInput(name="animal_name", display_name="Animal Name", required=True)]
                outputs = [Output(display_name="Out", name="out", method="make")]

                def make(self) -> Data:
                    return Data(data={"animal": self.animal_name})
            """
        ).strip()
        assert await validate_component_runtime(good) is None


class TestUserComponentOverlayReal:
    """RC-3 — real register then real overlay lookup makes a user component usable in a later build (report #3)."""

    def test_registered_component_is_discoverable_by_class_name(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LANGFLOW_FS_TOOL_BASE_DIR", str(tmp_path))
        from langflow.agentic.services.user_components import register_user_component
        from langflow.agentic.services.user_components_overlay import (
            load_registry_with_user_overlay,
        )

        code = (
            "from lfx.custom import Component\n"
            "from lfx.io import Output\n"
            "from lfx.schema.data import Data\n\n\n"
            "class SumComponent(Component):\n"
            "    display_name = 'Sum'\n"
            "    description = 'adds a and b'\n"
            "    inputs = []\n"
            "    outputs = [Output(name='result', display_name='Result', method='run')]\n\n"
            "    def run(self) -> Data:\n"
            "        return Data(data={'result': 3})\n"
        )
        register_user_component(user_id="alice", class_name="SumComponent", code=code)

        merged = load_registry_with_user_overlay(user_id="alice")
        assert "SumComponent" in merged, "user component not visible to build_flow registry overlay"

        # Built-in collision safety: a user component named like a builtin
        # must not shadow it (base wins) — the overlay must still expose the
        # native ChatInput, not the user file.
        register_user_component(user_id="alice", class_name="ChatInput", code=code)
        merged2 = load_registry_with_user_overlay(user_id="alice")
        assert "ChatInput" in merged2
        assert "code" not in str(merged2["ChatInput"].get("display_name", "")), (
            "user component must not shadow the builtin ChatInput"
        )
        # NOTE: per-user cross-tenant isolation is environment-dependent
        # (AUTO_LOGIN=true uses a shared sandbox) and is covered by the
        # dedicated authenticated suites: test_user_components_overlay.py /
        # test_user_components_threading.py.


@_OPENAI
class TestCompoundIntentMultilingualRealLLM:
    """Language-agnostic proof for the compound intent.

    A compound 'create a component THEN build & run a flow with it'
    request classifies as ``component_then_flow`` in ANY language (the
    TranslationFlow translates to English first, so the prompt's EN/PT
    examples are illustrative, not a language whitelist).
    """

    @pytest.mark.parametrize(
        "phrase",
        [
            # English
            "create a component that checks if a number is prime, then build a "
            "flow with it, clear the canvas and run it with 14",
            # Portuguese (the original report)
            "crie um componente que dado um numero diga se ele é primo, depois "
            "crie um flow com esse componente, limpe o canvas e rode com 14",
            # Spanish
            "crea un componente que diga si un número es primo, luego arma un "
            "flujo con él, limpia el lienzo y ejecútalo con 14",
            # French
            "crée un composant qui dit si un nombre est premier, puis construis "
            "un flux avec, vide le canevas et exécute-le avec 14",
            # German
            "erstelle eine Komponente, die prüft ob eine Zahl eine Primzahl "
            "ist, baue dann einen Flow damit und führe ihn mit 14 aus",
        ],
    )
    async def test_compound_request_is_language_agnostic(self, phrase):
        result = await classify_intent(
            text=phrase,
            global_variables={},
            provider=_PROVIDER,
            model_name=_MODEL,
            api_key_var=_KEY,
        )
        assert result.intent == "component_then_flow", f"{phrase!r} → {result.intent}"


@_OPENAI
class TestRunFlowIntentRealLLM:
    """Bugfix proof — run requests route to run_flow (deterministic), build still via the real LLM."""

    async def test_run_request_is_classified_run_flow(self):
        result = await classify_intent(
            text="rode o flow e me diga o resultado",
            global_variables={},
            provider=_PROVIDER,
            model_name=_MODEL,
            api_key_var=_KEY,
        )
        assert result.intent == "run_flow", f"expected run_flow, got {result.intent}"

    async def test_english_run_request_is_classified_run_flow(self):
        result = await classify_intent(
            text="run the flow and tell me the output",
            global_variables={},
            provider=_PROVIDER,
            model_name=_MODEL,
            api_key_var=_KEY,
        )
        assert result.intent == "run_flow", f"expected run_flow, got {result.intent}"

    async def test_edit_continuation_signal_routes_as_flow_request(self):
        # The "execution stack" depends on the edit-approval continuation
        # reaching the flow-builder assistant (a flow request) — never
        # off_topic/question, which would strand the deferred run. Stable
        # invariant: classified as a flow request even through the real
        # provider entrypoint (it's a deterministic short-circuit).
        from langflow.agentic.services.flow_types import EDIT_CONTINUATION_INPUT

        result = await classify_intent(
            text=EDIT_CONTINUATION_INPUT,
            global_variables={},
            provider=_PROVIDER,
            model_name=_MODEL,
            api_key_var=_KEY,
        )
        assert result.intent == "build_flow", f"continuation must be a flow request, got {result.intent}"

    async def test_build_request_is_not_swallowed_by_run_flow(self):
        # The new run_flow intent must NOT over-capture a build request.
        # (We assert the stable invariant — NOT run_flow — rather than exact
        # build_flow, which is genuinely flaky on a real LLM and not the
        # contract this bugfix is about.)
        result = await classify_intent(
            text="build me a chatbot flow with an agent",
            global_variables={},
            provider=_PROVIDER,
            model_name=_MODEL,
            api_key_var=_KEY,
        )
        assert result.intent != "run_flow", f"build request wrongly captured as run_flow ({result.intent})"


class TestRealEngineRunReturnsResult:
    """Bugfix proof — the REAL run engine executes a flow and returns its result.

    Refutes the production symptom: result not shown / "I couldn't apply
    that change to the canvas".
    """

    async def test_real_minimal_flow_runs_and_returns_result(self):
        import uuid

        from langflow.agentic.services.flow_run import run_working_flow
        from lfx.graph.flow_builder.builder import build_flow_from_spec, load_local_registry

        spec = (
            "name: Echo\n"
            "nodes:\n"
            "  A: ChatInput\n"
            "  B: ChatOutput\n"
            "edges:\n"
            "  A.message -> B.input_value\n"
            "config:\n"
            "  A.input_value: hello-run-42\n"
            # Disable DB persistence so the test is independent of
            # session_scope availability. The build path on ChatInput /
            # ChatOutput calls ``self.send_message`` which writes to the
            # message store when ``should_store_message=true`` (default);
            # in batched suites that DB context may be torn down by a
            # prior test, surfacing as
            # ``"Error building Component Chat Input"``. The intent of
            # this test is to verify ``run_working_flow`` actually runs
            # and returns the flow's output — message persistence is
            # unrelated to that contract.
            "  A.should_store_message: false\n"
            "  B.should_store_message: false\n"
        )
        built = build_flow_from_spec(spec, load_local_registry())
        assert "error" not in built, f"failed to build the test flow: {built}"
        # build_flow_from_spec → {"flow": {"name","data":{nodes,edges}}, ...};
        # built["flow"] is exactly the production working-flow shape that
        # _ensure_working_flow() returns ({"name","data":{nodes,edges}}).
        working_flow = built["flow"]

        out = await run_working_flow(
            flow_data=working_flow,
            flow_id=str(uuid.uuid4()),  # the run engine requires a valid UUID
            user_id=None,
        )

        # The real engine ran and returned the flow's actual output (not the
        # no-action error envelope) — the agent can discuss this result.
        assert "error" not in out, f"real run errored: {out}"
        assert "result" in out
        assert "hello-run-42" in out["result"], f"ChatOutput should echo the input, got: {out['result']!r}"

        # The real engine also surfaces run metrics so the agent can report
        # how the run performed. duration_seconds is the MEASURED wall time of
        # the real run — it must be > 0 (the production bug reported it as
        # "0,0s" because it was read from ResultData.timedelta, which the
        # engine never populates on the returned output vertices). A trivial
        # ChatInput→ChatOutput flow uses no LLM, so 0 total tokens is correct.
        metrics = out["metrics"]
        assert set(metrics) == {"duration_seconds", "input_tokens", "output_tokens", "total_tokens"}
        assert isinstance(metrics["duration_seconds"], float)
        assert metrics["duration_seconds"] > 0.0, f"real run must have measurable time, got {metrics}"
        assert metrics["total_tokens"] == 0
