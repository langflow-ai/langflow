import re
from collections.abc import Mapping
from itertools import pairwise
from math import isfinite
from typing import Any

from lfx.base.models.decisions.runtime import evaluate_decision, request_variables_of
from lfx.base.models.decisions.schema import (
    DecisionConfigurationError,
    DecisionEvaluationError,
    DecisionRequest,
    decision_request,
)
from lfx.base.models.unified_models import (
    get_llm,
    handle_model_input_update,
)
from lfx.custom import Component
from lfx.field_typing.range_spec import RangeSpec
from lfx.io import (
    BoolInput,
    DropdownInput,
    FloatInput,
    IntInput,
    MessageInput,
    MessageTextInput,
    ModelInput,
    MultilineInput,
    Output,
    SecretStrInput,
    TableInput,
)
from lfx.schema.message import Message
from lfx.schema.table import EditMode
from lfx.schema.token_usage import extract_usage_from_message

_ROUTE_ID = re.compile(r"category_([1-9][0-9]{0,3})_result")
_MAX_ROUTE_NUMBER = 9999
_CUSTOM_PROMPT_INFO = (
    "Additional instructions for LLM-based categorization. "
    "These will be added to the base prompt. "
    "Use {input_text} for the input text and {routes} for the available categories."
)
_CUSTOM_PROMPT_DECISION_INFO = (
    "Not used in Decision Model mode, which has no prompt. Kept so it applies again in Language Model mode."
)
_DECISION_KINDS = {"Choice": "choice", "Boolean": "boolean", "Score": "score"}
# Switching types swaps only these stock questions, never one the user wrote. Boolean has none:
# a yes/no question has to name what it asks.
_DECISION_QUESTIONS = {
    "choice": "Which route best matches the input?",
    "boolean": "",
    "score": "Which level best describes the input?",
}
_DECISION_QUESTION_INFO = {
    "choice": "Instructions for the decision model. Additional Instructions apply only to Language Model mode.",
    "boolean": (
        'A yes/no question, such as "Is the customer asking for a refund?". Yes takes the first route and No the '
        "second."
    ),
    "score": "The question that places the input on the routes, read as levels from lowest to highest.",
}
_ROUTES_INFO = {
    "choice": (
        "Define the categories for routing. Each row should have a route/category name "
        "and optionally a custom output value."
    ),
    "boolean": (
        "Exactly two routes: the first is Yes and the second No, and each description says what its answer means. "
        "OpenAI Decisions takes no descriptions. Unsure answers go to Else."
    ),
    "score": (
        "Levels ordered from lowest to highest, at most 10. Each route needs a Minimum Score: the input takes the "
        "highest route whose minimum its score reaches, and a score below every route goes to Else."
    ),
}
_MINIMUM_PROBABILITY_INFO = {
    "choice": (
        "Required in decision mode, from 0 to 1. The top route is chosen only when its probability is at "
        "least this value; otherwise the message goes to Else. This is the route's probability, not the "
        "provider's confidence score. A route can set its own threshold in the Routes table."
    ),
    "boolean": (
        "Required in decision mode, from 0 to 1. Yes takes the first route when P(yes) is at least this value, and "
        "No the second when P(no) is; otherwise the message goes to Else. A route can set its own threshold in "
        "the Routes table."
    ),
}


def _route_number(route_id: Any) -> int | None:
    """The number in a valid route ID such as ``category_3_result``, or None."""
    match = _ROUTE_ID.fullmatch(route_id) if isinstance(route_id, str) else None
    return int(match.group(1)) if match else None


def assign_route_ids(routes: list[dict], last_number: int) -> tuple[list[dict], int]:
    """Give every route a stable output name, so editing routes never moves an edge to another route.

    A row keeps a valid, unique ``route_id``. Rows saved before route IDs existed take their
    positional names, which match the handles already saved with the flow. Any other row
    without one, such as a new row or a copy, takes the next number above ``last_number``,
    so a deleted route's name is never given to a new route.
    """
    if isinstance(last_number, bool) or not isinstance(last_number, int) or not 0 <= last_number <= _MAX_ROUTE_NUMBER:
        msg = f"Last Route Number must be a whole number from 0 to {_MAX_ROUTE_NUMBER}."
        raise ValueError(msg)
    numbers: list[int | None] = []
    seen: set[int] = set()
    for row in routes:
        number = _route_number(row.get("route_id"))
        numbers.append(number if number not in seen else None)
        if number is not None:
            seen.add(number)
    if last_number == 0 and not any(numbers):
        numbers = list(range(1, len(routes) + 1))
    highest = max([last_number, *(number for number in numbers if number)])
    for i, number in enumerate(numbers):
        if number is None:
            highest += 1
            numbers[i] = highest
    if highest > _MAX_ROUTE_NUMBER:
        msg = f"A Smart Router can number at most {_MAX_ROUTE_NUMBER} routes over its lifetime."
        raise ValueError(msg)
    keyed = [{**row, "route_id": f"category_{number}_result"} for row, number in zip(routes, numbers, strict=True)]
    return keyed, highest


class SmartRouterComponent(Component):
    display_name = "Smart Router"
    description = "Routes an input message using LLM-based categorization."
    icon = "route"
    name = "SmartRouter"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._matched_category = None
        self._categorization_result: str | None = None
        self._excluded_outputs: set[str] = set()
        self._decision_evidence: dict | None = None

    inputs = [
        DropdownInput(
            name="routing_mode",
            display_name="Routing Mode",
            options=["Language Model", "Decision Model"],
            value="Language Model",
            real_time_refresh=True,
        ),
        ModelInput(
            name="decision_model",
            display_name="Decision Model",
            model_type="decision",
            show=False,
            real_time_refresh=True,
        ),
        DropdownInput(
            name="decision_kind",
            display_name="Decision Type",
            options=list(_DECISION_KINDS),
            value="Choice",
            info=(
                "Choice picks one route. Boolean answers yes or no between two routes. "
                "Score reads the routes as ordered levels."
            ),
            show=False,
            real_time_refresh=True,
        ),
        MultilineInput(
            name="decision_question",
            display_name="Decision Question",
            value=_DECISION_QUESTIONS["choice"],
            info=_DECISION_QUESTION_INFO["choice"],
            show=False,
        ),
        FloatInput(
            name="minimum_probability",
            preserve_empty=True,
            display_name="Minimum Probability",
            info=_MINIMUM_PROBABILITY_INFO["choice"],
            range_spec=RangeSpec(min=0, max=1, step=0.01),
            show=False,
        ),
        DropdownInput(
            name="evaluation_error_action",
            display_name="Evaluation Error Action",
            options=["Stop with error", "Route to Else"],
            value="Stop with error",
            show=False,
            advanced=True,
        ),
        ModelInput(
            name="model",
            display_name="Language Model",
            info="Select your model provider",
            real_time_refresh=True,
            required=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="Overrides global provider settings. Leave blank to use your pre-configured API Key.",
            real_time_refresh=True,
            advanced=True,
        ),
        MessageTextInput(
            name="input_text",
            display_name="Input",
            info="The primary text input for the operation.",
            required=True,
        ),
        TableInput(
            name="routes",
            display_name="Routes",
            info=_ROUTES_INFO["choice"],
            table_schema=[
                {
                    "name": "route_category",
                    "display_name": "Route Name",
                    "type": "str",
                    "description": "Name for the route (used for both output name and category matching)",
                    "edit_mode": EditMode.INLINE,
                },
                {
                    "name": "route_description",
                    "display_name": "Route Description",
                    "type": "str",
                    "description": "Description of when this route should be used (helps LLM understand the category)",
                    "default": "",
                    "edit_mode": EditMode.POPOVER,
                },
                {
                    "name": "output_value",
                    "display_name": "Route Message (Optional)",
                    "type": "str",
                    "description": (
                        "Optional message to send when this route is matched."
                        "Leave empty to pass through the original input text."
                    ),
                    "default": "",
                    "edit_mode": EditMode.POPOVER,
                },
                {
                    "name": "minimum_probability",
                    "display_name": "Minimum Probability (Optional)",
                    "type": "float",
                    "formatter": "number",
                    "description": (
                        "Decision mode only: the probability this route needs, at least, from 0 to 1. "
                        "Leave empty to use the router's Minimum Probability."
                    ),
                    "edit_mode": EditMode.INLINE,
                },
                {
                    # Its own column, so a type switch never reads a probability as a score or back.
                    "name": "minimum_score",
                    "display_name": "Minimum Score",
                    "type": "float",
                    "formatter": "number",
                    "description": (
                        "Score mode: the lowest score that takes this route. The score runs from 0, every level's "
                        "weight on the first route, to 1, all of it on the last. Required, and higher on each route "
                        "than on the one before."
                    ),
                    "edit_mode": EditMode.INLINE,
                    "hidden": True,
                },
                {
                    "name": "route_id",
                    "display_name": "Route ID",
                    "type": "str",
                    "description": "Set automatically. Keeps this route's connections when other routes change.",
                    "hidden": True,
                    "disable_edit": True,
                },
            ],
            value=[
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
            real_time_refresh=True,
            required=True,
        ),
        MessageInput(
            name="message",
            display_name="Override Output",
            info=(
                "Optional override message that will replace both the Input and Output Value "
                "for all routes when filled."
            ),
            required=False,
            advanced=True,
        ),
        BoolInput(
            name="enable_else_output",
            display_name="Include Else Output",
            info=(
                "Include an Else output for cases that don't match any route. Decision mode requires it, "
                "connected: messages no route is confident enough for go there."
            ),
            value=False,
            advanced=True,
            real_time_refresh=True,
        ),
        IntInput(
            name="last_route_number",
            display_name="Last Route Number",
            info="Set automatically: the highest route number assigned, so a deleted route's output is never reused.",
            value=0,
            show=False,
            advanced=True,
            override_skip=True,
        ),
        MultilineInput(
            name="custom_prompt",
            display_name="Additional Instructions",
            info=_CUSTOM_PROMPT_INFO,
            advanced=True,
        ),
    ]

    outputs: list[Output] = []

    def _selected_model_provider_policy_ids(self, parameters: Mapping[str, Any] | None = None) -> tuple[str, ...]:
        effective = dict(parameters if parameters is not None else self._parameters)
        effective.pop("model" if self._is_decision_mode(effective.get("routing_mode")) else "decision_model", None)
        return super()._selected_model_provider_policy_ids(effective)

    def _is_decision_mode(self, mode: Any = None) -> bool:
        """Whether ``mode``, by default this router's Routing Mode, is Decision Model; an unknown mode stops."""
        if mode is None:
            mode = getattr(self, "routing_mode", "Language Model")
        if mode not in {"Language Model", "Decision Model"}:
            msg = "Unknown routing mode."
            raise DecisionConfigurationError(msg)
        return mode == "Decision Model"

    def _decision_kind(self, kind: Any = None) -> str:
        """``kind``, by default this router's Decision Type, as a request kind; an unknown type stops."""
        if kind is None:
            kind = getattr(self, "decision_kind", "Choice")
        if kind not in _DECISION_KINDS:
            msg = "Unknown decision type."
            raise DecisionConfigurationError(msg)
        return _DECISION_KINDS[kind]

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None):
        """Dynamically update build config with user-filtered model options."""
        decision_mode = self._is_decision_mode(field_value if field_name == "routing_mode" else None)
        kind = self._decision_kind(
            field_value if field_name == "decision_kind" else (build_config.get("decision_kind") or {}).get("value")
        )
        for name in ("decision_model", "decision_kind", "decision_question", "evaluation_error_action"):
            if name in build_config:
                build_config[name]["show"] = decision_mode
                build_config[name]["required"] = decision_mode
        if "minimum_probability" in build_config:
            # Score routes each carry their own minimum score instead.
            uses_router_threshold = decision_mode and kind != "score"
            build_config["minimum_probability"].update(
                show=uses_router_threshold,
                required=uses_router_threshold,
                info=_MINIMUM_PROBABILITY_INFO.get(kind, _MINIMUM_PROBABILITY_INFO["choice"]),
            )
        if "decision_question" in build_config:
            question = build_config["decision_question"]
            question["info"] = _DECISION_QUESTION_INFO[kind]
            if (
                field_name == "decision_kind"
                and str(question.get("value") or "").strip() in _DECISION_QUESTIONS.values()
            ):
                question["value"] = _DECISION_QUESTIONS[kind]
        # The API key overrides the Language Model's credentials only; decision
        # credentials come from that provider's own settings.
        for name in ("model", "api_key"):
            if name in build_config:
                build_config[name]["show"] = not decision_mode
        if "model" in build_config:
            build_config["model"]["required"] = not decision_mode
        if "custom_prompt" in build_config:
            # Decision mode ignores the prompt; show a saved one with an explanation instead of hiding it.
            prompt = build_config["custom_prompt"]
            prompt["show"] = not decision_mode or bool(str(prompt.get("value") or "").strip())
            prompt["info"] = _CUSTOM_PROMPT_DECISION_INFO if decision_mode else _CUSTOM_PROMPT_INFO
        if "enable_else_output" in build_config:
            # Decision mode needs Else, so switching to it turns Else on and keeps the setting in view.
            if decision_mode and field_name == "routing_mode":
                build_config["enable_else_output"]["value"] = True
            build_config["enable_else_output"]["advanced"] = not decision_mode
        if "routes" in build_config:
            routes = build_config["routes"]
            routes["info"] = _ROUTES_INFO[kind if decision_mode else "choice"]
            schema = routes.get("table_schema") or []
            score_mode = decision_mode and kind == "score"
            for column in schema.get("columns", []) if isinstance(schema, dict) else schema:
                if column.get("name") == "minimum_probability":
                    column["hidden"] = score_mode
                elif column.get("name") == "minimum_score":
                    column["hidden"] = not score_mode
            rows = field_value if field_name == "routes" else routes.get("value")
            last = (build_config.get("last_route_number") or {}).get("value") or 0
            routes["value"], last = assign_route_ids(rows or [], last)
            if "last_route_number" in build_config:
                build_config["last_route_number"]["value"] = last
        if decision_mode:
            return handle_model_input_update(
                self, build_config, field_value, field_name, model_field_name="decision_model"
            )
        return handle_model_input_update(self, build_config, field_value, field_name)

    def update_outputs(self, frontend_node: dict, field_name: str, field_value: Any) -> dict:
        """Create a dynamic output for each category in the categories table."""
        # The update endpoint rebuilds this node from the class, which declares no outputs,
        # so every field refresh must recreate them or the editor drops the route edges.
        frontend_node["outputs"] = []

        # Prefer the template's routes: update_build_config has already given them their IDs.
        template = frontend_node.get("template") or {}
        fallback = field_value if field_name == "routes" else getattr(self, "routes", [])
        routes_data, _ = assign_route_ids(
            (template.get("routes") or {}).get("value", fallback) or [],
            (template.get("last_route_number") or {}).get("value", getattr(self, "last_route_number", 0)) or 0,
        )

        # Add a dynamic output for each category - all using the same method
        for i, row in enumerate(routes_data):
            route_category = row.get("route_category", f"Category {i + 1}")
            frontend_node["outputs"].append(
                Output(
                    display_name=route_category,
                    name=row["route_id"],
                    method="process_case",
                    group_outputs=True,
                )
            )
        # Add default output only if enabled
        if field_name == "enable_else_output":
            enable_else = field_value
        else:
            enable_else = (template.get("enable_else_output") or {}).get(
                "value", getattr(self, "enable_else_output", False)
            )

        if enable_else:
            frontend_node["outputs"].append(
                Output(display_name="Else", name="default_result", method="default_response", group_outputs=True)
            )
        return frontend_node

    def _get_categorization(self) -> str:
        """Perform LLM categorization and cache the result.

        This ensures the LLM is called only once per component execution,
        regardless of how many outputs are connected.
        """
        # Return cached result if available
        if self._categorization_result is not None:
            return self._categorization_result

        if self._is_decision_mode():
            return self._get_decision_categorization()

        categories = getattr(self, "routes", [])
        input_text = getattr(self, "input_text", "")
        llm = get_llm(model=self.model, user_id=self.user_id, api_key=self.api_key)

        if not llm or not categories:
            self.status = "No LLM provided for categorization"
            self._categorization_result = "NONE"
            return self._categorization_result

        # Create prompt for categorization
        category_info = []
        for i, category in enumerate(categories):
            cat_name = category.get("route_category", f"Category {i + 1}")
            cat_desc = category.get("route_description", "")
            if cat_desc and cat_desc.strip():
                category_info.append(f'"{cat_name}": {cat_desc}')
            else:
                category_info.append(f'"{cat_name}"')

        categories_text = "\n".join([f"- {info}" for info in category_info if info])

        # Create base prompt
        base_prompt = (
            f"You are a text classifier. Given the following text and categories, "
            f"determine which category best matches the text.\n\n"
            f'Text to classify: "{input_text}"\n\n'
            f"Available categories:\n{categories_text}\n\n"
            f"Respond with ONLY the exact category name that best matches the text. "
            f'If none match well, respond with "NONE".\n\n'
            f"Category:"
        )

        # Use custom prompt as additional instructions if provided
        custom_prompt = getattr(self, "custom_prompt", "")
        if custom_prompt and custom_prompt.strip():
            self.status = "Using custom prompt as additional instructions"
            simple_routes = ", ".join(
                [f'"{cat.get("route_category", f"Category {i + 1}")}"' for i, cat in enumerate(categories)]
            )
            formatted_custom = custom_prompt.format(input_text=input_text, routes=simple_routes)
            prompt = f"{base_prompt}\n\nAdditional Instructions:\n{formatted_custom}"
        else:
            self.status = "Using default prompt for LLM categorization"
            prompt = base_prompt

        self.status = f"Prompt sent to LLM:\n{prompt}"

        try:
            if hasattr(llm, "invoke"):
                response = llm.invoke(prompt)
                self._token_usage = extract_usage_from_message(response)
                if hasattr(response, "content"):
                    categorization = response.content.strip().strip('"')
                else:
                    categorization = str(response).strip().strip('"')
            else:
                categorization = str(llm(prompt)).strip().strip('"')

            self.status = f"LLM response: '{categorization}'"
            self._categorization_result = categorization
        except RuntimeError as e:
            self.status = f"Error in LLM categorization: {e!s}"
            self._categorization_result = "NONE"

        return self._categorization_result

    @staticmethod
    def _validate_probability(value: Any, name: str = "Minimum probability") -> float:
        if isinstance(value, str):
            # Table cells can hold the number as text.
            try:
                value = float(value.strip())
            except ValueError:
                value = None
        if isinstance(value, bool) or not isinstance(value, int | float) or not isfinite(value) or not 0 <= value <= 1:
            msg = f"{name} must be a number between 0 and 1."
            raise DecisionConfigurationError(msg)
        return float(value)

    def _validate_decision_graph(self) -> None:
        if (
            not self.enable_else_output
            or self._vertex is None
            or not any(
                edge.source_handle and edge.source_handle.name == "default_result"
                for edge in self._vertex.outgoing_edges
            )
        ):
            msg = "Decision mode requires an enabled, connected Else output."
            raise DecisionConfigurationError(msg)

    def _get_decision_categorization(self) -> str:
        self._validate_decision_graph()
        kind = self._decision_kind()
        # Score routes each carry their own minimum score; the other types fall back to the router's.
        threshold = None if kind == "score" else self._validate_probability(self.minimum_probability)
        if self.evaluation_error_action not in {"Stop with error", "Route to Else"}:
            msg = "Unknown evaluation error action."
            raise DecisionConfigurationError(msg)
        if len(self.routes) < 2:  # noqa: PLR2004 - a choice needs at least two options
            msg = "Decision mode needs at least two routes; uncertain results already go to Else."
            raise DecisionConfigurationError(msg)
        names = [str(row.get("route_category") or "").strip() for row in self.routes]
        if not all(names):
            msg = "Every route needs a name in decision mode."
            raise DecisionConfigurationError(msg)
        if kind == "boolean" and (len(names) != 2 or names[0].casefold() == names[1].casefold()):  # noqa: PLR2004
            msg = "Boolean mode needs exactly two routes with different names: Yes first, then No."
            raise DecisionConfigurationError(msg)
        if not str(self.decision_question or "").strip():
            msg = "Decision mode needs a Decision Question."
            raise DecisionConfigurationError(msg)
        candidates = [
            {"id": route_id, "label": row["route_category"], "description": row.get("route_description") or ""}
            for route_id, row in zip(self._route_ids(), self.routes, strict=True)
        ]
        boolean = kind == "boolean"
        request = decision_request(
            kind=kind,
            question=self.decision_question,
            context=self.input_text,
            options=candidates if kind == "choice" else (),
            levels=candidates if kind == "score" else (),
            # The Yes and No routes' descriptions say what each answer means.
            yes_description=candidates[0]["description"] if boolean else "",
            no_description=candidates[1]["description"] if boolean else "",
        )
        column, measure = (
            ("minimum_score", "Minimum score") if kind == "score" else ("minimum_probability", "Minimum probability")
        )
        thresholds = {}
        for candidate, row, name in zip(candidates, self.routes, names, strict=True):
            own = row.get(column)
            if own is not None and str(own).strip():
                thresholds[candidate["id"]] = self._validate_probability(own, f"{measure} for {name!r}")
            elif threshold is None:
                msg = f"Score mode needs a Minimum Score on every route; {name!r} has none."
                raise DecisionConfigurationError(msg)
            else:
                thresholds[candidate["id"]] = threshold
        if kind == "score":
            for (low_name, low), (high_name, high) in pairwise(zip(names, thresholds.values(), strict=True)):
                if high <= low:
                    msg = (
                        "In Score mode, each route's Minimum Score must be higher than the route before it: "
                        f"{high_name!r} is not higher than {low_name!r}."
                    )
                    raise DecisionConfigurationError(msg)
        evidence = {
            "kind": kind,
            "options": candidates,
            "minimum_probability": threshold,
            "route_thresholds": thresholds,
            "activated_branch": None,
            "error_action": self.evaluation_error_action,
        }
        self._decision_evidence = evidence
        try:
            self._categorization_result = self._apply_decision(request, thresholds, evidence)
        finally:
            # Any exception leaves the result unset, so a stopped build never activates Else.
            if self._categorization_result == "":
                evidence["activated_branch"] = "default_result"
            self.log(self._sanitize_secret_values(evidence), name="Decision evidence")
        return self._categorization_result

    def _apply_decision(self, request: DecisionRequest, thresholds: dict, evidence: dict) -> str:
        """Return the accepted route label, or "" for Else; raise when the policy says stop."""
        stop = self.evaluation_error_action == "Stop with error"
        try:
            # Never forward the Language Model's API key to a decision provider.
            result = evaluate_decision(
                request,
                model=self.decision_model,
                user_id=self.user_id,
                request_variables=request_variables_of(self),
            )
        except DecisionEvaluationError as exc:
            evidence.update(reason="evaluation_error", error={"category": exc.category, "message": str(exc)})
            if stop:
                raise
            return ""
        except (PermissionError, DecisionConfigurationError) as exc:
            # Always stops; the evidence still records why.
            category = "permission_denied" if isinstance(exc, PermissionError) else "configuration_error"
            evidence.update(reason=category, error={"category": category, "message": str(exc)})
            raise
        evidence["result"] = result.model_dump(exclude_none=True)
        if result.status == "refusal":
            evidence["reason"] = "refusal"
            if stop:
                msg = "The decision provider refused the evaluation."
                raise DecisionEvaluationError(msg, category="refusal")
            return ""
        labels = {option["id"]: option["label"] for option in evidence["options"]}
        if request.kind == "score":
            # From 0, every level's weight on the first route, to 1, all of it on the last, so route
            # minimums read the same whatever the number of routes.
            # Rounded so float error never moves a score off a minimum it sits on.
            score = round(result.score / (len(request.levels) - 1), 12)
            evidence["normalized_score"] = score
            reached = [route_id for route_id, minimum in thresholds.items() if score >= minimum]
            if not reached:
                evidence["reason"] = "below_minimum_score"
                return ""
            # Minimums rise with route order, so the last route reached is the highest tier.
            winner = reached[-1]
        else:
            probabilities = result.probabilities
            if request.kind == "boolean":
                # The first route is Yes and the second No. P(no) is rounded so float error never drops it
                # below a threshold it meets: 1 - 0.33 is 0.6699999999999999.
                yes, no = evidence["options"][0]["id"], evidence["options"][1]["id"]
                probabilities = {yes: result.probability_true, no: round(1 - result.probability_true, 12)}
                evidence["route_probabilities"] = probabilities
            top_probability = max(probabilities.values())
            winners = [option_id for option_id, p in probabilities.items() if p == top_probability]
            if len(winners) != 1:
                evidence["reason"] = "tied_top_probability"
                return ""
            winner = winners[0]
            if top_probability < thresholds[winner]:
                evidence.update(
                    selected_outcome=winner, applied_threshold=thresholds[winner], reason="below_minimum_probability"
                )
                return ""
        evidence.update(
            selected_outcome=winner, applied_threshold=thresholds[winner], reason="accepted", activated_branch=winner
        )
        return labels[winner]

    def _build_artifact(self, result):
        artifact = super()._build_artifact(result)
        if self._decision_evidence is not None:
            artifact["raw"] = {
                "message": artifact["raw"],
                "decision": self._sanitize_secret_values(self._decision_evidence),
            }
            artifact["type"] = "object"
        return artifact

    def _pre_run_setup(self) -> None:
        """Reset per-run routing state before each build.

        Called once per vertex build (before the output methods run), so the categorization
        and branch-exclusion decisions are recomputed fresh on every execution.
        """
        self._matched_category = None
        self._categorization_result = None
        self._excluded_outputs = set()
        self._decision_evidence = None
        # Checked before any model is called, so a mismatch never costs an inference.
        self._route_ids()
        if self._is_decision_mode():
            self._validate_decision_graph()

    def _route_ids(self) -> list[str]:
        """Each route's output name, in route order.

        Rows sent with no IDs at all, such as an API tweak written before route IDs, take this
        router's saved route outputs in order, as their position meant before. The routes must
        match the saved route outputs exactly: a route with no output would reach a branch nothing
        is connected to, and an output with no route would never be switched off.
        """
        rows = getattr(self, "routes", []) or []
        # Components built without a saved node (direct calls) have no outputs to follow or check.
        saved = [name for name in self._outputs_map if _route_number(name)]
        if saved and not any(_route_number(row.get("route_id")) for row in rows):
            route_ids = saved
        else:
            route_ids = [
                row["route_id"] for row in assign_route_ids(rows, getattr(self, "last_route_number", 0) or 0)[0]
            ]
        if self._outputs_map and (len(route_ids) != len(rows) or set(route_ids) != set(saved)):
            msg = "The Smart Router's routes don't match its outputs. Open the flow in the editor to update them."
            raise DecisionConfigurationError(msg)
        return route_ids

    def _deactivate_branches(self, output_names: list[str]) -> None:
        """Deactivate the given output branches so their downstream nodes do not execute.

        Two complementary mechanisms are used (mirroring ConditionalRouterComponent):

        * ``stop()`` marks each branch INACTIVE for the current scheduling pass. It also
          detaches the branch from any shared downstream node's pending-predecessor list,
          so that node can still run from the *selected* branch.
        * ``exclude_branches_conditionally()`` records a *persistent* exclusion. The INACTIVE
          state is reset between scheduling passes, so without this a re-activated branch that
          reconverges on a shared downstream node gets picked up again and executes -- the
          unselected-branch-runs bug this guards against.

        Exclusions accumulate across calls (``process_case`` runs once per connected output,
        plus ``default_response``) so excluding one branch never clears its siblings.
        """
        for name in output_names:
            self.stop(name)
        # The persistent exclusion needs a real vertex/graph. Skip it when the component is
        # exercised without one (e.g. direct unit tests that mock ``stop``).
        if self._vertex is None:
            return
        self._excluded_outputs.update(output_names)
        self._vertex.graph.exclude_branches_conditionally(self._id, sorted(self._excluded_outputs))

    def process_case(self) -> Message:
        """Process all categories using LLM categorization and return message for matching category."""
        # Clear any previous match state (only on first call)
        if self._categorization_result is None:
            self._matched_category = None

        # Get categories and input text
        categories = getattr(self, "routes", [])
        input_text = getattr(self, "input_text", "")

        # Get the cached categorization result (performs LLM call only once)
        categorization = self._get_categorization()

        # Find matching category based on LLM response
        matched_category = None
        for i, category in enumerate(categories):
            route_category = category.get("route_category", "")
            if categorization.lower() == route_category.lower():
                matched_category = i
                self.status = f"MATCH FOUND! Category {i + 1} matched with '{categorization}'"
                break

        if matched_category is not None:
            # Store the matched category for other outputs to check
            self._matched_category = matched_category

            # Deactivate all category outputs except the matched one, plus the default
            # output if present, so only the matched branch continues downstream.
            route_ids = self._route_ids()
            outputs_to_deactivate = [route_id for i, route_id in enumerate(route_ids) if i != matched_category]
            enable_else = getattr(self, "enable_else_output", False)
            if enable_else:
                outputs_to_deactivate.append("default_result")
            self._deactivate_branches(outputs_to_deactivate)

            route_category = categories[matched_category].get("route_category", f"Category {matched_category + 1}")
            self.status = f"Categorized as {route_category}"
            matched_output_name = route_ids[matched_category]
            if self._current_output and self._current_output != matched_output_name:
                return Message(text="")

            # Check if there's an override output (takes precedence over everything)
            override_output = getattr(self, "message", None)
            if (
                override_output
                and hasattr(override_output, "text")
                and override_output.text
                and str(override_output.text).strip()
            ):
                return Message(text=str(override_output.text))
            if override_output and isinstance(override_output, str) and override_output.strip():
                return Message(text=str(override_output))

            # Check if there's a custom output value for this category
            custom_output = categories[matched_category].get("output_value", "")
            # Treat None, empty string, or whitespace as blank
            if custom_output and str(custom_output).strip() and str(custom_output).strip().lower() != "none":
                # Use custom output value
                return Message(text=str(custom_output))
            # Use input as default output
            return Message(text=input_text)
        # No match found: deactivate every category output so none continue downstream.
        # The default/Else output (if enabled) is intentionally left active and handled by
        # default_response.
        self._deactivate_branches(self._route_ids())

        # Check if else output is enabled
        enable_else = getattr(self, "enable_else_output", False)
        if enable_else:
            # The default_response will handle the else case
            self.stop("process_case")
            return Message(text="")
        # No else output, so no output at all
        self.status = "No match found and Else output is disabled"
        return Message(text="")

    def default_response(self) -> Message:
        """Handle the else case when no conditions match."""
        enable_else = getattr(self, "enable_else_output", False)
        if not enable_else:
            self.status = "Else output is disabled"
            return Message(text="")

        categories = getattr(self, "routes", [])
        input_text = getattr(self, "input_text", "")

        # Get the cached categorization result (performs LLM call only if not already done)
        categorization = self._get_categorization()

        # Check if the categorization matches any category
        has_match = False
        for i, category in enumerate(categories):
            route_category = category.get("route_category", "")
            if categorization.lower() == route_category.lower():
                has_match = True
                self.status = f"Match found for '{categorization}' (Category {i + 1}), stopping default_response"
                break

        if has_match:
            # A case matches, so the Else branch must not continue downstream.
            self._deactivate_branches(["default_result"])
            return Message(text="")

        # No case matches, check for override output first, then use input as default
        override_output = getattr(self, "message", None)
        if (
            override_output
            and hasattr(override_output, "text")
            and override_output.text
            and str(override_output.text).strip()
        ):
            self.status = "Routed to Else (no match) - using override output"
            return Message(text=str(override_output.text))
        if override_output and isinstance(override_output, str) and override_output.strip():
            self.status = "Routed to Else (no match) - using override output"
            return Message(text=str(override_output))

        self.status = "Routed to Else (no match) - using input as default"
        return Message(text=input_text)
