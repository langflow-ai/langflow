import re

from langflow.custom.custom_component.component import Component
from langflow.io import BoolInput, DropdownInput, IntInput, MessageInput, MessageTextInput, Output
from langflow.schema.message import Message


class ConditionalRouterComponent(Component):
    display_name = "If-Else"
    description = "Routes an input message to a corresponding output based on text comparison."
    documentation: str = "https://docs.langflow.org/components-logic#conditional-router-if-else-component"
    icon = "split"
    name = "ConditionalRouter"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__iteration_updated = False

    inputs = [
        MessageTextInput(
            name="input_text",
            display_name="Text Input",
            info="The primary text input for the operation.",
            required=True,
        ),
        DropdownInput(
            name="operator",
            display_name="Operator",
            options=[
                "equals",
                "not equals",
                "contains",
                "starts with",
                "ends with",
                "regex",
                "less than",
                "less than or equal",
                "greater than",
                "greater than or equal",
                "is empty",
            ],
            info="The operator to apply for comparing the texts.",
            value="equals",
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="match_text",
            display_name="Match Text",
            info="The text input to compare against.",
            required=True,
        ),
        BoolInput(
            name="case_sensitive",
            display_name="Case Sensitive",
            info="If true, the comparison will be case sensitive.",
            value=True,
            advanced=True,
        ),
        MessageInput(
            name="true_case_message",
            display_name="Case True",
            info="The message to pass if the condition is True.",
            advanced=True,
        ),
        MessageInput(
            name="false_case_message",
            display_name="Case False",
            info="The message to pass if the condition is False.",
            advanced=True,
        ),
        IntInput(
            name="max_iterations",
            display_name="Max Iterations",
            info="The maximum number of iterations for the conditional router.",
            value=10,
            advanced=True,
        ),
        DropdownInput(
            name="default_route",
            display_name="Default Route",
            options=["true_result", "false_result"],
            info="The default route to take when max iterations are reached.",
            value="false_result",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="True", name="true_result", method="true_response", group_outputs=True),
        Output(display_name="False", name="false_result", method="false_response", group_outputs=True),
    ]

    def _pre_run_setup(self):
        self.__iteration_updated = False

    def evaluate_condition(self, input_text: str, match_text: str, operator: str, *, case_sensitive: bool) -> bool:
        if not case_sensitive and operator not in ["regex", "is empty"]:
            input_text = input_text.lower()
            match_text = match_text.lower()

        if operator == "equals":
            return input_text == match_text
        if operator == "not equals":
            return input_text != match_text
        if operator == "contains":
            return match_text in input_text
        if operator == "starts with":
            return input_text.startswith(match_text)
        if operator == "ends with":
            return input_text.endswith(match_text)
        if operator == "regex":
            try:
                return bool(re.match(match_text, input_text))
            except re.error:
                return False  # Return False if the regex is invalid
        if operator == "is empty":
            return not input_text or input_text.strip() == ""
        if operator in ["less than", "less than or equal", "greater than", "greater than or equal"]:
            try:
                input_num = float(input_text)
                match_num = float(match_text)
                if operator == "less than":
                    return input_num < match_num
                if operator == "less than or equal":
                    return input_num <= match_num
                if operator == "greater than":
                    return input_num > match_num
                if operator == "greater than or equal":
                    return input_num >= match_num
            except ValueError:
                return False  # Invalid number format for comparison
        return False

    def iterate_and_stop_once(self, route_to_stop: str):
        if not self.__iteration_updated:
            self.update_ctx({f"{self._id}_iteration": self.ctx.get(f"{self._id}_iteration", 0) + 1})
            self.__iteration_updated = True
            if self.ctx.get(f"{self._id}_iteration", 0) >= self.max_iterations and route_to_stop == self.default_route:
                route_to_stop = "true_result" if route_to_stop == "false_result" else "false_result"
            self.stop(route_to_stop)

    def true_response(self) -> Message:
        result = self.evaluate_condition(
            self.input_text, self.match_text, self.operator, case_sensitive=self.case_sensitive
        )
        if result:
            # Use true_case_message if provided, otherwise use input_text as default
            if self.true_case_message and hasattr(self.true_case_message, 'text') and self.true_case_message.text:
                output_message = self.true_case_message
                self.status = self.true_case_message.text
            elif self.true_case_message and isinstance(self.true_case_message, str) and self.true_case_message.strip():
                output_message = Message(text=self.true_case_message)
                self.status = self.true_case_message
            else:
                output_message = Message(text=self.input_text)
                self.status = f"True condition met - returning input: {self.input_text}"
            
            self.iterate_and_stop_once("false_result")
            return output_message
        self.iterate_and_stop_once("true_result")
        return Message(content="")

    def false_response(self) -> Message:
        result = self.evaluate_condition(
            self.input_text, self.match_text, self.operator, case_sensitive=self.case_sensitive
        )
        if not result:
            # Use false_case_message if provided, otherwise use input_text as default
            if self.false_case_message and hasattr(self.false_case_message, 'text') and self.false_case_message.text:
                output_message = self.false_case_message
                self.status = self.false_case_message.text
            elif self.false_case_message and isinstance(self.false_case_message, str) and self.false_case_message.strip():
                output_message = Message(text=self.false_case_message)
                self.status = self.false_case_message
            else:
                output_message = Message(text=self.input_text)
                self.status = f"False condition met - returning input: {self.input_text}"
            
            self.iterate_and_stop_once("true_result")
            return output_message
        self.iterate_and_stop_once("false_result")
        return Message(content="")

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:
        if field_name == "operator":
            # Hide case_sensitive for regex and empty operators
            if field_value in ["regex", "is empty"]:
                build_config.pop("case_sensitive", None)
            elif "case_sensitive" not in build_config:
                case_sensitive_input = next(
                    (input_field for input_field in self.inputs if input_field.name == "case_sensitive"), None
                )
                if case_sensitive_input:
                    build_config["case_sensitive"] = case_sensitive_input.to_dict()
            
            # Hide match_text for empty operators
            if field_value == "is empty":
                build_config.pop("match_text", None)
            elif "match_text" not in build_config:
                match_text_input = next(
                    (input_field for input_field in self.inputs if input_field.name == "match_text"), None
                )
                if match_text_input:
                    build_config["match_text"] = match_text_input.to_dict()
        return build_config
