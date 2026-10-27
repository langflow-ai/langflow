from lfx.base.models.decisions.runtime import decision_token_usage, evaluate_decision, request_variables_of
from lfx.base.models.decisions.schema import DecisionConfigurationError, decision_request
from lfx.base.models.unified_models import handle_model_input_update
from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, FloatInput, HandleInput, MessageTextInput, ModelInput, Output, TableInput
from lfx.schema.data import Data
from lfx.schema.table import EditMode

_KINDS = ("Choice", "Boolean", "Score")
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
# What an agent learns about this component when it is a tool.
_RESULT_INFO = (
    "Answers this component's fixed question about the text you pass as context, and returns JSON. Choice gives "
    "probabilities by option ID and, when the provider names one, selected_option (otherwise take the most "
    "probable option); Boolean gives probability_true, the "
    "probability the answer is yes, from 0 to 1; Score gives score, from 0 (the first level) up to one less than "
    "the number of levels, and probabilities by level ID. confidence is the provider's own measure, not an "
    "option's probability."
)

# Follow-ups, deferred until there is demand:
# - Several named questions in one request, answered as one typed object. All three providers take
#   them, but Perplexity's full model answers grouped questions jointly (an answer can change with
#   its group) and its flash model bills the context once per question, so keep it opt-in.
# - Images: TypeSafe `assets` behind its TypeSafe-Danger-Zone-Images header, Perplexity image parts
#   in `state`, OpenAI image inputs. Needs size limits and SSRF checks for each format.
# - Pinned model versions, such as pplx-decider-v1.2: policy allows models by name, so each version
#   needs its own catalog and policy entry.


class DecisionModelComponent(Component):
    """Evaluates one judgment through the same runtime as the Smart Router."""

    display_name = "Decision Model"
    description = "Evaluate a choice, probability, or ordered score"
    name = "DecisionModel"
    icon = "Split"

    inputs = [
        ModelInput(
            model_type="decision", name="model", display_name="Decision Model", required=True, real_time_refresh=True
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
            value=[
                {"id": "low", "label": "Low", "description": ""},
                {"id": "medium", "label": "Medium", "description": ""},
                {"id": "high", "label": "High", "description": ""},
            ],
            info=_TABLE["Choice"][1],
            table_schema=[
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
            ],
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

    def evaluate(self) -> Data:
        # A tweak can send anything here; the dropdown only offers these three.
        if self.kind not in _KINDS:
            msg = "Pick a Decision Type: Choice, Boolean or Score."
            raise DecisionConfigurationError(msg)
        kind = self.kind.lower()
        boolean = kind == "boolean"
        request = decision_request(
            kind=kind,
            question=self.question,
            context=self._context(),
            options=self.candidates if kind == "choice" else (),
            levels=self.candidates if kind == "score" else (),
            # Hidden for other types, so a value left from Boolean never applies to them.
            yes_description=(self.yes_description or "") if boolean else "",
            no_description=(self.no_description or "") if boolean else "",
        )
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
        self._show_fields(template, (template.get("kind") or {}).get("value", "Choice"))
        return new_frontend_node

    def update_build_config(self, build_config: dict, field_value, field_name: str | None = None) -> dict:
        config = handle_model_input_update(self, build_config, field_value, field_name)
        self._show_fields(
            config, field_value if field_name == "kind" else config.get("kind", {}).get("value", "Choice")
        )
        return config

    @staticmethod
    def _show_fields(config: dict, kind: str) -> None:
        """Show the table and the Yes/No meanings for this Decision Type, and name the table for it."""
        config["candidates"]["show"] = kind != "Boolean"
        if kind in _TABLE:
            config["candidates"]["display_name"], config["candidates"]["info"] = _TABLE[kind]
        for name in ("yes_description", "no_description"):
            if name in config:
                config[name]["show"] = kind == "Boolean"
