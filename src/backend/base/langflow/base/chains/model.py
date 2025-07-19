from lfx.custom.custom_component.component import Component

from langflow.template.field.base import Output


class LCChainComponent(Component):
    trace_type = "chain"

    outputs = [Output(display_name="Text", name="text", method="invoke_chain")]

    def _validate_outputs(self) -> None:
        required_output_methods = ["invoke_chain"]
        output_names = [output.name for output in self.outputs]
        for method_name in required_output_methods:
            if method_name not in output_names:
                msg = f"Output with name '{method_name}' must be defined."
                raise ValueError(msg)
            if not hasattr(self, method_name):
                msg = f"Method '{method_name}' must be defined."
                raise ValueError(msg)
