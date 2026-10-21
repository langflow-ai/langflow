from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from lfx.base.models.decisions.schema import DecisionConfigurationError, DecisionEvaluationError, DecisionResult
from lfx.components.llm_operations.llm_conditional_router import SmartRouterComponent, assign_route_ids
from lfx.schema.dotdict import dotdict
from lfx.schema.message import Message

from tests.base import ComponentTestBaseWithoutClient


def _rows(*route_ids):
    return [{"route_category": f"Route {i}", "route_id": route_id} for i, route_id in enumerate(route_ids)]


def _fresh_build_config(router):
    build_config = dotdict(router.to_frontend_node()["data"]["node"]["template"])
    build_config["routes"]["value"] = [{"route_category": name} for name in ("Billing", "Sales")]
    return build_config


def _threshold_column(build_config):
    return next(column for column in build_config["routes"]["table_schema"] if column["name"] == "minimum_probability")


def _decide(monkeypatch, kind, routes, result, *, minimum_probability=0.7, question="Is this a refund request?"):
    """Route one message with ``result`` as the provider's answer; returns the label, evidence and request."""
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
    )
    router._vertex = SimpleNamespace(
        outgoing_edges=[SimpleNamespace(source_handle=SimpleNamespace(name="default_result"))]
    )
    router.log = lambda *_args, **_kwargs: None
    label = router._get_categorization()
    return label, router._decision_evidence, sent[0] if sent else None


def _boolean(probability_true):
    return DecisionResult(kind="boolean", provider="TypeSafe", model="jev-1.13.0", probability_true=probability_true)


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


REFUND_ROUTES = [{"route_category": "Refund"}, {"route_category": "No refund"}]
# The tiers from the design discussion: A at 0.1, B at 0.5, C at 0.95.
TIERS = [
    {"route_category": "A", "minimum_probability": 0.1},
    {"route_category": "B", "minimum_probability": 0.5},
    {"route_category": "C", "minimum_probability": 0.95},
]


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
        with pytest.raises(DecisionConfigurationError, match="between 0 and 1"):
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


class TestSmartRouterDecisionTypes:
    """Choice, Boolean and Score in Decision Model mode, and the fields each one shows."""

    def test_decision_type_shows_only_in_decision_mode(self):
        router = SmartRouterComponent()
        build_config = router.update_build_config(_fresh_build_config(router), "Language Model", "routing_mode")
        assert build_config["decision_kind"]["show"] is False
        build_config = router.update_build_config(build_config, "Decision Model", "routing_mode")
        assert build_config["decision_kind"]["show"] is True
        assert build_config["decision_kind"]["value"] == "Choice"

    def test_score_moves_each_threshold_onto_its_route(self):
        router = SmartRouterComponent()
        router.set(routing_mode="Decision Model")
        build_config = router.update_build_config(_fresh_build_config(router), "Decision Model", "routing_mode")
        choice_column = dict(_threshold_column(build_config))

        build_config = router.update_build_config(build_config, "Score", "decision_kind")
        assert build_config["minimum_probability"]["show"] is False
        assert build_config["minimum_probability"]["required"] is False
        assert _threshold_column(build_config)["display_name"] == "Minimum Score"
        assert "Minimum Score" in build_config["routes"]["info"]

        build_config = router.update_build_config(build_config, "Choice", "decision_kind")
        assert build_config["minimum_probability"]["show"] is True
        assert _threshold_column(build_config) == choice_column

    def test_language_model_mode_keeps_probability_labels_whatever_the_type(self):
        router = SmartRouterComponent()
        build_config = _fresh_build_config(router)
        build_config["decision_kind"]["value"] = "Score"
        build_config = router.update_build_config(build_config, "Language Model", "routing_mode")
        assert _threshold_column(build_config)["display_name"] == "Minimum Probability (Optional)"

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

    @pytest.mark.parametrize(("probability_true", "label"), [(0.9, "Refund"), (0.1, "No refund")])
    def test_boolean_sends_yes_to_the_first_route_and_no_to_the_second(self, monkeypatch, probability_true, label):
        routed, evidence, request = _decide(monkeypatch, "Boolean", REFUND_ROUTES, _boolean(probability_true))
        assert routed == label
        assert request.kind == "boolean"
        assert not request.options
        assert not request.levels
        assert evidence["route_probabilities"] == pytest.approx(
            {"category_1_result": probability_true, "category_2_result": 1 - probability_true}
        )

    def test_boolean_tells_the_model_what_each_route_means(self, monkeypatch):
        routes = [
            {"route_category": "Refund", "route_description": "Asks for money back"},
            {"route_category": "No refund", "route_description": "Anything else"},
        ]
        _, _, request = _decide(monkeypatch, "Boolean", routes, _boolean(0.9))
        assert (request.yes_description, request.no_description) == ("Asks for money back", "Anything else")

    @pytest.mark.parametrize(
        ("probability_true", "reason"), [(0.5, "tied_top_probability"), (0.6, "below_minimum_probability")]
    )
    def test_an_unsure_boolean_goes_to_else(self, monkeypatch, probability_true, reason):
        routed, evidence, _ = _decide(monkeypatch, "Boolean", REFUND_ROUTES, _boolean(probability_true))
        assert routed == ""
        assert evidence["reason"] == reason
        assert evidence["activated_branch"] == "default_result"

    @pytest.mark.parametrize(
        "routes",
        [
            [*REFUND_ROUTES, {"route_category": "Unsure"}],
            [{"route_category": "Refund"}, {"route_category": "refund"}],
        ],
    )
    def test_boolean_needs_two_distinct_routes(self, monkeypatch, routes):
        with pytest.raises(DecisionConfigurationError, match="exactly two routes"):
            _decide(monkeypatch, "Boolean", routes, _boolean(0.9))

    def test_a_blank_question_stops_before_any_model_call(self, monkeypatch):
        with pytest.raises(DecisionConfigurationError, match="needs a Decision Question"):
            _decide(monkeypatch, "Boolean", REFUND_ROUTES, _boolean(0.9), question="  ")

    @pytest.mark.parametrize(
        ("probabilities", "label"),
        [
            ((0.1, 0.4, 0.5), "B"),  # 0.7: above B's 0.5, below C's 0.95
            ((0.9, 0.1, 0.0), ""),  # 0.05: below every route
            ((0.0, 0.08, 0.92), "C"),  # 0.96
        ],
    )
    def test_score_takes_the_highest_route_whose_minimum_it_reaches(self, monkeypatch, probabilities, label):
        routed, evidence, request = _decide(
            monkeypatch, "Score", TIERS, _score(*probabilities), minimum_probability=None
        )
        assert routed == label
        assert [level.label for level in request.levels] == ["A", "B", "C"]
        assert evidence["normalized_score"] == pytest.approx(sum(i * p for i, p in enumerate(probabilities)) / 2)
        assert evidence["reason"] == ("accepted" if label else "below_minimum_score")

    @pytest.mark.parametrize(
        ("routes", "match"),
        [
            ([TIERS[0], {"route_category": "B"}, TIERS[2]], "Minimum Score on every route"),
            ([TIERS[1], TIERS[0], TIERS[2]], "higher than the route before it"),
            ([TIERS[0], {**TIERS[1], "minimum_probability": 0.1}, TIERS[2]], "higher than the route before it"),
        ],
    )
    def test_score_minimums_must_rise_on_every_route(self, monkeypatch, routes, match):
        with pytest.raises(DecisionConfigurationError, match=match):
            _decide(monkeypatch, "Score", routes, _score(0.1, 0.4, 0.5), minimum_probability=None)
