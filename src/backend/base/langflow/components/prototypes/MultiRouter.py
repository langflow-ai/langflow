from langflow.custom import Component
from langflow.io import BoolInput, DropdownInput, MessageInput, MessageTextInput, Output
from langflow.schema.message import Message


class MultiConditionalRouterComponent(Component):
    display_name = "Multi Conditional Router"
    description = "Routes an input message to a corresponding output based on text comparison."
    icon = "equal"
    name = "ConditionalRouter"

    inputs = [
        MessageTextInput(
            name="input_text",
            display_name="Input Text",
            info="The primary text input for the operation.",
        ),
        DropdownInput(
            name="operator",
            display_name="Operator",
            options=["equals", "not equals", "contains", "starts with", "ends with"],
            info="The operator to apply for comparing the texts.",
            value="equals",
            advanced=True,
        ),
        MessageTextInput(
            name="case_1_text",
            display_name="Case 1 Text",
            info="The text input for Case 1 comparison.",
        ),
        MessageTextInput(
            name="case_2_text",
            display_name="Case 2 Text",
            info="The text input for Case 2 comparison.",
        ),
        MessageTextInput(
            name="case_3_text",
            display_name="Case 3 Text",
            info="The text input for Case 3 comparison.",
        ),
        BoolInput(
            name="case_sensitive",
            display_name="Case Sensitive",
            info="If true, the comparison will be case sensitive.",
            value=False,
            advanced=True,
        ),
        MessageInput(
            name="message",
            display_name="Message",
            info="The message to pass through either route.",
        ),
    ]

    outputs = [
        Output(display_name="Case 1 Response", name="case_1_result", method="case_1_response"),
        Output(display_name="Case 2 Response", name="case_2_result", method="case_2_response"),
        Output(display_name="Case 3 Response", name="case_3_result", method="case_3_response"),
        Output(display_name="Default Response", name="default_result", method="default_response"),
    ]

    def evaluate_condition(self, input_text: str, match_text: str, operator: str, case_sensitive: bool) -> bool:
        if not case_sensitive:
            input_text = input_text.lower()
            match_text = match_text.lower()

        conditions = {
            "equals": input_text == match_text,
            "not equals": input_text != match_text,
            "contains": match_text in input_text,
            "starts with": input_text.startswith(match_text),
            "ends with": input_text.endswith(match_text),
        }
        return conditions.get(operator, False)

    def case_response(self, case_text: str, case_name: str) -> Message:
        result = self.evaluate_condition(self.input_text, case_text, self.operator, self.case_sensitive)
        if result:
            self.status = self.message
            return self.message
        else:
            self.stop(case_name)
            return None  # type: ignore

    def case_1_response(self) -> Message:
        return self.case_response(self.case_1_text, "case_1_result")

    def case_2_response(self) -> Message:
        return self.case_response(self.case_2_text, "case_2_result")

    def case_3_response(self) -> Message:
        return self.case_response(self.case_3_text, "case_3_result")

    def case_4_response(self) -> Message:
        # Logic for case 4 can be added here if needed
        self.stop("case_4_result")
        return None  # type: ignore

    def default_response(self) -> Message:
        # Check if all cases are false
        case_1_result = self.evaluate_condition(self.input_text, self.case_1_text, self.operator, self.case_sensitive)
        case_2_result = self.evaluate_condition(self.input_text, self.case_2_text, self.operator, self.case_sensitive)
        case_3_result = self.evaluate_condition(self.input_text, self.case_3_text, self.operator, self.case_sensitive)
        if not (case_1_result or case_2_result or case_3_result):
            self.status = self.message
            return self.message
        else:
            self.stop("default_result")
            return None  # type: ignore
        return None
