from langflow.custom import Component
from langflow.io import BoolInput, DropdownInput, IntInput, MessageInput, MessageTextInput, Output
from langflow.schema.message import Message


class ConditionalRouterComponent(Component):
    display_name = "If-Else"
    description = "Routes an input message to a corresponding output based on text comparison."
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
        ),
        MessageTextInput(
            name="match_text",
            display_name="Match Text",
            info="The text input to compare against.",
        ),
        DropdownInput(
            name="operator",
            display_name="Operator",
            options=["equals", "not equals", "contains", "starts with", "ends with"],
            info="The operator to apply for comparing the texts.",
            value="equals",
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
            advanced=True,
        ),
        IntInput(
            name="max_iterations",
            display_name="Max Iterations",
            info="The maximum number of iterations for the conditional router.",
            value=10,
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
        Output(display_name="True", name="true_result", method="true_response"),
        Output(display_name="False", name="false_result", method="false_response"),
    ]

    def _pre_run_setup(self):
        self.__iteration_updated = False

    def evaluate_condition(self, input_text: str, match_text: str, operator: str, *, case_sensitive: bool) -> bool:
        if not case_sensitive:
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
        return False

    def iterate_and_stop_once(self, route_to_stop: str):
        if not self.__iteration_updated:
            self.update_ctx({f"{self._id}_iteration": self.ctx.get(f"{self._id}_iteration", 0) + 1})
            self.__iteration_updated = True
            if self.ctx.get(f"{self._id}_iteration", 0) >= self.max_iterations and route_to_stop == self.default_route:
                # We need to stop the other route
                route_to_stop = "true_result" if route_to_stop == "false_result" else "false_result"
            self.stop(route_to_stop)

    def true_response(self) -> Message:
        result = self.evaluate_condition(
            self.input_text, self.match_text, self.operator, case_sensitive=self.case_sensitive
        )
        if result:
            self.status = self.message
            self.iterate_and_stop_once("false_result")
            return self.message
        self.iterate_and_stop_once("true_result")
        return self.message

    def false_response(self) -> Message:
        result = self.evaluate_condition(
            self.input_text, self.match_text, self.operator, case_sensitive=self.case_sensitive
        )
        if not result:
            self.status = self.message
            self.iterate_and_stop_once("true_result")
            return self.message
        self.iterate_and_stop_once("false_result")
        return self.message
