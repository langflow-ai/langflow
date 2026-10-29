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
from lfx.field_typing.range_spec import RangeSpec
from lfx.io import (
    DropdownInput,
    FloatInput,
    HandleInput,
    IntInput,
    MessageTextInput,
    ModelInput,
    MultilineInput,
    Output,
    TabInput,
    TableInput,
)
from lfx.schema.data import Data
from lfx.schema.table import EditMode

_KINDS = ("Choice", "Boolean", "Score")
_FORM, _JSON = "Form", "JSON"
# More questions go in Questions JSON; every form question is a hidden group on every node.
_MAX_FORM_QUESTIONS = 5
# Fields whose change re-runs _show_fields; the editor sends the new value beside the config.
_REFRESHED_FIELDS = {"question_mode", "number_of_questions", "kind"} | {
    f"kind_{number}" for number in range(2, _MAX_FORM_QUESTIONS + 1)
}
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


def _field(role: str, number: int) -> str:
    """Question 1 keeps the original field names, so saved single-question flows still load."""
    return role if number == 1 else f"{role}_{number}"


def _question_inputs(number: int) -> list:
    """One question's group. Question 1 shows by default; the others show as Number of Questions grows."""
    first = number == 1
    suffix = "" if first else f" {number}"
    return [
        MessageTextInput(
            name=_field("question_name", number),
            display_name=f"Question Name{suffix}",
            info=f"Optional: this answer's key in the result, such as urgent. Defaults to q{number}.",
            show=False,
        ),
        DropdownInput(
            name=_field("kind", number),
            display_name=f"Decision Type{suffix}",
            options=list(_KINDS),
            value="Choice",
            info="Choice picks one option. Boolean answers yes or no. Score places the input on ordered levels.",
            real_time_refresh=True,
            show=first,
        ),
        MessageTextInput(
            name=_field("question", number),
            display_name=f"Question{suffix}",
            info='What to decide about the Context, such as "Which team should handle this message?"',
            required=first,
            show=first,
        ),
        TableInput(
            name=_field("candidates", number),
            display_name=f"{_TABLE['Choice'][0]}{suffix}",
            # Options are typed in, not connected: connected rows arrive with NaN cells and number IDs.
            input_types=[],
            value=[row.copy() for row in _DEFAULT_CANDIDATES["Choice"]],
            info=_TABLE["Choice"][1],
            table_schema=_TABLE_SCHEMA,
            show=first,
        ),
        TableInput(
            name=_field("levels", number),
            display_name=f"{_TABLE['Score'][0]}{suffix}",
            input_types=[],
            value=[row.copy() for row in _DEFAULT_CANDIDATES["Score"]],
            info=_TABLE["Score"][1],
            table_schema=_TABLE_SCHEMA,
            show=False,
        ),
        MessageTextInput(
            name=_field("yes_description", number),
            display_name=f"What Yes Means{suffix} (Optional)",
            info=(
                "Optional: what a Yes answer means. Some decision models don't accept this; if yours "
                "doesn't, the run stops and asks you to clear it."
            ),
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name=_field("no_description", number),
            display_name=f"What No Means{suffix} (Optional)",
            info=(
                "Optional: what a No answer means. Some decision models don't accept this; if yours "
                "doesn't, the run stops and asks you to clear it."
            ),
            show=False,
            advanced=True,
        ),
    ]


def _question_count(value) -> int:
    """The editor's Number of Questions, kept in range for showing fields; a run checks it strictly."""
    try:
        return min(max(int(value), 1), _MAX_FORM_QUESTIONS)
    except (TypeError, ValueError):
        return 1


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
        IntInput(
            name="number_of_questions",
            display_name="Number of Questions",
            value=1,
            range_spec=RangeSpec(min=1, max=_MAX_FORM_QUESTIONS, step=1, step_type="int"),
            real_time_refresh=True,
            info=f"Ask up to {_MAX_FORM_QUESTIONS} questions about the same Context in one call; use Questions "
            "JSON for more. With more than one, the result holds each answer under its Question Name.",
        ),
        *[field for number in range(1, _MAX_FORM_QUESTIONS + 1) for field in _question_inputs(number)],
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

    def _form_question(self, number: int) -> dict:
        """One form question's fields, only those its Decision Type uses."""
        kind = getattr(self, _field("kind", number))
        # A tweak can send anything here; the dropdown only offers these three.
        if kind not in _KINDS:
            where = "" if number == 1 else f" for Question {number}"
            msg = f"Pick a Decision Type{where}: Choice, Boolean or Score."
            raise DecisionConfigurationError(msg)
        kind = kind.lower()
        boolean = kind == "boolean"
        return {
            "kind": kind,
            "question": getattr(self, _field("question", number)),
            "options": getattr(self, _field("candidates", number)) if kind == "choice" else (),
            "levels": getattr(self, _field("levels", number)) if kind == "score" else (),
            # Hidden for other types, so a value left from Boolean never applies to them.
            "yes_description": (getattr(self, _field("yes_description", number)) or "") if boolean else "",
            "no_description": (getattr(self, _field("no_description", number)) or "") if boolean else "",
        }

    def _request(self):
        context = self._context()
        if self.question_mode == _JSON:
            return self._json_request(context)
        if self.question_mode != _FORM:
            msg = "Pick a Questions Mode: Form or JSON."
            raise DecisionConfigurationError(msg)
        count = self.number_of_questions
        if type(count) is not int or not 1 <= count <= _MAX_FORM_QUESTIONS:
            msg = f"Number of Questions must be a whole number from 1 to {_MAX_FORM_QUESTIONS}."
            raise DecisionConfigurationError(msg)
        if count == 1:
            return decision_request(context=context, **self._form_question(1))
        questions = {}
        for number in range(1, count + 1):
            name = str(getattr(self, _field("question_name", number)) or "").strip() or f"q{number}"
            if name in questions:
                msg = f"Two questions are named {name!r}. Give each question a different Question Name."
                raise DecisionConfigurationError(msg)
            try:
                questions[name] = DecisionQuestion(**self._form_question(number))
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
        self._show_fields(template)
        return new_frontend_node

    def update_build_config(self, build_config: dict, field_value, field_name: str | None = None) -> dict:
        config = handle_model_input_update(self, build_config, field_value, field_name)
        if field_name in _REFRESHED_FIELDS and field_name in config:
            config[field_name]["value"] = field_value
        self._show_fields(config)
        return config

    @staticmethod
    def _show_fields(config: dict) -> None:
        """Show the active mode's inputs and each shown question's type fields, keeping every value."""
        form = config.get("question_mode", {}).get("value", _FORM) != _JSON
        count = _question_count(config.get("number_of_questions", {}).get("value", 1)) if form else 0
        shown = {"number_of_questions": form, "questions_json": not form}
        for number in range(1, _MAX_FORM_QUESTIONS + 1):
            active = number <= count
            kind = config.get(_field("kind", number), {}).get("value", "Choice")
            shown |= {
                _field("question_name", number): active and count > 1,
                _field("kind", number): active,
                _field("question", number): active,
                _field("candidates", number): active and kind == "Choice",
                _field("levels", number): active and kind == "Score",
                _field("yes_description", number): active and kind == "Boolean",
                _field("no_description", number): active and kind == "Boolean",
            }
            if (name := _field("question", number)) in config:
                config[name]["required"] = active
        for name, show in shown.items():
            if name in config:
                config[name]["show"] = show
        if "questions_json" in config:
            config["questions_json"]["advanced"] = form
