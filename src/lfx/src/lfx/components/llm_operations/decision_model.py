from lfx.base.models.decisions.runtime import evaluate_decision, request_variables_of
from lfx.base.models.decisions.schema import decision_request
from lfx.base.models.unified_models import handle_model_input_update
from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, FloatInput, MessageTextInput, ModelInput, Output, TableInput
from lfx.schema.data import Data
from lfx.schema.table import EditMode


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
        MessageTextInput(name="context", display_name="Context", required=True),
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
        FloatInput(name="timeout", display_name="Timeout (seconds)", value=60, advanced=True),
    ]
    outputs = [Output(name="result", display_name="Decision Result", method="evaluate")]

    def evaluate(self) -> Data:
        kind = self.kind.lower()
        request = decision_request(
            kind=kind,
            question=self.question,
            context=self.context,
            options=self.candidates if kind == "choice" else (),
            levels=self.candidates if kind == "score" else (),
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
        return config
