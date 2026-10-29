import json
from copy import deepcopy

from pydantic import ValidationError

from lfx.base.models.decisions.providers import unique_json_object
from lfx.base.models.decisions.runtime import decision_token_usage, evaluate_decision, request_variables_of
from lfx.base.models.decisions.schema import (
    DecisionBatchRequest,
    DecisionConfigurationError,
    DecisionQuestion,
    configuration_summary,
    decision_request,
    validation_summary,
)
from lfx.base.models.unified_models import handle_model_input_update
from lfx.custom.custom_component.component import Component
from lfx.io import (
    DecisionQuestionsInput,
    FloatInput,
    HandleInput,
    MessageTextInput,
    ModelInput,
    MultilineInput,
    Output,
    TabInput,
)
from lfx.schema.data import Data
from lfx.schema.table import EditMode

_KINDS = ("Choice", "Boolean", "Score")
_FORM, _JSON = "Form", "JSON"
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
# Text fields a node held before the question list, which could be bound to a global variable.
_LEGACY_LABELS = {"question": "Question", "yes_description": "What Yes Means", "no_description": "What No Means"}
# What Add question appends; a node starts with one.
_NEW_QUESTION = {
    "name": "",
    "kind": "Choice",
    "question": "",
    "options": [
        {"id": "a", "label": "Option A", "description": ""},
        {"id": "b", "label": "Option B", "description": ""},
    ],
    "levels": [
        {"id": "low", "label": "Low", "description": ""},
        {"id": "medium", "label": "Medium", "description": ""},
        {"id": "high", "label": "High", "description": ""},
    ],
    "yes_description": "",
    "no_description": "",
}

# What an agent learns about this component when it is a tool.
_RESULT_INFO = (
    "Answers the configured questions about the context and returns JSON. Several questions return an answers "
    "object keyed by question name, with shared usage counted once. Choice gives "
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
        TabInput(
            name="question_mode",
            display_name="Questions Mode",
            options=[_FORM, _JSON],
            value=_FORM,
            real_time_refresh=True,
            info="Fill in the questions here, or paste Questions JSON. All questions share the same Context.",
        ),
        MultilineInput(
            name="questions_json",
            display_name="Questions JSON",
            advanced=True,
            show=False,
            value="",
            info="In JSON mode, paste an object keyed by question name. Each value uses kind (choice, boolean, "
            "score), question, and options or levels as arrays of {id, label, description}. Boolean descriptions "
            'are optional. Example: {"urgent":{"kind":"boolean","question":"Is this urgent?"}}. '
            "This replaces the form for this run; its values are preserved.",
        ),
        MessageTextInput(
            name="context",
            display_name="Context",
            info="The text the questions are about, such as a message or a document.",
            tool_mode=True,
        ),
        DecisionQuestionsInput(
            name="questions",
            display_name="Questions",
            value=[deepcopy(_NEW_QUESTION)],
            new_question=_NEW_QUESTION,
            table_schema=_TABLE_SCHEMA,
            info="Each question has its own Decision Type: Choice picks one option, Boolean answers yes or no, and "
            "Score places the input on ordered levels. With more than one question, they are sent in one call and "
            "the result holds each answer under its Name, which defaults to q1, q2 and so on.",
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

    def _json_request(self, context: str | dict) -> DecisionBatchRequest:
        try:
            questions = json.loads(self.questions_json or "", object_pairs_hook=unique_json_object)
        except (ValueError, TypeError) as exc:
            msg = f"Questions JSON must be a valid JSON object keyed by question name: {exc}"
            raise DecisionConfigurationError(msg) from None
        try:
            return DecisionBatchRequest(context=context, questions=questions)
        except ValidationError as exc:
            msg = f"Check Questions: {validation_summary(exc)}"
            raise DecisionConfigurationError(msg) from None

    @staticmethod
    def _question_fields(item, number: int) -> dict:
        """One question's fields, only those its Decision Type uses."""
        # A tweak can send anything here; the editor only offers these three types.
        kind = item.get("kind") if isinstance(item, dict) else None
        if kind not in _KINDS:
            msg = f"Pick a Decision Type for Question {number}: Choice, Boolean or Score."
            raise DecisionConfigurationError(msg)
        kind = kind.lower()
        boolean = kind == "boolean"
        # A migrated field still holding the name of the global variable it was bound to; see _legacy_question.
        for field, variable in (item.get("global_variables") or {}).items():
            if (field == "question" or boolean) and item.get(field) == variable:
                msg = (
                    f"Question {number}'s {_LEGACY_LABELS.get(field, field)} was read from the global variable "
                    f"{variable!r}, which question cards can't use. Type the text into the card, or clear it."
                )
                raise DecisionConfigurationError(msg)
        return {
            "kind": kind,
            "question": item.get("question"),
            "options": (item.get("options") or ()) if kind == "choice" else (),
            "levels": (item.get("levels") or ()) if kind == "score" else (),
            # Ignored for other types, so a value left from Boolean never applies to them.
            "yes_description": (item.get("yes_description") or "") if boolean else "",
            "no_description": (item.get("no_description") or "") if boolean else "",
        }

    def _request(self):
        context = self._context()
        if self.question_mode == _JSON:
            return self._json_request(context)
        if self.question_mode != _FORM:
            msg = "Pick a Questions Mode: Form or JSON."
            raise DecisionConfigurationError(msg)
        items = self.questions
        if not isinstance(items, list) or not items:
            msg = "Add a question."
            raise DecisionConfigurationError(msg)
        if len(items) == 1:
            return decision_request(context=context, **self._question_fields(items[0], 1))
        questions = {}
        for number, item in enumerate(items, start=1):
            fields = self._question_fields(item, number)
            name = str(item.get("name") or "").strip() or f"q{number}"
            if name in questions:
                msg = f"Two questions are named {name!r}. Give each question a different Name."
                raise DecisionConfigurationError(msg)
            try:
                questions[name] = DecisionQuestion(**fields)
            except ValidationError as exc:
                msg = f"Question {number}: {configuration_summary(exc)}"
                raise DecisionConfigurationError(msg) from None
        try:
            return DecisionBatchRequest(context=context, questions=questions)
        except ValidationError as exc:
            raise DecisionConfigurationError(configuration_summary(exc)) from None

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
        """Carry a node saved before the question list over to it, then show the saved mode's fields.

        Update rebuilds the node from the class and copies back only values whose field names match.
        """
        await super().update_frontend_node(new_frontend_node, current_frontend_node)
        template = new_frontend_node.get("template", {})
        saved = current_frontend_node.get("template", {})
        if (saved.get("questions") or {}).get("type") != "decision_questions":
            template["questions"]["value"] = (
                [_legacy_question(saved)] if "question" in saved else [deepcopy(_NEW_QUESTION)]
            )
        if template["question_mode"]["value"] not in {_FORM, _JSON}:
            template["question_mode"]["value"] = _FORM
        self._show_fields(template)
        return new_frontend_node

    def update_build_config(self, build_config: dict, field_value, field_name: str | None = None) -> dict:
        config = handle_model_input_update(self, build_config, field_value, field_name)
        if field_name == "question_mode":
            config["question_mode"]["value"] = field_value
        self._show_fields(config)
        return config

    @staticmethod
    def _show_fields(config: dict) -> None:
        """Show the question list in Form mode and Questions JSON in JSON mode, keeping both values."""
        form = config.get("question_mode", {}).get("value", _FORM) != _JSON
        if "questions" in config:
            config["questions"]["show"] = form
        if "questions_json" in config:
            config["questions_json"]["show"] = not form
            config["questions_json"]["advanced"] = form


def _legacy_question(saved: dict) -> dict:
    """The one question a node held in separate fields before the question list.

    A question card has no global variables, so a field bound to one keeps the variable's name and
    records the binding; the run refuses it until the card holds real text.
    """

    def value(name: str, default):
        return deepcopy((saved.get(name) or {}).get("value", default))

    bound = {
        name: value(name, "")
        for name in _LEGACY_LABELS
        if (saved.get(name) or {}).get("load_from_db") and value(name, "")
    }

    kind = value("kind", "Choice")
    options = value("candidates", _NEW_QUESTION["options"])
    levels = value("levels", _NEW_QUESTION["levels"])
    if "levels" not in saved and kind == "Score":
        # Older Score nodes stored their rubric in the shared candidates field.
        options, levels = deepcopy(_NEW_QUESTION["options"]), options
    return {
        **deepcopy(_NEW_QUESTION),
        "kind": kind,
        "question": value("question", ""),
        "options": options,
        "levels": levels,
        "yes_description": value("yes_description", ""),
        "no_description": value("no_description", ""),
        **({"global_variables": bound} if bound else {}),
    }
