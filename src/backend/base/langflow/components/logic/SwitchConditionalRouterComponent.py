import re
from langflow.custom import Component
from langflow.io import BoolInput, MessageInput, MessageTextInput, Output, TableInput
from langflow.schema.message import Message


class SwitchConditionalRouterComponent(Component):
    display_name = "Switch-Case"
    description = "Route the input message to the first matching output based on multi-segment text comparison"
    icon = "split"
    name = "SwitchConditionalRouter"

    inputs = [
        MessageTextInput(
            name="input_text",
            display_name="Text Input",
            info="The primary text input for the operation.",
            required=True,
        ),
        TableInput(
            name="condition_table",
            display_name="matching rules",
            info="enter Matching Text And Operators(equals, not equals, contains, starts with, ends with, regex)",
            table_schema=[
                {
                    "name": "operator",
                    "display_name": "Operator",
                    "type": "str",
                    "description": "The operator to apply for comparing the texts.",
                },
                {
                    "name": "match_text",
                    "display_name": "Match Text",
                    "description": "The text input to compare against.",
                },
            ],
            value=[],
            real_time_refresh=True,
            refresh_button=True,
        ),
        BoolInput(
            name="case_sensitive",
            display_name="Case Sensitive",
            info="If true, the comparison will be case sensitive.",
            value=False,
        ),
        MessageInput(
            name="message",
            display_name="Message",
            info="The message to pass through either route.",
            advanced=True,
        ),
    ]

    def __getattr__(self, name):
        """This method is called when accessing a non-existent property"""

        # 创建一个闭包函数来处理方法调用
        def method_handler() -> Message:
            return self.switch_response_common(name)

        if name.startswith("switch_response_common"):
            return method_handler
        else:
            return super().__getattr__(name)

    def _pre_run_setup(self):
        self.__iteration_updated = False

    def evaluate_condition(self, input_text: str, match_text: str, operator: str, *, case_sensitive: bool) -> bool:
        if not case_sensitive and operator != "regex":
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
        return False

    def switch_response_common(self, method_name: str) -> Message:

        output_index = int(method_name.split("_")[-1])
        if isinstance(self.condition_table, list):
            for i, item in enumerate(self.condition_table):
                operator: str = item.get('operator').strip().lower()
                match_text = item.get('match_text').strip()
                result = self.evaluate_condition(
                    self.input_text, match_text, operator, case_sensitive=self.case_sensitive
                )
                self.log(f"method_name: {method_name}, result: {result}")
                if output_index > i and result:
                    self.stop(method_name)
                    self.log(f"method_name: {method_name} is stop.Because the previous condition has been met")
                    return Message(content="")
                elif output_index == i:
                    if result:
                        self.status = self.message
                        self.log(f"method_name: {method_name}, return message: {self.message}")
                        return self.message
                    else:
                        self.log(f"method_name: {method_name}, stop.Because the conditions are not met")
                        self.stop(method_name)
                        return Message(content="")
                elif output_index < i:
                    break
            self.log(f"method_name: {method_name}。all conditions are not met, take the default channel.")
            self.status = self.message
            return self.message
        else:
            raise ValueError("condition_table must be a list")

    def update_outputs(self, frontend_node: dict, field_name: str, field_value: list[dict]) -> dict:

        outputs = []
        i = 0
        for item in self.condition_table:
            output_name = f'switch_response_common_{i}'
            outputs.append(Output(
                name=output_name,
                display_name=f"WHEN {item.get('operator')} {item.get('match_text')}",
                method=output_name,
            ))
            i += 1
        outputs.append(Output(
            name=f'switch_response_common_{i}',
            display_name="ELSE",
            method=f'switch_response_common_{i}',
        ))
        frontend_node['outputs'] = outputs
        return frontend_node

    def _get_outputs_to_process(self):

        if self._outputs_map is None:
            self._outputs_map = {}
        i = 0
        for condition in self.condition_table:
            output_name = f'switch_response_common_{i}'
            self._outputs_map[output_name] = Output(
                name=output_name,
                display_name=f"{condition.get('operator')}_{condition.get('match_text')}",
                method=output_name,
            )
            i += 1
        # 添加else
        self._outputs_map[f'switch_response_common_{i}'] = Output(
            name=f'switch_response_common_{i}',
            display_name="ELSE",
            method=f'switch_response_common_{i}',
        )
        return (output for output in self._outputs_map.values() if self._should_process_output(output))
