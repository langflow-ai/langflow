from lfx.base.models.decisions.runtime import evaluate_decision, request_variables_of
from lfx.base.models.decisions.schema import DecisionConfigurationError, decision_request
from lfx.base.models.unified_models import handle_model_input_update
from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, FloatInput, HandleInput, MessageTextInput, ModelInput, Output, TableInput
from lfx.schema.data import Data
from lfx.schema.table import EditMode

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
            options=["Choice", "Boolean", "Score"],
            value="Choice",
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="context",
            display_name="Context",
            info="What the model judges. Used as a tool, the agent supplies it.",
            tool_mode=True,
        ),
        MessageTextInput(name="question", display_name="Question", required=True),
        TableInput(
            name="candidates",
            display_name="Options / Ordered Score Levels",
            value=[],
            info="Choice options or Score levels ordered from lowest (0) to highest. IDs must be unique.",
            table_schema=[
                {"name": "id", "display_name": "ID", "type": "str", "edit_mode": EditMode.INLINE},
                {"name": "label", "display_name": "Label", "type": "str", "edit_mode": EditMode.INLINE},
                {
                    "name": "description",
                    "display_name": "Description",
                    "type": "str",
                    "edit_mode": EditMode.POPOVER,
                    "default": "",
                },
            ],
        ),
        MessageTextInput(
            name="yes_description",
            display_name="What Yes Means",
            info="Boolean only: what a Yes answer means. TypeSafe and Perplexity take it; OpenAI Decisions doesn't.",
            show=False,
            advanced=True,
        ),
        MessageTextInput(
            name="no_description",
            display_name="What No Means",
            info="Boolean only: what a No answer means. TypeSafe and Perplexity take it; OpenAI Decisions doesn't.",
            show=False,
            advanced=True,
        ),
        HandleInput(
            name="structured_context",
            display_name="Structured Context",
            info="JSON sent to the model as it is, in place of Context.",
            input_types=["Data", "JSON"],
            advanced=True,
        ),
        FloatInput(name="timeout", display_name="Timeout (seconds)", value=60, advanced=True),
    ]
    outputs = [Output(name="result", display_name="Decision Result", method="evaluate")]

    def _context(self) -> str | dict:
        """Context as text, or Structured Context as JSON; exactly one of them."""
        text = str(self.context or "").strip()
        # An unconnected handle holds an empty string.
        structured = self.structured_context or None
        if structured is None:
            if not text:
                msg = "Decision Model needs a Context or a Structured Context."
                raise DecisionConfigurationError(msg)
            return self.context
        if text:
            msg = "Set Context or Structured Context, not both."
            raise DecisionConfigurationError(msg)
        return structured.data if isinstance(structured, Data) else structured

    def evaluate(self) -> Data:
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
        data = Data(
            data={**result.model_dump(mode="json"), "request": request.model_dump(mode="json", exclude={"context"})}
        )
        self.status = data
        return data

    def update_build_config(self, build_config: dict, field_value, field_name: str | None = None) -> dict:
        config = handle_model_input_update(self, build_config, field_value, field_name)
        kind = field_value if field_name == "kind" else config.get("kind", {}).get("value", "Choice")
        config["candidates"]["show"] = kind != "Boolean"
        for name in ("yes_description", "no_description"):
            if name in config:
                config[name]["show"] = kind == "Boolean"
        return config
