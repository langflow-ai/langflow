import re
from collections.abc import Mapping
from math import floor, isfinite
from typing import Any

from lfx.base.models.decisions.runtime import decision_token_usage, evaluate_decision, request_variables_of
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

_MAX_ROUTE_NUMBER = 9999
# Choice and Language Model mode route through the routes table; Score keeps its own levels, so
# switching between them never loses either's rows. Each table numbers its own outputs.
_TABLES = {"routes": ("category", "last_route_number"), "score_levels": ("level", "last_level_number")}
_CUSTOM_PROMPT_INFO = (
    "Additional instructions for LLM-based categorization. "
    "These will be added to the base prompt. "
    "Use {input_text} for the input text and {routes} for the available categories."
)
_CUSTOM_PROMPT_DECISION_INFO = (
    "Not used in Decision Model mode, which has no prompt. Kept so it applies again in Language Model mode."
)
_DECISION_KINDS = {"Choice": "choice", "Boolean": "boolean", "Score": "score"}
# Boolean's fixed outputs, in place of one output per route.
_YES_OUTPUT, _NO_OUTPUT = "yes_result", "no_result"
# What Else receives, which differs only for Score: every Score answer reaches a level.
_ELSE_INFO = {
    "choice": (
        "Include an Else output for cases that don't match any route. Decision Model mode needs it on and "
        "connected: it gets answers that aren't sure enough, and evaluation errors when Evaluation Error "
        "Action is Route to Else."
    ),
    "score": (
        "Include an Else output for cases that don't match any route. Decision Model mode needs it on and "
        "connected. Every Score answer reaches a level, so Else gets only evaluation errors and refusals, "
        "when Evaluation Error Action is Route to Else."
    ),
}
_BOOLEAN_FIELDS = (
    "yes_description",
    "no_description",
    "yes_message",
    "no_message",
    "yes_minimum_probability",
    "no_minimum_probability",
)
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
        'A yes/no question, such as "Is the customer asking for a refund?". A Yes answer goes to the Yes output '
        "and a No answer to the No output."
    ),
    "score": "The question that places the input on the Levels, from lowest to highest.",
}
_ROUTES_INFO = (
    "The routes to choose between. Each needs a Route Name; its Route Description says when it applies, and its "
    "Route Message, if set, is sent in place of the input."
)
_MINIMUM_PROBABILITY_INFO = {
    "choice": (
        "From 0 to 1. The most likely route is used only when its probability is at least this value; otherwise "
        "the message goes to Else. A route can set its own in the Routes table."
    ),
    "boolean": (
        "From 0 to 1. The more likely answer, Yes or No, is used only when its probability is at least this "
        "value; otherwise the message goes to Else. Yes and No can each set their own."
    ),
}


def _route_number(route_id: Any, prefix: str = "category") -> int | None:
    """The number in a valid route ID such as ``category_3_result`` (or ``level_3_result``), or None."""
    match = re.fullmatch(rf"{prefix}_([1-9][0-9]{{0,3}})_result", route_id) if isinstance(route_id, str) else None
    return int(match.group(1)) if match else None


def assign_route_ids(routes: list[dict], last_number: int, prefix: str = "category") -> tuple[list[dict], int]:
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
        number = _route_number(row.get("route_id"), prefix)
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
    keyed = [{**row, "route_id": f"{prefix}_{number}_result"} for row, number in zip(routes, numbers, strict=True)]
    return keyed, highest


class SmartRouterComponent(Component):
    display_name = "Smart Router"
    description = "Routes an input message with a language model or a decision model."
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
                "Choice picks one route. Boolean answers yes or no through Yes and No outputs. Score places the "
                "input on its own ordered Levels. Changing the type replaces the outputs and removes their "
                "connections; Else keeps its own."
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
        MessageTextInput(
            name="yes_description",
            display_name="What Yes Means (Optional)",
            info=(
                "Optional: what a Yes answer means. Some decision models don't accept this; if yours "
                "doesn't, the run stops and asks you to clear it."
            ),
            show=False,
        ),
        MessageTextInput(
            name="no_description",
            display_name="What No Means (Optional)",
            info=(
                "Optional: what a No answer means. Some decision models don't accept this; if yours "
                "doesn't, the run stops and asks you to clear it."
            ),
            show=False,
        ),
        MessageTextInput(
            name="yes_message",
            display_name="Yes Message (Optional)",
            info="Boolean only: the message the Yes output sends. Leave empty to pass the input through.",
            show=False,
        ),
        MessageTextInput(
            name="no_message",
            display_name="No Message (Optional)",
            info="Boolean only: the message the No output sends. Leave empty to pass the input through.",
            show=False,
        ),
        FloatInput(
            name="yes_minimum_probability",
            preserve_empty=True,
            display_name="Yes Minimum Probability (Optional)",
            info=(
                "Boolean only: the probability Yes needs, from 0 to 1, when Yes is the more likely answer. Leave "
                "empty to use Minimum Probability."
            ),
            range_spec=RangeSpec(min=0, max=1, step=0.01),
            show=False,
            advanced=True,
        ),
        FloatInput(
            name="no_minimum_probability",
            preserve_empty=True,
            display_name="No Minimum Probability (Optional)",
            info=(
                "Boolean only: the probability No needs, from 0 to 1, when No is the more likely answer. Leave "
                "empty to use Minimum Probability."
            ),
            range_spec=RangeSpec(min=0, max=1, step=0.01),
            show=False,
            advanced=True,
        ),
        DropdownInput(
            name="evaluation_error_action",
            display_name="Evaluation Error Action",
            options=["Stop with error", "Route to Else"],
            value="Stop with error",
            info=(
                "What to do when the decision model times out, fails or declines to answer: stop the run, or send "
                "the message to Else. A missing or rejected key, or invalid settings, always stop the run."
            ),
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
            info=_ROUTES_INFO,
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
                    "description": "When this route should be used; the model judges the input against it.",
                    "default": "",
                    "edit_mode": EditMode.POPOVER,
                },
                {
                    "name": "output_value",
                    "display_name": "Route Message (Optional)",
                    "type": "str",
                    "description": (
                        "Optional message to send when this route is matched. "
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
                        "Decision Model mode only: the probability this route needs, at least, from 0 to 1. "
                        "Leave empty to use the router's Minimum Probability."
                    ),
                    "edit_mode": EditMode.INLINE,
                    # Language Model mode is the default; update_build_config shows it in Decision Model mode.
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
        TableInput(
            name="score_levels",
            display_name="Levels",
            info=(
                "Score only: levels ordered from lowest to highest, at most 10. The model scores the input from 0 "
                "(the first level) up to one less than the number of levels, and the message goes to the level "
                "that score rounds to. Exactly halfway goes to the higher level."
            ),
            table_schema=[
                {
                    "name": "route_category",
                    "display_name": "Level Name",
                    "type": "str",
                    "description": "Name for the level, shown on its output.",
                    "edit_mode": EditMode.INLINE,
                },
                {
                    "name": "route_description",
                    "display_name": "Level Description",
                    "type": "str",
                    "description": "What this level means; the model places the input against it.",
                    "default": "",
                    "edit_mode": EditMode.POPOVER,
                },
                {
                    "name": "output_value",
                    "display_name": "Level Message (Optional)",
                    "type": "str",
                    "description": (
                        "Optional message to send when this level is chosen. "
                        "Leave empty to pass through the original input text."
                    ),
                    "default": "",
                    "edit_mode": EditMode.POPOVER,
                },
                {
                    "name": "route_id",
                    "display_name": "Level ID",
                    "type": "str",
                    "description": "Set automatically. Keeps this level's connections when other levels change.",
                    "hidden": True,
                    "disable_edit": True,
                },
            ],
            value=[
                {"route_category": "Low", "route_description": "Can wait", "output_value": ""},
                {"route_category": "Medium", "route_description": "Needs attention soon", "output_value": ""},
                {"route_category": "High", "route_description": "Urgent", "output_value": ""},
            ],
            real_time_refresh=True,
            show=False,
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
            info=_ELSE_INFO["choice"],
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
        IntInput(
            name="last_level_number",
            display_name="Last Level Number",
            info="Set automatically: the highest level number assigned, so a deleted level's output is never reused.",
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

    @staticmethod
    def _table(*, decision_mode: bool, kind: str) -> str | None:
        """The table whose rows are this router's outputs: none for Boolean's Yes and No."""
        if decision_mode and kind == "boolean":
            return None
        return "score_levels" if decision_mode and kind == "score" else "routes"

    def _rows_table(self) -> str | None:
        """This router's table, as its saved settings say."""
        return self._table(decision_mode=self._is_decision_mode(), kind=self._decision_kind())

    def _decision_kind(self, kind: Any = None) -> str:
        """``kind``, by default this router's Decision Type, as a request kind; an unknown type stops."""
        if kind is None:
            kind = getattr(self, "decision_kind", "Choice")
        if kind not in _DECISION_KINDS:
            msg = "Unknown decision type."
            raise DecisionConfigurationError(msg)
        return _DECISION_KINDS[kind]

    async def update_frontend_node(self, new_frontend_node: dict, current_frontend_node: dict):
        """Re-apply the saved mode's fields and route IDs after a code update.

        Update rebuilds the node from the class, which shows Language Model mode's fields, and copies only
        values back. Without this a Decision Model router came back with its decision settings hidden, so
        the run dropped them, and routes saved before route IDs stayed without them.
        """
        await super().update_frontend_node(new_frontend_node, current_frontend_node)
        template = new_frontend_node.get("template", {})
        self._show_fields(template, (template.get("routing_mode") or {}).get("value"), "routing_mode")
        return new_frontend_node

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None):
        """Dynamically update build config with user-filtered model options."""
        if self._show_fields(build_config, field_value, field_name):
            return handle_model_input_update(
                self, build_config, field_value, field_name, model_field_name="decision_model"
            )
        return handle_model_input_update(self, build_config, field_value, field_name)

    def _show_fields(self, build_config: dict, field_value: Any, field_name: str | None) -> bool:
        """Show the fields, table and threshold column of the mode and type; return whether it's Decision Model."""
        decision_mode = self._is_decision_mode(field_value if field_name == "routing_mode" else None)
        kind = self._decision_kind(
            field_value if field_name == "decision_kind" else (build_config.get("decision_kind") or {}).get("value")
        )
        for name in ("decision_model", "decision_kind", "decision_question", "evaluation_error_action"):
            if name in build_config:
                build_config[name]["show"] = decision_mode
                build_config[name]["required"] = decision_mode
        if "minimum_probability" in build_config:
            # Score rounds to a level and needs no threshold.
            uses_router_threshold = decision_mode and kind != "score"
            build_config["minimum_probability"].update(
                show=uses_router_threshold,
                required=uses_router_threshold,
                info=_MINIMUM_PROBABILITY_INFO.get(kind, _MINIMUM_PROBABILITY_INFO["choice"]),
            )
        # Boolean replaces the routes with its Yes and No fields; the routes are kept for the other types.
        boolean_mode = decision_mode and kind == "boolean"
        for name in _BOOLEAN_FIELDS:
            if name in build_config:
                build_config[name]["show"] = boolean_mode
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
            build_config["enable_else_output"]["info"] = _ELSE_INFO["score" if kind == "score" else "choice"]
        shown_table = self._table(decision_mode=decision_mode, kind=kind)
        for table, (prefix, counter) in _TABLES.items():
            if table not in build_config:
                continue
            rows_input = build_config[table]
            rows_input["show"] = rows_input["required"] = table == shown_table
            rows = field_value if field_name == table else rows_input.get("value")
            last = (build_config.get(counter) or {}).get("value") or 0
            rows_input["value"], last = assign_route_ids(rows or [], last, prefix)
            if counter in build_config:
                build_config[counter]["value"] = last
        if "routes" in build_config:
            # A route's own threshold only applies in Decision Model mode.
            schema = build_config["routes"].get("table_schema") or []
            for column in schema.get("columns", []) if isinstance(schema, dict) else schema:
                if column.get("name") == "minimum_probability":
                    column["hidden"] = not decision_mode
        return decision_mode

    def update_outputs(self, frontend_node: dict, field_name: str, field_value: Any) -> dict:
        """Create a dynamic output for each category in the categories table."""
        # The update endpoint rebuilds this node from the class, which declares no outputs,
        # so every field refresh must recreate them or the editor drops the route edges.
        frontend_node["outputs"] = []
        template = frontend_node.get("template") or {}

        def current(name: str, *, default: Any) -> Any:
            if field_name == name:
                return field_value
            return (template.get(name) or {}).get("value", getattr(self, name, default))

        table = self._table(
            decision_mode=self._is_decision_mode(current("routing_mode", default="Language Model")),
            kind=self._decision_kind(current("decision_kind", default="Choice")),
        )
        # Switching type swaps the outputs (Yes and No, levels or routes), so the editor drops the old edges.
        if table is None:
            frontend_node["outputs"] = [
                Output(display_name="Yes", name=_YES_OUTPUT, method="process_case", group_outputs=True),
                Output(display_name="No", name=_NO_OUTPUT, method="process_case", group_outputs=True),
            ]
        else:
            # Prefer the template's rows: update_build_config has already given them their IDs.
            prefix, counter = _TABLES[table]
            fallback = field_value if field_name == table else getattr(self, table, [])
            routes_data, _ = assign_route_ids(
                (template.get(table) or {}).get("value", fallback) or [],
                (template.get(counter) or {}).get("value", getattr(self, counter, 0)) or 0,
                prefix,
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
        enable_else = current("enable_else_output", default=False)

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
    def _validate_probability(value: Any, name: str = "Minimum Probability") -> float:
        if value is None or (isinstance(value, str) and not value.strip()):
            msg = f"Enter a {name} from 0 to 1, such as 0.7."
            raise DecisionConfigurationError(msg)
        if isinstance(value, str):
            # Table cells can hold the number as text.
            try:
                value = float(value.strip())
            except ValueError:
                value = None
        if isinstance(value, bool) or not isinstance(value, int | float) or not isfinite(value) or not 0 <= value <= 1:
            msg = f"{name} must be a number from 0 to 1."
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
            msg = "Decision Model mode needs Include Else Output on and its Else output connected."
            raise DecisionConfigurationError(msg)

    def _get_decision_categorization(self) -> str:
        self._validate_decision_graph()
        kind = self._decision_kind()
        # Score rounds to a level and needs no threshold; the other types fall back to the router's.
        threshold = None if kind == "score" else self._validate_probability(self.minimum_probability)
        if self.evaluation_error_action not in {"Stop with error", "Route to Else"}:
            msg = "Unknown evaluation error action."
            raise DecisionConfigurationError(msg)
        if not str(self.decision_question or "").strip():
            msg = "Enter a Decision Question."
            raise DecisionConfigurationError(msg)
        candidates, thresholds = (
            self._boolean_branches(threshold) if kind == "boolean" else self._route_branches(kind, threshold)
        )
        boolean = kind == "boolean"
        request = decision_request(
            kind=kind,
            question=self.decision_question,
            context=self.input_text,
            options=candidates if kind == "choice" else (),
            levels=candidates if kind == "score" else (),
            yes_description=candidates[0]["description"] if boolean else "",
            no_description=candidates[1]["description"] if boolean else "",
        )
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

    def _boolean_branches(self, threshold: float) -> tuple[list[dict], dict]:
        """Boolean's Yes and No outputs, what each answer means, and the probability each needs."""
        candidates = [
            {"id": _YES_OUTPUT, "label": "Yes", "description": self.yes_description or ""},
            {"id": _NO_OUTPUT, "label": "No", "description": self.no_description or ""},
        ]
        thresholds = {}
        for candidate, own in zip(candidates, (self.yes_minimum_probability, self.no_minimum_probability), strict=True):
            blank = own is None or not str(own).strip()
            name = f"{candidate['label']} Minimum Probability"
            thresholds[candidate["id"]] = threshold if blank else self._validate_probability(own, name)
        return candidates, thresholds

    def _route_branches(self, kind: str, threshold: float | None) -> tuple[list[dict], dict]:
        """One candidate per route or level, and the probability each Choice route needs; levels need none."""
        rows = getattr(self, self._rows_table(), []) or []
        noun, column = ("level", "Level Name") if kind == "score" else ("route", "Route Name")
        if len(rows) < 2:  # noqa: PLR2004 - a choice needs at least two options
            msg = f"Add at least two {noun}s."
            raise DecisionConfigurationError(msg)
        names = [str(row.get("route_category") or "").strip() for row in rows]
        if not all(names):
            msg = f"Every {noun} needs a {column}."
            raise DecisionConfigurationError(msg)
        seen: set[str] = set()
        for name in names:
            if name.casefold() in seen:
                msg = f"Every {noun} needs a different {column}; {name!r} is used twice."
                raise DecisionConfigurationError(msg)
            seen.add(name.casefold())
        candidates = [
            {"id": route_id, "label": row["route_category"], "description": row.get("route_description") or ""}
            for route_id, row in zip(self._route_ids(), rows, strict=True)
        ]
        thresholds = {}
        if kind == "choice":
            for candidate, row, name in zip(candidates, rows, names, strict=True):
                own = row.get("minimum_probability")
                blank = own is None or not str(own).strip()
                minimum = f"Minimum Probability for {name!r}"
                thresholds[candidate["id"]] = threshold if blank else self._validate_probability(own, minimum)
        return candidates, thresholds

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
        # A refusal is billed too, so its tokens count before the policy below decides where it goes.
        self._token_usage = decision_token_usage(result)
        evidence["result"] = result.model_dump(exclude_none=True)
        if result.status == "refusal":
            evidence["reason"] = "refusal"
            if stop:
                msg = (
                    f"{result.provider} declined to answer. Rephrase the Decision Question or the input, or set "
                    "Evaluation Error Action to Route to Else."
                )
                raise DecisionEvaluationError(msg, category="refusal")
            return ""
        labels = {option["id"]: option["label"] for option in evidence["options"]}
        if request.kind == "score":
            # The level the probability-weighted score rounds to, as TypeSafe suggests for one outcome. A
            # score exactly between two levels takes the higher one; Python's round() would take the even one.
            winner = request.levels[min(floor(result.score + 0.5), len(request.levels) - 1)].id
            evidence.update(reason="accepted", activated_branch=winner)
            return labels[winner]
        probabilities = result.probabilities
        if request.kind == "boolean":
            # The first candidate is Yes and the second No. P(no) is rounded so float error never drops it
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
        # The top route the threshold is checked against; activated_branch says where the message went.
        evidence.update(top_outcome=winner, applied_threshold=thresholds[winner])
        if top_probability < thresholds[winner]:
            evidence["reason"] = "below_minimum_probability"
            return ""
        evidence.update(reason="accepted", activated_branch=winner)
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
        self._token_usage = None
        # Checked before any model is called, so a mismatch never costs an inference. Boolean's
        # Yes and No outputs don't come from a table, but must be the saved ones: a tweak that switches
        # a routes flow to Boolean would otherwise run every route branch.
        if self._rows_table() is not None:
            self._route_ids()
        elif self._outputs_map and set(self._outputs_map) - {"default_result"} != {_YES_OUTPUT, _NO_OUTPUT}:
            msg = (
                "The Smart Router's outputs don't match its Decision Type. Open the flow in the editor to update them."
            )
            raise DecisionConfigurationError(msg)
        if self._is_decision_mode():
            self._validate_decision_graph()

    def _route_ids(self) -> list[str]:
        """Each route's (or Score level's) output name, in table order.

        Rows sent with no IDs at all, such as an API tweak written before route IDs, take this
        router's saved route outputs in order, as their position meant before. The routes must
        match the saved route outputs exactly: a route with no output would reach a branch nothing
        is connected to, and an output with no route would never be switched off.
        """
        table = self._rows_table()
        prefix, counter = _TABLES[table]
        rows = getattr(self, table, []) or []
        # Components built without a saved node (direct calls) have no outputs to follow or check.
        saved = [name for name in self._outputs_map if _route_number(name, prefix)]
        if saved and not any(_route_number(row.get("route_id"), prefix) for row in rows):
            route_ids = saved
        else:
            route_ids = [row["route_id"] for row in assign_route_ids(rows, getattr(self, counter, 0) or 0, prefix)[0]]
        if self._outputs_map and (len(route_ids) != len(rows) or set(route_ids) != set(saved)):
            things = "levels" if table == "score_levels" else "routes"
            msg = f"The Smart Router's {things} don't match its outputs. Open the flow in the editor to update them."
            raise DecisionConfigurationError(msg)
        return route_ids

    def _branches(self) -> list[tuple[str, str, Any]]:
        """Each branch output as (output name, label it is chosen by, its own message), in output order."""
        table = self._rows_table()
        if table is None:
            return [(_YES_OUTPUT, "Yes", self.yes_message), (_NO_OUTPUT, "No", self.no_message)]
        rows = getattr(self, table, []) or []
        return [
            (route_id, row.get("route_category") or "", row.get("output_value", ""))
            for route_id, row in zip(self._route_ids(), rows, strict=True)
        ]

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

        # Get branches and input text
        branches = self._branches()
        input_text = getattr(self, "input_text", "")

        # Get the cached categorization result (performs LLM call only once)
        categorization = self._get_categorization()

        # Find matching category based on LLM response
        matched_category = None
        for i, (_, route_category, _) in enumerate(branches):
            if categorization.lower() == route_category.lower():
                matched_category = i
                self.status = f"MATCH FOUND! Category {i + 1} matched with '{categorization}'"
                break

        if matched_category is not None:
            # Store the matched category for other outputs to check
            self._matched_category = matched_category

            # Deactivate all category outputs except the matched one, plus the default
            # output if present, so only the matched branch continues downstream.
            route_ids = [output_name for output_name, _, _ in branches]
            outputs_to_deactivate = [route_id for i, route_id in enumerate(route_ids) if i != matched_category]
            enable_else = getattr(self, "enable_else_output", False)
            if enable_else:
                outputs_to_deactivate.append("default_result")
            self._deactivate_branches(outputs_to_deactivate)

            route_category = branches[matched_category][1] or f"Category {matched_category + 1}"
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
            custom_output = branches[matched_category][2]
            # Treat None, empty string, or whitespace as blank
            if custom_output and str(custom_output).strip() and str(custom_output).strip().lower() != "none":
                # Use custom output value
                return Message(text=str(custom_output))
            # Use input as default output
            return Message(text=input_text)
        # No match found: deactivate every category output so none continue downstream.
        # The default/Else output (if enabled) is intentionally left active and handled by
        # default_response.
        self._deactivate_branches([output_name for output_name, _, _ in branches])

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

        input_text = getattr(self, "input_text", "")

        # Get the cached categorization result (performs LLM call only if not already done)
        categorization = self._get_categorization()

        # Check if the categorization matches any category
        has_match = False
        for i, (_, route_category, _) in enumerate(self._branches()):
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
