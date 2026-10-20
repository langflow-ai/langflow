import re
from collections.abc import Mapping
from math import isfinite
from typing import Any

from pydantic import ValidationError

from lfx.base.models.decisions.runtime import evaluate_decision, request_variables_of
from lfx.base.models.decisions.schema import (
    DecisionConfigurationError,
    DecisionEvaluationError,
    DecisionOption,
    DecisionRequest,
    validation_summary,
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
        route_id = row.get("route_id")
        match = _ROUTE_ID.fullmatch(route_id) if isinstance(route_id, str) else None
        number = int(match.group(1)) if match else None
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
        MultilineInput(
            name="decision_question",
            display_name="Decision Question",
            value="Which route best matches the input?",
            info="Instructions for the decision model. Additional Instructions apply only to Language Model mode.",
            show=False,
        ),
        FloatInput(
            name="minimum_probability",
            preserve_empty=True,
            display_name="Minimum Probability",
            info=(
                "Required in decision mode, from 0 to 1. The top route is chosen only when its probability is at "
                "least this value; otherwise the message goes to Else. This is the route's probability, not the "
                "provider's confidence score. A route can set its own threshold in the Routes table."
            ),
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
            info=(
                "Define the categories for routing. Each row should have a route/category name "
                "and optionally a custom output value."
            ),
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
        mode = effective.get("routing_mode", getattr(self, "routing_mode", "Language Model"))
        if mode not in {"Language Model", "Decision Model"}:
            msg = "Unknown routing mode."
            raise DecisionConfigurationError(msg)
        effective.pop("model" if mode == "Decision Model" else "decision_model", None)
        return super()._selected_model_provider_policy_ids(effective)

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None):
        """Dynamically update build config with user-filtered model options."""
        decision_mode = (
            field_value if field_name == "routing_mode" else getattr(self, "routing_mode", "Language Model")
        ) == "Decision Model"
        for name in ("decision_model", "decision_question", "minimum_probability", "evaluation_error_action"):
            if name in build_config:
                build_config[name]["show"] = decision_mode
                build_config[name]["required"] = decision_mode
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
            rows = field_value if field_name == "routes" else build_config["routes"].get("value")
            last = (build_config.get("last_route_number") or {}).get("value") or 0
            build_config["routes"]["value"], last = assign_route_ids(rows or [], last)
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

        if getattr(self, "routing_mode", "Language Model") == "Decision Model":
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
    def _validate_probability(value: Any) -> float:
        if isinstance(value, str):
            # Table cells can hold the number as text.
            try:
                value = float(value.strip())
            except ValueError:
                value = None
        if isinstance(value, bool) or not isinstance(value, int | float) or not isfinite(value) or not 0 <= value <= 1:
            msg = "Minimum probability must be a number between 0 and 1."
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
        threshold = self._validate_probability(self.minimum_probability)
        if self.evaluation_error_action not in {"Stop with error", "Route to Else"}:
            msg = "Unknown evaluation error action."
            raise DecisionConfigurationError(msg)
        if len(self.routes) < 2:  # noqa: PLR2004 - a choice needs at least two options
            msg = "Decision mode needs at least two routes; uncertain results already go to Else."
            raise DecisionConfigurationError(msg)
        if any(not str(row.get("route_category") or "").strip() for row in self.routes):
            msg = "Every route needs a name in decision mode."
            raise DecisionConfigurationError(msg)
        try:
            options = tuple(
                DecisionOption(
                    id=route_id,
                    label=row["route_category"],
                    description=row.get("route_description") or "",
                )
                for route_id, row in zip(self._route_ids(), self.routes, strict=True)
            )
            request = DecisionRequest(
                kind="choice", question=self.decision_question, context=self.input_text, options=options
            )
        except ValidationError as exc:
            raise DecisionConfigurationError(validation_summary(exc)) from None
        thresholds = {
            option.id: (
                threshold
                if row.get("minimum_probability") is None or not str(row["minimum_probability"]).strip()
                else self._validate_probability(row["minimum_probability"])
            )
            for option, row in zip(options, self.routes, strict=True)
        }
        evidence = {
            "options": [option.model_dump() for option in options],
            "minimum_probability": threshold,
            "route_thresholds": thresholds,
            "activated_branch": None,
            "error_action": self.evaluation_error_action,
        }
        self._decision_evidence = evidence
        try:
            self._categorization_result = self._apply_decision(request, options, thresholds, evidence)
        finally:
            # Any exception leaves the result unset, so a stopped build never activates Else.
            if self._categorization_result == "":
                evidence["activated_branch"] = "default_result"
            self.log(self._sanitize_secret_values(evidence), name="Decision evidence")
        return self._categorization_result

    def _apply_decision(
        self, request: DecisionRequest, options: tuple[DecisionOption, ...], thresholds: dict, evidence: dict
    ) -> str:
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
        top_probability = max(result.probabilities.values())
        winners = [option_id for option_id, p in result.probabilities.items() if p == top_probability]
        if len(winners) != 1:
            evidence["reason"] = "tied_top_probability"
            return ""
        winner = winners[0]
        evidence.update(selected_outcome=winner, applied_threshold=thresholds[winner])
        if top_probability < thresholds[winner]:
            evidence["reason"] = "below_minimum_probability"
            return ""
        evidence.update(reason="accepted", activated_branch=winner)
        return next(option.label for option in options if option.id == winner)

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
        mode = getattr(self, "routing_mode", "Language Model")
        if mode not in {"Language Model", "Decision Model"}:
            msg = "Unknown routing mode."
            raise DecisionConfigurationError(msg)
        if mode == "Decision Model":
            self._validate_decision_graph()

    def _route_ids(self) -> list[str]:
        """Each route's output name, in route order."""
        routes, _ = assign_route_ids(getattr(self, "routes", []) or [], getattr(self, "last_route_number", 0) or 0)
        return [row["route_id"] for row in routes]

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
