import json
from copy import deepcopy

from pydantic import ValidationError

from lfx.base.models.decisions.runtime import decision_token_usage, evaluate_decision, request_variables_of
from lfx.base.models.decisions.schema import (
    DecisionBatchRequest,
    DecisionConfigurationError,
    decision_request,
    validation_summary,
)
from lfx.base.models.unified_models import handle_model_input_update
from lfx.custom.custom_component.component import Component
from lfx.io import (
    DropdownInput,
    FloatInput,
    HandleInput,
    MessageTextInput,
    ModelInput,
    MultilineInput,
    Output,
    TableInput,
)
from lfx.schema.data import Data
from lfx.schema.table import EditMode

_KINDS = ("Choice", "Boolean", "Score")
_DEFAULT_CANDIDATES = {
    "Choice": [
        {"id": "a", "label": "Option A", "description": ""},
        {"id": "b", "label": "Option B", "description": ""},
    ],
    "Score": [
        {"id": "low", "label": "Low", "description": ""},
        {"id": "medium", "label": "Medium", "description": ""},
        {"id": "high", "label": "High", "description": ""},
    ],
}
# The table's name and help follow the Decision Type.
_TABLE = {
    "Choice": (
        "Options",
        "The options to choose between, 2 to 255. ID is a short unique key the result uses, such as refund; "
        "Label is the name the model reads.",
    ),
    "Score": (
        "Levels",
        "Levels ordered from lowest to highest, 2 to 10. The model scores the input from 0 (the first level) up "
        "to one less than the number of levels. ID is a short unique key the result uses; Label is the name the "
        "model reads.",
    ),
}
_TABLE_SCHEMA = [
    {
        "name": "id",
        "display_name": "ID",
        "type": "str",
        "description": "A short unique key, such as refund. The result uses it.",
        "edit_mode": EditMode.INLINE,
    },
    {
        "name": "label",
        "display_name": "Label",
        "type": "str",
        "description": "The name the model reads. Labels must differ, ignoring case.",
        "edit_mode": EditMode.INLINE,
    },
    {
        "name": "description",
        "display_name": "Description",
        "type": "str",
        "description": "Optional: more about when this one applies.",
        "edit_mode": EditMode.POPOVER,
        "default": "",
    },
]

_QUESTION_ID_COLUMN = {
    "name": "question_id",
    "display_name": "Question ID",
    "type": "str",
    "edit_mode": EditMode.INLINE,
    "description": "The ID of the question these options or levels belong to.",
}
_QUESTIONS_SCHEMA = [
    {"name": "id", "display_name": "ID", "type": "str", "edit_mode": EditMode.INLINE},
    {"name": "kind", "display_name": "Type", "type": "str", "options": list(_KINDS), "default": "Boolean"},
    {"name": "question", "display_name": "Question", "type": "str"},
    {"name": "yes_description", "display_name": "What Yes Means", "type": "str", "default": ""},
    {"name": "no_description", "display_name": "What No Means", "type": "str", "default": ""},
]

# What an agent learns about this component when it is a tool.
_RESULT_INFO = (
    "Answers the configured questions about the context and returns JSON. Multiple questions return an answers "
    "object keyed by question ID, with shared usage counted once. Choice gives "
    "probabilities by option ID and, when the provider names one, selected_option (otherwise take the most "
    "probable option); Boolean gives probability_true, the "
    "probability the answer is yes, from 0 to 1; Score gives score, from 0 (the first level) up to one less than "
    "the number of levels, and probabilities by level ID. confidence is the provider's own measure, not an "
    "option's probability."
)

# Follow-ups, deferred until there is demand:
# - Images: TypeSafe `assets` behind its TypeSafe-Danger-Zone-Images header, Perplexity image parts
#   in `state`, OpenAI image inputs. Needs size limits and SSRF checks for each format.
# - Pinned model versions, such as pplx-decider-v1.2: policy allows models by name, so each version
#   needs its own catalog and policy entry.


class DecisionModelComponent(Component):
    """Evaluates named judgments through the same runtime as the Smart Router."""

    display_name = "Decision Model"
    description = "Evaluate one or more choices, probabilities, or ordered scores"
    name = "DecisionModel"
    icon = "Split"

    inputs = [
        ModelInput(
            model_type="decision", name="model", display_name="Decision Model", required=True, real_time_refresh=True
        ),
        DropdownInput(
            name="question_mode",
            display_name="Questions Mode",
            options=["Single", "Multiple", "JSON"],
            value="Single",
            real_time_refresh=True,
            info="Use one question, edit several named questions, or paste Questions JSON. All share the same context.",
        ),
        TableInput(
            name="questions",
            display_name="Questions",
            input_types=[],
            value=[],
            show=False,
            table_schema=_QUESTIONS_SCHEMA,
            info="One row per question, with a unique ID and its own type. Boolean outcome descriptions are optional. "
            "Questions are sent together; grouping can affect provider results and billing.",
        ),
        TableInput(
            name="question_options",
            display_name="Choice Options",
            input_types=[],
            value=[],
            show=False,
            table_schema=[_QUESTION_ID_COLUMN, *_TABLE_SCHEMA],
            info="Options for Choice questions. Match Question ID to a row in Questions. "
            "Add at least two per question.",
        ),
        TableInput(
            name="question_levels",
            display_name="Score Levels",
            input_types=[],
            value=[],
            show=False,
            table_schema=[_QUESTION_ID_COLUMN, *_TABLE_SCHEMA],
            info="Levels for Score questions, lowest first. Match Question ID to a row in Questions. "
            "Add at least two per question.",
        ),
        MultilineInput(
            name="questions_json",
            display_name="Questions JSON",
            advanced=True,
            show=False,
            value="",
            info="In JSON mode, paste an object keyed by question ID. Each value uses kind (choice, boolean, score), "
            "question, and options or levels as arrays of {id, label, description}. Boolean descriptions are optional. "
            'Example: {"urgent":{"kind":"boolean","question":"Is this urgent?"}}. '
            "This replaces the tables for this run; their values are preserved.",
        ),
        DropdownInput(
            name="kind",
            display_name="Decision Type",
            options=list(_KINDS),
            value="Choice",
            info="Choice picks one option. Boolean answers yes or no. Score places the input on ordered levels.",
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="context",
            display_name="Context",
            info="The text the question is about, such as a message or a document.",
            tool_mode=True,
        ),
        MessageTextInput(
            name="question",
            display_name="Question",
            info='What to decide about the Context, such as "Which team should handle this message?"',
            required=True,
        ),
        TableInput(
            name="candidates",
            display_name=_TABLE["Choice"][0],
            # Options are typed in, not connected: connected rows arrive with NaN cells and number IDs.
            input_types=[],
            value=[row.copy() for row in _DEFAULT_CANDIDATES["Choice"]],
            info=_TABLE["Choice"][1],
            table_schema=_TABLE_SCHEMA,
        ),
        TableInput(
            name="levels",
            display_name=_TABLE["Score"][0],
            input_types=[],
            value=[row.copy() for row in _DEFAULT_CANDIDATES["Score"]],
            info=_TABLE["Score"][1],
            table_schema=_TABLE_SCHEMA,
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
            advanced=True,
        ),
        MessageTextInput(
            name="no_description",
            display_name="What No Means (Optional)",
            info=(
                "Optional: what a No answer means. Some decision models don't accept this; if yours "
                "doesn't, the run stops and asks you to clear it."
            ),
            show=False,
            advanced=True,
        ),
        HandleInput(
            name="structured_context",
            display_name="Structured Context",
            info=(
                "Optional: JSON to judge in place of Context, such as a record from another component. "
                "Use Context or Structured Context, not both."
            ),
            input_types=["Data", "JSON"],
            advanced=True,
        ),
        FloatInput(
            name="timeout",
            display_name="Timeout (seconds)",
            info="How long to wait for the decision model: more than 0 and at most 300 seconds.",
            value=60,
            advanced=True,
        ),
    ]
    outputs = [Output(name="result", display_name="Decision Result", method="evaluate", info=_RESULT_INFO)]

    def _context(self) -> str | dict:
        """Context as text, or Structured Context as JSON; exactly one of them."""
        text = str(self.context or "").strip()
        structured = self.structured_context
        # An unconnected handle holds an empty string.
        connected = structured not in (None, "")
        if isinstance(structured, Data):
            structured = structured.data
        # Empty JSON gives the model nothing to judge.
        if not structured:
            structured = None
        if structured is None:
            if connected or not text:
                msg = (
                    "Structured Context is empty. Give the component it comes from at least one field, or use Context."
                    if connected
                    else "Enter a Context, or connect a Structured Context."
                )
                raise DecisionConfigurationError(msg)
            return self.context
        if text:
            msg = "Use Context or Structured Context, not both."
            raise DecisionConfigurationError(msg)
        return structured

    def _batch_request(self, context: str | dict) -> DecisionBatchRequest:
        if self.question_mode == "JSON":

            def unique_keys(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        msg = "Questions JSON contains a duplicate key. Give every question and field a unique key."
                        raise DecisionConfigurationError(msg)
                    result[key] = value
                return result

            try:
                questions = json.loads(self.questions_json or "", object_pairs_hook=unique_keys)
            except (ValueError, TypeError) as exc:
                if isinstance(exc, DecisionConfigurationError):
                    raise
                msg = "Questions JSON must be a valid JSON object keyed by question ID."
                raise DecisionConfigurationError(msg) from None
        else:
            questions = {}
            for row in self.questions or []:
                if not isinstance(row, dict):
                    msg = "Each Questions row must be an object."
                    raise DecisionConfigurationError(msg)
                name = row.get("id")
                if not isinstance(name, str) or not name.strip():
                    msg = "Every Questions row needs an ID."
                    raise DecisionConfigurationError(msg)
                if name in questions:
                    msg = "Questions must have unique IDs."
                    raise DecisionConfigurationError(msg)
                question = {key: value for key, value in row.items() if key != "id"}
                kind = question.get("kind")
                if kind not in _KINDS:
                    msg = "Each question needs a Type: Choice, Boolean or Score."
                    raise DecisionConfigurationError(msg)
                question["kind"] = kind.lower()
                questions[name] = question
            for rows, field, kind in (
                (self.question_options, "options", "choice"),
                (self.question_levels, "levels", "score"),
            ):
                for row in rows or []:
                    name = row.get("question_id") if isinstance(row, dict) else None
                    if not isinstance(name, str) or name not in questions or questions[name]["kind"] != kind:
                        msg = f"Each {field} row must reference a {kind.title()} question's ID."
                        raise DecisionConfigurationError(msg)
                    questions[name].setdefault(field, []).append(
                        {key: value for key, value in row.items() if key != "question_id"}
                    )
        try:
            return DecisionBatchRequest(context=context, questions=questions)
        except ValidationError as exc:
            msg = f"Check Questions: {validation_summary(exc)}"
            raise DecisionConfigurationError(msg) from None

    def _request(self):
        context = self._context()
        if self.question_mode in {"Multiple", "JSON"}:
            return self._batch_request(context)
        if self.question_mode != "Single":
            msg = "Pick a Questions Mode: Single, Multiple or JSON."
            raise DecisionConfigurationError(msg)
        # A tweak can send anything here; the dropdown only offers these three.
        if self.kind not in _KINDS:
            msg = "Pick a Decision Type: Choice, Boolean or Score."
            raise DecisionConfigurationError(msg)
        kind = self.kind.lower()
        boolean = kind == "boolean"
        return decision_request(
            kind=kind,
            question=self.question,
            context=context,
            options=self.candidates if kind == "choice" else (),
            levels=self.levels if kind == "score" else (),
            # Hidden for other types, so a value left from Boolean never applies to them.
            yes_description=(self.yes_description or "") if boolean else "",
            no_description=(self.no_description or "") if boolean else "",
        )

    def evaluate(self) -> Data:
        request = self._request()
        result = evaluate_decision(
            request,
            model=self.model,
            user_id=self.user_id,
            request_variables=request_variables_of(self),
            timeout=self.timeout,
        )
        self._token_usage = decision_token_usage(result)
        # Only what this decision returned and asked: no empty fields from the other types.
        data = Data(
            data={
                **result.model_dump(mode="json", exclude_none=True),
                "request": request.model_dump(mode="json", exclude={"context"}, exclude_defaults=True),
            }
        )
        self.status = data
        return data

    async def update_frontend_node(self, new_frontend_node: dict, current_frontend_node: dict):
        """Re-apply the saved Decision Type's fields after a code update.

        Update rebuilds the node from the class, which shows Choice's fields, and copies only values back.
        Without this a Boolean node came back with What Yes Means and What No Means hidden, so the run
        dropped them.
        """
        await super().update_frontend_node(new_frontend_node, current_frontend_node)
        template = new_frontend_node.get("template", {})
        saved_template = current_frontend_node.get("template", {})
        if "levels" not in saved_template and (saved_template.get("kind") or {}).get("value") == "Score":
            # Older Score nodes stored their rubric in the shared candidates field.
            template["levels"]["value"] = deepcopy(saved_template["candidates"]["value"])
            template["candidates"]["value"] = deepcopy(_DEFAULT_CANDIDATES["Choice"])
        self._show_fields(template, (template.get("kind") or {}).get("value", "Choice"))
        return new_frontend_node

    def update_build_config(self, build_config: dict, field_value, field_name: str | None = None) -> dict:
        config = handle_model_input_update(self, build_config, field_value, field_name)
        if field_name == "question_mode":
            config["question_mode"]["value"] = field_value
        self._show_fields(
            config, field_value if field_name == "kind" else config.get("kind", {}).get("value", "Choice")
        )
        return config

    @staticmethod
    def _show_fields(config: dict, kind: str) -> None:
        """Show only the active type's inputs without modifying either table's values."""
        mode = config.get("question_mode", {}).get("value", "Single")
        single = mode == "Single"
        for name in ("kind", "question"):
            if name in config:
                config[name]["show"] = single
        if "question" in config:
            config["question"]["required"] = single
        for name in ("questions", "question_options", "question_levels"):
            if name in config:
                config[name]["show"] = mode == "Multiple"
        if "questions_json" in config:
            config["questions_json"]["show"] = mode == "JSON"
            config["questions_json"]["advanced"] = mode != "JSON"
        config["candidates"]["show"] = single and kind == "Choice"
        config["levels"]["show"] = single and kind == "Score"
        for name in ("yes_description", "no_description"):
            if name in config:
                config[name]["show"] = single and kind == "Boolean"
