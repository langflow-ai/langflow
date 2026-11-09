from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from lfx.base.models.decisions.schema import DecisionConfigurationError, DecisionEvaluationError, DecisionResult
from lfx.components.llm_operations.llm_conditional_router import SmartRouterComponent, assign_route_ids
from lfx.schema.dotdict import dotdict
from lfx.schema.message import Message
from lfx.schema.properties import Usage

from tests.base import ComponentTestBaseWithoutClient


def _rows(*route_ids):
    return [{"route_category": f"Route {i}", "route_id": route_id} for i, route_id in enumerate(route_ids)]


def _fresh_build_config(router):
    build_config = dotdict(router.to_frontend_node()["data"]["node"]["template"])
    build_config["routes"]["value"] = [{"route_category": name} for name in ("Billing", "Sales")]
    return build_config


def _decide(monkeypatch, kind, routes, result, **settings):
    """Route one message with ``result`` as the provider's answer; returns the label, evidence and request."""
    router, label, sent = _decided_router(monkeypatch, kind, routes, result, **settings)
    return label, router._decision_evidence, sent[0] if sent else None


def _decided_router(
    monkeypatch, kind, routes, result, *, minimum_probability=0.7, question="Is this a refund request?", **fields
):
    """The router after routing one message with ``result`` as the provider's answer, its label and requests."""
    sent = []

    def evaluate(request, **_kwargs):
        sent.append(request)
        return result

    monkeypatch.setattr("lfx.components.llm_operations.llm_conditional_router.evaluate_decision", evaluate)
    router = SmartRouterComponent()
    router.set(
        input_text="I was charged twice.",
        routes=routes,
        routing_mode="Decision Model",
        decision_model=[{"provider": "TypeSafe", "name": "jev-latest"}],
        decision_kind=kind,
        decision_question=question,
        minimum_probability=minimum_probability,
        evaluation_error_action="Route to Else",
        enable_else_output=True,
        **fields,
    )
    router._vertex = SimpleNamespace(
        outgoing_edges=[SimpleNamespace(source_handle=SimpleNamespace(name="default_result"))]
    )
    router.log = lambda *_args, **_kwargs: None
    label = router._get_categorization()
    return router, label, sent


def _boolean(probability_true):
    return DecisionResult(kind="boolean", provider="TypeSafe", model="jev-1.13.0", probability_true=probability_true)


def _choice_result(*probabilities):
    ids = [f"category_{i + 1}_result" for i in range(len(probabilities))]
    return DecisionResult(
        kind="choice", provider="TypeSafe", model="jev-1.13.0", probabilities=dict(zip(ids, probabilities, strict=True))
    )


def _score(*probabilities):
    ids = [f"category_{i + 1}_result" for i in range(len(probabilities))]
    score = sum(i * p for i, p in enumerate(probabilities))
    return DecisionResult(
        kind="score",
        provider="TypeSafe",
        model="jev-1.13.0",
        probabilities=dict(zip(ids, probabilities, strict=True)),
        score=score,
    )


LEVELS = [{"route_category": "Low"}, {"route_category": "Medium"}, {"route_category": "High"}]


class TestSmartRouterComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return SmartRouterComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "model": [
                {
                    "name": "gpt-4o",
                    "provider": "OpenAI",
                    "icon": "OpenAI",
                    "metadata": {
                        "model_class": "ChatOpenAI",
                        "model_name_param": "model",
                        "api_key_param": "api_key",  # pragma: allowlist secret
                    },
                }
            ],
            "input_text": "I love this product!",
            "routes": [
                {
                    "route_category": "Positive",
                    "route_description": "Positive feedback, satisfaction, or compliments",
                    "output_value": "",
                },
                {
                    "route_category": "Negative",
                    "route_description": "Complaints, issues, or dissatisfaction",
                    "output_value": "",
                },
            ],
            "enable_else_output": False,
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component doesn't have version-specific files."""
        return []

    async def component_setup(self, component_class, default_kwargs):
        component = await super().component_setup(component_class, default_kwargs)
        # Route outputs are dynamic: the frontend builds one per route.
        await self.map_frontend_outputs(component, "routes", default_kwargs["routes"])
        return component

    async def test_latest_version(self, component_class, default_kwargs, skipped_outputs):
        # Answer the classification prompt offline; the routing around it runs for real.
        fake_llm = FakeListChatModel(responses=["Positive"])
        with patch("lfx.components.llm_operations.llm_conditional_router.get_llm", return_value=fake_llm):
            await super().test_latest_version(component_class, default_kwargs, skipped_outputs)

    def _create_component_with_mock_categorization(self, categorization_result, *, enable_else=False):
        """Helper to create a component with a mocked categorization result."""
        component = SmartRouterComponent()
        component.routes = [
            {"route_category": "Positive", "route_description": "Good feedback", "output_value": ""},
            {"route_category": "Negative", "route_description": "Bad feedback", "output_value": ""},
        ]
        component.input_text = "Test input"
        component.enable_else_output = enable_else
        component.message = None
        component._categorization_result = categorization_result
        component.stop = MagicMock()
        return component

    def test_positive_output(self):
        """Test routing to positive category."""
        component = self._create_component_with_mock_categorization("Positive")

        result = component.process_case()

        assert isinstance(result, Message)
        assert result.text == "Test input"
        component.stop.assert_any_call("category_2_result")  # Negative should be stopped

    def test_negative_output(self):
        """Test routing to negative category."""
        component = self._create_component_with_mock_categorization("Negative")

        result = component.process_case()

        assert isinstance(result, Message)
        assert result.text == "Test input"
        component.stop.assert_any_call("category_1_result")  # Positive should be stopped

    def test_neutral_output_no_match(self):
        """Test when input doesn't match any category (no else output)."""
        component = self._create_component_with_mock_categorization("NONE", enable_else=False)

        result = component.process_case()

        assert isinstance(result, Message)
        assert result.text == ""
        assert component.status == "No match found and Else output is disabled"

    def test_else_output(self):
        """Test else output when no category matches."""
        component = self._create_component_with_mock_categorization("NONE", enable_else=True)

        result = component.default_response()

        assert isinstance(result, Message)
        assert result.text == "Test input"
        assert "Routed to Else (no match)" in component.status

    def test_categorization_caching(self):
        """Test that LLM categorization result is cached and only called once."""
        component = SmartRouterComponent()
        component.routes = [
            {"route_category": "Positive", "route_description": "", "output_value": ""},
        ]
        component.input_text = "Great product!"
        component.model = [{"name": "test-model", "provider": "Test"}]
        component._user_id = "test-user"
        component.api_key = "test-key"  # pragma: allowlist secret

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Positive"
        mock_llm.invoke.return_value = mock_response

        with patch("lfx.components.llm_operations.llm_conditional_router.get_llm", return_value=mock_llm):
            result1 = component._get_categorization()
            result2 = component._get_categorization()

        assert result1 == "Positive"
        assert result2 == "Positive"
        assert mock_llm.invoke.call_count == 1  # LLM only called once due to caching

    @pytest.mark.parametrize("value", [None, "", "  ", -0.1, 1.1, float("nan"), float("inf")])
    def test_decision_threshold_has_no_implicit_zero(self, value):
        component = SmartRouterComponent()
        component.set(minimum_probability=value)
        with pytest.raises(DecisionConfigurationError):
            component._validate_probability(component.minimum_probability)

    @pytest.mark.parametrize("value", [False, True])
    def test_decision_threshold_rejects_boolean(self, value):
        component = SmartRouterComponent()
        with pytest.raises(ValueError, match="not a Boolean"):
            component.set(minimum_probability=value)

    def test_decision_artifacts_mask_secrets_without_changing_message(self):
        component = SmartRouterComponent()
        component.set(api_key="private-secret")  # pragma: allowlist secret
        component._decision_evidence = {
            "reason": "evaluation_error",
            "error": {"category": "DecisionEvaluationError", "message": "Failed private-secret"},
        }
        message = Message(text="Original message")
        artifact = component._build_artifact(message)
        assert artifact["raw"]["message"] == "Original message"
        assert artifact["raw"]["decision"]["error"]["message"] == "Failed **********"
        assert artifact["type"] == "object"
        assert message.text == "Original message"

    def test_switching_mode_preserves_llm_configuration(self, monkeypatch):
        component = SmartRouterComponent()
        component.set(model=[{"provider": "Test", "name": "llm"}], custom_prompt="Use {routes} for {input_text}")
        config = {name: input_.model_dump() for name, input_ in component._inputs.items()}
        monkeypatch.setattr(
            "lfx.components.llm_operations.llm_conditional_router.handle_model_input_update",
            lambda _component, build_config, *_args, **_kwargs: build_config,
        )
        decision_config = component.update_build_config(config, "Decision Model", "routing_mode")
        assert decision_config["custom_prompt"]["value"] == "Use {routes} for {input_text}"
        assert decision_config["model"]["value"] == [{"provider": "Test", "name": "llm"}]
        assert not decision_config["api_key"]["show"]
        assert decision_config["minimum_probability"]["required"]
        llm_config = component.update_build_config(decision_config, "Language Model", "routing_mode")
        assert llm_config["custom_prompt"]["value"] == "Use {routes} for {input_text}"
        assert llm_config["custom_prompt"]["show"]
        assert llm_config["api_key"]["show"]
        assert not llm_config["minimum_probability"]["required"]

    def test_optional_float_threshold_roundtrip_preserves_blank_and_legacy_default(self):
        from lfx.inputs.inputs import FloatInput, instantiate_input

        for value in (None, "", "  "):
            threshold = FloatInput(name="minimum_probability", value=value, preserve_empty=True)
            serialized = threshold.to_dict()
            restored = instantiate_input(serialized.pop("_input_type"), serialized)
            assert restored.value is None
            restored.value = 0
            assert restored.value == 0
            restored.value = value
            assert restored.value is None
            assert FloatInput(name="legacy", value=value).value == 0

    @pytest.mark.parametrize(
        ("mode", "expected"), [("Decision Model", ("perplexity",)), ("Language Model", ("openai",))]
    )
    def test_provider_policy_only_checks_active_selection(self, mode, expected):
        component = SmartRouterComponent()
        parameters = {
            "routing_mode": mode,
            "model": [{"provider": "OpenAI", "name": "llm"}],
            "decision_model": [{"provider": "Perplexity", "name": "decider"}],
        }
        assert component._selected_model_provider_policy_ids(parameters) == expected
        assert "model" in parameters
        assert "decision_model" in parameters

    async def test_active_provider_denial_cannot_fall_back_to_else(self, monkeypatch):
        from lfx.services.model_provider_policy import ModelProviderPolicyPurpose

        component = SmartRouterComponent()
        component.set(
            routing_mode="Decision Model",
            model=[{"provider": "OpenAI", "name": "llm"}],
            decision_model=[{"provider": "Perplexity", "name": "decider"}],
            evaluation_error_action="Route to Else",
        )
        seen = []

        class Policy:
            def require(self, provider):
                seen.append(provider)
                msg = "Decision provider denied before credentials"
                raise PermissionError(msg)

        async def policy(**_kwargs):
            return Policy()

        monkeypatch.setattr("lfx.services.model_provider_policy.aresolve_model_provider_policy", policy)
        with pytest.raises(PermissionError, match="before credentials"):
            await component.arequire_model_provider_policy(ModelProviderPolicyPurpose.USE)
        assert seen == ["perplexity"]

    @pytest.mark.parametrize("field_name", [i.name for i in SmartRouterComponent.inputs if i.real_time_refresh])
    def test_every_field_refresh_keeps_the_route_outputs(self, field_name):
        """The update endpoint passes a node with no outputs; losing them drops every route edge in the editor."""
        router = SmartRouterComponent()
        router.set(
            routes=[{"route_category": "Billing"}, {"route_category": "Sales"}],
            enable_else_output=True,
            routing_mode="Decision Model",
        )
        node = router.update_outputs({"outputs": []}, field_name, getattr(router, field_name, None))
        assert [output.name for output in node["outputs"]] == [
            "category_1_result",
            "category_2_result",
            "default_result",
        ]

    @pytest.mark.parametrize(
        ("rows", "last_number", "expected", "expected_last"),
        [
            # A flow saved before route IDs keeps its positional handles.
            (_rows(None, None, None), 0, ["category_1_result", "category_2_result", "category_3_result"], 3),
            # Deleting the middle route leaves the others' outputs alone.
            (_rows("category_1_result", "category_3_result"), 3, ["category_1_result", "category_3_result"], 3),
            # Deleting the last route and adding one in the same save never reuses its name.
            (
                _rows("category_1_result", "category_2_result", None),
                3,
                ["category_1_result", "category_2_result", "category_4_result"],
                4,
            ),
            # A copied row gets its own output.
            (_rows("category_1_result", "category_1_result"), 1, ["category_1_result", "category_2_result"], 2),
            # Replacing every route still never reuses an old name.
            (_rows(None, None), 3, ["category_4_result", "category_5_result"], 5),
            # A malformed ID is replaced, not trusted.
            (_rows("category_1_result", "default_result"), 1, ["category_1_result", "category_2_result"], 2),
        ],
    )
    def test_assign_route_ids(self, rows, last_number, expected, expected_last):
        keyed, last = assign_route_ids(rows, last_number)
        assert [row["route_id"] for row in keyed] == expected
        assert last == expected_last
        assert assign_route_ids(keyed, last) == (keyed, last), "assignment must be stable"

    def test_editor_route_edits_keep_every_other_routes_output(self):
        """Replays the editor: a load refresh, then one save that deletes a route and adds another."""
        router = SmartRouterComponent()
        router.set(enable_else_output=True)
        build_config = dotdict(router.to_frontend_node()["data"]["node"]["template"])
        build_config["routes"]["value"] = [{"route_category": name} for name in ("Billing", "Sales", "Support")]
        build_config = router.update_build_config(build_config, None, "decision_model")

        billing, _sales, support = build_config["routes"]["value"]
        edited = [billing, support, {"route_category": "Accounts", "route_id": None}]
        build_config = router.update_build_config(build_config, edited, "routes")
        node = router.update_outputs({"outputs": [], "template": build_config}, "routes", edited)

        assert [(output.display_name, output.name) for output in node["outputs"]] == [
            ("Billing", "category_1_result"),
            ("Support", "category_3_result"),
            ("Accounts", "category_4_result"),
            ("Else", "default_result"),
        ]
        assert build_config["last_route_number"]["value"] == 4

    def test_switching_to_decision_mode_turns_else_on(self):
        router = SmartRouterComponent()
        build_config = router.update_build_config(_fresh_build_config(router), "Decision Model", "routing_mode")
        node = router.update_outputs({"outputs": [], "template": build_config}, "routing_mode", "Decision Model")

        assert build_config["enable_else_output"]["value"] is True
        assert build_config["enable_else_output"]["advanced"] is False
        assert [output.name for output in node["outputs"]][-1] == "default_result"

    @pytest.mark.parametrize(("prompt", "shown"), [("Prefer Billing for refunds.", True), ("", False)])
    def test_decision_mode_explains_a_saved_custom_prompt_instead_of_hiding_it(self, prompt, shown):
        router = SmartRouterComponent()
        build_config = _fresh_build_config(router)
        build_config["custom_prompt"]["value"] = prompt
        original_info = build_config["custom_prompt"]["info"]

        build_config = router.update_build_config(build_config, "Decision Model", "routing_mode")
        assert build_config["custom_prompt"]["show"] is shown
        assert "Not used in Decision Model mode" in build_config["custom_prompt"]["info"]
        assert build_config["custom_prompt"]["value"] == prompt

        build_config = router.update_build_config(build_config, "Language Model", "routing_mode")
        assert build_config["custom_prompt"]["show"] is True
        assert build_config["custom_prompt"]["info"] == original_info

    @pytest.mark.parametrize("last_number", [-1, 10000, "3", True])
    def test_assign_route_ids_rejects_an_out_of_range_counter(self, last_number):
        with pytest.raises(ValueError, match="Last Route Number"):
            assign_route_ids(_rows(None), last_number)

    def test_assign_route_ids_fails_clearly_when_numbers_run_out(self):
        with pytest.raises(ValueError, match="at most 9999 routes"):
            assign_route_ids(_rows("category_9999_result", None), 9999)

    @pytest.mark.parametrize(("value", "expected"), [("0.8", 0.8), (" 0.75 ", 0.75), (0.5, 0.5), (1, 1.0)])
    def test_thresholds_typed_into_the_routes_table_are_numbers(self, value, expected):
        assert SmartRouterComponent._validate_probability(value) == expected

    @pytest.mark.parametrize("value", ["high", "", "1.5", "nan", None, True])
    def test_invalid_thresholds_fail_clearly(self, value):
        with pytest.raises(DecisionConfigurationError, match="from 0 to 1"):
            SmartRouterComponent._validate_probability(value)

    def test_unknown_routing_mode_fails_instead_of_running_as_language_model(self):
        router = SmartRouterComponent()
        router.set(routing_mode="Decison Model")
        with pytest.raises(DecisionConfigurationError, match="Unknown routing mode"):
            router._pre_run_setup()

    def test_decision_mode_passes_the_callers_request_variables(self, monkeypatch):
        """Per-request credentials (X-LANGFLOW-GLOBAL-VAR-*) reach the decision runtime."""
        seen = {}

        def evaluate(_request, **kwargs):
            seen.update(kwargs)
            msg = "Timed out."
            raise DecisionEvaluationError(msg, category="timeout")

        monkeypatch.setattr("lfx.components.llm_operations.llm_conditional_router.evaluate_decision", evaluate)
        router = SmartRouterComponent()
        router.set(
            input_text="I was charged twice.",
            routes=[{"route_category": "Billing"}, {"route_category": "Sales"}],
            routing_mode="Decision Model",
            decision_model=[{"provider": "TypeSafe", "name": "jev-latest"}],
            decision_question="Which team?",
            minimum_probability=0.7,
            evaluation_error_action="Route to Else",
            enable_else_output=True,
        )
        graph = SimpleNamespace(context={"request_variables": {"TYPESAFE_API_KEY": "tenant-key"}}, user_id=None)
        router._vertex = SimpleNamespace(
            graph=graph, outgoing_edges=[SimpleNamespace(source_handle=SimpleNamespace(name="default_result"))]
        )
        router.log = lambda *_args, **_kwargs: None
        router._get_categorization()
        assert seen["request_variables"] == {"TYPESAFE_API_KEY": "tenant-key"}  # pragma: allowlist secret

    @staticmethod
    def _router_with_outputs(*output_names):
        router = SmartRouterComponent()
        router._set_outputs([{"name": name, "display_name": name, "method": "process_case"} for name in output_names])
        return router

    def test_routes_without_ids_keep_their_positional_names_at_run_time(self):
        router = self._router_with_outputs("category_1_result", "category_2_result", "default_result")
        router.set(routes=[{"route_category": "A"}, {"route_category": "B"}], last_route_number=2)
        assert router._route_ids() == ["category_1_result", "category_2_result"]

    def test_a_route_without_a_matching_output_fails_clearly(self):
        router = self._router_with_outputs("category_1_result", "default_result")
        router.set(
            routes=[
                {"route_category": "A", "route_id": "category_1_result"},
                {"route_category": "B", "route_id": "category_5_result"},
            ],
            last_route_number=5,
        )
        with pytest.raises(DecisionConfigurationError, match="don't match its outputs"):
            router._route_ids()

    def test_a_saved_route_output_without_a_route_fails_clearly(self):
        """A tweak that drops route 2 would otherwise leave its connected branch running."""
        router = self._router_with_outputs("category_1_result", "category_2_result", "category_3_result")
        router.set(
            routes=[
                {"route_category": "A", "route_id": "category_1_result"},
                {"route_category": "C", "route_id": "category_3_result"},
            ],
            last_route_number=3,
        )
        with pytest.raises(DecisionConfigurationError, match="don't match its outputs"):
            router._route_ids()

    def test_rows_without_ids_follow_the_saved_route_order(self):
        """A tweak that sends routes in their saved order keeps each route on its own output."""
        router = self._router_with_outputs("category_1_result", "category_3_result", "category_2_result")
        router.set(routes=[{"route_category": "A"}, {"route_category": "C"}, {"route_category": "B"}])
        assert router._route_ids() == ["category_1_result", "category_3_result", "category_2_result"]

    @pytest.mark.parametrize("mode", ["Language Model", "Decision Model"])
    def test_routes_that_dont_match_the_outputs_stop_before_any_model_call(self, mode):
        router = self._router_with_outputs("category_1_result", "category_2_result", "default_result")
        router.set(
            routing_mode=mode,
            routes=[{"route_category": "A"}, {"route_category": "B"}, {"route_category": "C"}],
        )
        with (
            patch.object(router, "_get_categorization", side_effect=AssertionError("no model call")),
            pytest.raises(DecisionConfigurationError, match="don't match its outputs"),
        ):
            router._pre_run_setup()

    def test_decision_type_shows_only_in_decision_mode(self):
        router = SmartRouterComponent()
        build_config = router.update_build_config(_fresh_build_config(router), "Language Model", "routing_mode")
        assert build_config["decision_kind"]["show"] is False
        build_config = router.update_build_config(build_config, "Decision Model", "routing_mode")
        assert build_config["decision_kind"]["show"] is True
        assert build_config["decision_kind"]["value"] == "Choice"

    def test_choice_and_score_keep_their_own_rows_and_outputs(self):
        """Switching type swaps tables and outputs, and neither table loses its rows."""
        router = SmartRouterComponent()
        router.set(routing_mode="Decision Model")
        build_config = router.update_build_config(_fresh_build_config(router), "Decision Model", "routing_mode")
        node = {"outputs": [], "template": build_config}
        shown = {}
        for kind in ("Score", "Choice", "Score"):
            build_config = router.update_build_config(build_config, kind, "decision_kind")
            build_config["decision_kind"]["value"] = kind
            outputs = [output.name for output in router.update_outputs(node, "decision_kind", kind)["outputs"]]
            shown[kind] = (outputs, build_config["routes"]["show"], build_config["score_levels"]["show"])
        assert shown["Score"] == (["level_1_result", "level_2_result", "level_3_result", "default_result"], False, True)
        assert shown["Choice"] == (["category_1_result", "category_2_result", "default_result"], True, False)
        assert [row["route_category"] for row in build_config["routes"]["value"]] == ["Billing", "Sales"]
        assert [row["route_category"] for row in build_config["score_levels"]["value"]] == ["Low", "Medium", "High"]
        # Score rounds to a level, so the router's threshold doesn't apply either.
        assert build_config["minimum_probability"]["show"] is False
        assert "rounds to" in build_config["score_levels"]["info"]

    def test_score_uses_its_own_levels_not_the_routes(self, monkeypatch):
        routes = [{"route_category": name, "minimum_probability": 0.99} for name in ("Billing", "Support", "Sales")]
        routed, evidence, request = _decide(
            monkeypatch, "Score", routes, _score(0.1, 0.4, 0.5), minimum_probability=None, score_levels=LEVELS
        )
        assert routed == "Medium"
        assert [level.label for level in request.levels] == ["Low", "Medium", "High"]
        assert evidence["route_thresholds"] == {}

    @pytest.mark.parametrize(
        ("question", "kind", "expected"),
        [
            ("Which route best matches the input?", "Score", "Which level best describes the input?"),
            ("Which route best matches the input?", "Boolean", ""),
            ("", "Choice", "Which route best matches the input?"),
            ("Which team should take this?", "Boolean", "Which team should take this?"),
        ],
    )
    def test_switching_type_swaps_only_a_stock_question(self, question, kind, expected):
        router = SmartRouterComponent()
        router.set(routing_mode="Decision Model")
        build_config = _fresh_build_config(router)
        build_config["decision_question"]["value"] = question
        build_config = router.update_build_config(build_config, kind, "decision_kind")
        assert build_config["decision_question"]["value"] == expected

    def test_unknown_decision_type_fails_instead_of_running_as_choice(self):
        router = SmartRouterComponent()
        with pytest.raises(DecisionConfigurationError, match="Unknown decision type"):
            router.update_build_config(_fresh_build_config(router), "Ranking", "decision_kind")

    @pytest.mark.parametrize(("probability_true", "label"), [(0.9, "Yes"), (0.1, "No")])
    def test_boolean_answers_through_its_yes_and_no_outputs(self, monkeypatch, probability_true, label):
        # The routes table plays no part in Boolean.
        routed, evidence, request = _decide(monkeypatch, "Boolean", [], _boolean(probability_true))
        assert routed == label
        assert request.kind == "boolean"
        assert not request.options
        assert not request.levels
        assert evidence["route_probabilities"] == pytest.approx(
            {"yes_result": probability_true, "no_result": 1 - probability_true}
        )

    def test_a_no_exactly_at_its_threshold_takes_the_no_output(self, monkeypatch):
        """1 - 0.33 is 0.6699999999999999 in floating point, just under a 0.67 threshold."""
        routed, evidence, _ = _decide(monkeypatch, "Boolean", [], _boolean(0.33), minimum_probability=0.67)
        assert routed == "No"
        assert evidence["route_probabilities"]["no_result"] == 0.67

    def test_boolean_tells_the_model_what_yes_and_no_mean(self, monkeypatch):
        _, _, request = _decide(
            monkeypatch,
            "Boolean",
            [],
            _boolean(0.9),
            yes_description="Asks for money back",
            no_description="Anything else",
        )
        assert (request.yes_description, request.no_description) == ("Asks for money back", "Anything else")

    @pytest.mark.parametrize(
        ("probability_true", "fields", "label"),
        [
            (0.85, {"yes_minimum_probability": 0.9}, ""),  # Yes needs more than the router's 0.7
            (0.35, {"no_minimum_probability": 0.6}, "No"),  # No needs less
            (0.35, {"no_minimum_probability": ""}, ""),  # blank falls back to the router's 0.7
        ],
    )
    def test_yes_and_no_can_each_set_their_own_threshold(self, monkeypatch, probability_true, fields, label):
        routed, evidence, _ = _decide(monkeypatch, "Boolean", [], _boolean(probability_true), **fields)
        assert routed == label
        expected = {"yes_result": 0.7, "no_result": 0.7}
        expected.update({f"{key.split('_')[0]}_result": value for key, value in fields.items() if value != ""})
        assert evidence["route_thresholds"] == expected

    def test_switching_to_boolean_replaces_the_route_outputs_with_yes_and_no(self):
        router = SmartRouterComponent()
        router.set(routing_mode="Decision Model")
        build_config = router.update_build_config(_fresh_build_config(router), "Decision Model", "routing_mode")
        node = {"outputs": [], "template": build_config}

        build_config = router.update_build_config(build_config, "Boolean", "decision_kind")
        names = [output.name for output in router.update_outputs(node, "decision_kind", "Boolean")["outputs"]]
        # Else keeps its edge: it still takes unsure answers.
        assert names == ["yes_result", "no_result", "default_result"]
        assert build_config["routes"]["show"] is False
        assert build_config["routes"]["required"] is False
        assert all(build_config[name]["show"] for name in ("yes_description", "no_description", "yes_message"))

        build_config["decision_kind"]["value"] = "Boolean"
        build_config = router.update_build_config(build_config, "Choice", "decision_kind")
        names = [output.name for output in router.update_outputs(node, "decision_kind", "Choice")["outputs"]]
        assert names == ["category_1_result", "category_2_result", "default_result"]
        assert build_config["routes"]["show"] is True
        assert not any(build_config[name]["show"] for name in ("yes_description", "no_description", "yes_message"))

    def test_language_model_mode_keeps_the_route_outputs_whatever_the_type(self):
        router = SmartRouterComponent()
        build_config = _fresh_build_config(router)
        build_config["decision_kind"]["value"] = "Boolean"
        build_config = router.update_build_config(build_config, "Language Model", "routing_mode")
        node = router.update_outputs({"outputs": [], "template": build_config}, "routing_mode", "Language Model")
        assert [output.name for output in node["outputs"]] == ["category_1_result", "category_2_result"]
        assert build_config["routes"]["show"] is True
        assert build_config["yes_description"]["show"] is False

    @pytest.mark.parametrize(
        ("probability_true", "reason"), [(0.5, "tied_top_probability"), (0.6, "below_minimum_probability")]
    )
    def test_an_unsure_boolean_goes_to_else(self, monkeypatch, probability_true, reason):
        routed, evidence, _ = _decide(monkeypatch, "Boolean", [], _boolean(probability_true))
        assert routed == ""
        assert evidence["reason"] == reason
        assert evidence["activated_branch"] == "default_result"

    def test_a_decision_reports_the_tokens_it_used(self, monkeypatch):
        """Chat Output adds these to the Playground message, as it does a language model's."""
        result = _boolean(0.9).model_copy(update={"usage": {"input_tokens": 296, "output_tokens": 1}})
        router, routed, _ = _decided_router(monkeypatch, "Boolean", [], result)
        assert routed == "Yes"
        assert router._token_usage == Usage(input_tokens=296, output_tokens=1, total_tokens=297)

    def test_a_refusal_still_reports_its_tokens(self, monkeypatch):
        refusal = DecisionResult(
            kind="boolean",
            provider="OpenAI",
            model="gpt-6-luna",
            status="refusal",
            usage={"input_tokens": 120, "output_tokens": 0, "total_tokens": 120},
        )
        router, routed, _ = _decided_router(monkeypatch, "Boolean", [], refusal)
        assert routed == ""
        assert router._token_usage == Usage(input_tokens=120, output_tokens=0, total_tokens=120)

    def test_a_decision_without_usage_reports_none(self, monkeypatch):
        router, _, _ = _decided_router(monkeypatch, "Boolean", [], _boolean(0.9))
        assert router._token_usage is None

    def test_each_run_starts_without_the_last_runs_tokens(self):
        router = self._router_with_outputs("yes_result", "no_result", "default_result")
        router.set(routing_mode="Decision Model", decision_kind="Boolean", enable_else_output=True)
        router._vertex = SimpleNamespace(
            outgoing_edges=[SimpleNamespace(source_handle=SimpleNamespace(name="default_result"))]
        )
        router._token_usage = Usage(input_tokens=5, output_tokens=5, total_tokens=10)
        router._pre_run_setup()
        assert router._token_usage is None

    def test_a_blank_question_stops_before_any_model_call(self, monkeypatch):
        with pytest.raises(DecisionConfigurationError, match="Enter a Decision Question"):
            _decide(monkeypatch, "Boolean", [], _boolean(0.9), question="  ")

    def test_a_boolean_router_runs_without_matching_routes_to_outputs(self):
        """Its Yes and No outputs don't come from the routes, so the route check doesn't apply."""
        router = self._router_with_outputs("yes_result", "no_result", "default_result")
        router.set(
            routing_mode="Decision Model",
            decision_kind="Boolean",
            routes=[{"route_category": "Leftover"}],
            enable_else_output=True,
        )
        router._vertex = SimpleNamespace(
            outgoing_edges=[SimpleNamespace(source_handle=SimpleNamespace(name="default_result"))]
        )
        router._pre_run_setup()

    @pytest.mark.parametrize(
        ("probabilities", "label"),
        [
            ((0.89, 0.0, 0.11), "Low"),  # score 0.22
            ((0.1, 0.4, 0.5), "Medium"),  # 1.4
            ((0.0, 0.08, 0.92), "High"),  # 1.92
            ((0.0, 0.0, 1.0), "High"),  # 2.0, the top level
            ((0.5, 0.5, 0.0), "Medium"),  # 0.5: halfway takes the higher level, where round() gives 0
            ((0.0, 0.5, 0.5), "High"),  # 1.5: halfway again
            ((0.25, 0.5, 0.25), "Medium"),  # 1.0
        ],
    )
    def test_score_takes_the_level_its_score_rounds_to(self, monkeypatch, probabilities, label):
        routed, evidence, request = _decide(
            monkeypatch, "Score", [], _score(*probabilities), minimum_probability=None, score_levels=LEVELS
        )
        assert routed == label
        assert [level.label for level in request.levels] == ["Low", "Medium", "High"]
        assert evidence["reason"] == "accepted"
        assert evidence["activated_branch"] == f"level_{['Low', 'Medium', 'High'].index(label) + 1}_result"

    def test_duplicate_route_names_are_named(self, monkeypatch):
        routes = [{"route_category": "Billing"}, {"route_category": "billing"}]
        with pytest.raises(DecisionConfigurationError, match="needs a different Route Name; 'billing' is used twice"):
            _decide(monkeypatch, "Choice", routes, _choice_result(0.9, 0.1))

    def test_a_blank_threshold_says_it_is_empty(self):
        with pytest.raises(
            DecisionConfigurationError, match=r"Enter a Minimum Probability from 0 to 1, such as 0\.7\."
        ):
            SmartRouterComponent._validate_probability(None)

    def test_language_model_mode_hides_the_route_threshold_column(self):
        router = SmartRouterComponent()
        # A router added from the sidebar starts in Language Model mode, before any refresh runs.
        fresh = router.to_frontend_node()["data"]["node"]["template"]["routes"]["table_schema"]
        assert next(c for c in fresh if c["name"] == "minimum_probability")["hidden"] is True
        build_config = router.update_build_config(_fresh_build_config(router), "Language Model", "routing_mode")
        [column] = [c for c in build_config["routes"]["table_schema"] if c["name"] == "minimum_probability"]
        assert column["hidden"] is True
        router.set(routing_mode="Decision Model")
        build_config = router.update_build_config(build_config, "Decision Model", "routing_mode")
        assert column["hidden"] is False


class TestSmartRouterUpdate:
    """Update rebuilds the node from the class defaults and copies back only values."""

    @staticmethod
    async def _update(saved_template: dict) -> dict:
        router = SmartRouterComponent()
        fresh = router.to_frontend_node()["data"]["node"]
        saved = {**fresh, "template": {**fresh["template"], **saved_template}}
        return await router.update_frontend_node(router.to_frontend_node()["data"]["node"], saved)

    async def test_a_decision_router_keeps_its_decision_fields(self):
        node = await self._update(
            {
                "routing_mode": {"type": "str", "value": "Decision Model"},
                "decision_kind": {"type": "str", "value": "Boolean"},
                "routes": {"type": "table", "value": [{"route_category": "Billing"}]},
            }
        )
        template = node["template"]
        for name in ("decision_model", "decision_question", "minimum_probability", "yes_message"):
            assert template[name]["show"] is True, name
        assert template["model"]["show"] is False
        assert template["routes"]["show"] is False

    async def test_routes_saved_without_ids_get_them(self):
        rows = [{"route_category": name} for name in ("A", "B", "C")]
        node = await self._update({"routes": {"type": "table", "value": rows}})
        template = node["template"]
        assert [row["route_id"] for row in template["routes"]["value"]] == [
            "category_1_result",
            "category_2_result",
            "category_3_result",
        ]
        assert template["last_route_number"]["value"] == 3


def test_else_help_says_what_it_gets_for_each_type():
    router = SmartRouterComponent()
    router.set(routing_mode="Decision Model")
    config = _fresh_build_config(router)
    config = router.update_build_config(config, "Score", "decision_kind")
    assert "Every Score answer reaches a level" in config["enable_else_output"]["info"]
    config = router.update_build_config(config, "Choice", "decision_kind")
    assert "aren't sure enough" in config["enable_else_output"]["info"]
