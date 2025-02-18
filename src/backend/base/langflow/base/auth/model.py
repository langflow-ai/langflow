from langflow.custom import Component
from langflow.template import Output


class AuthComponent(Component):
    trace_type = "auth"
    icon = "lock"

    outputs = [Output(display_name="Result", name="auth_result", method="validate_auth")]

    def _validate_outputs(self) -> None:
        required_output_methods = ["validate_auth"]
        output_names = [output.name for output in self.outputs]
        for method_name in required_output_methods:
            if method_name not in output_names:
                msg = f"Output with name '{method_name}' must be defined."
                raise ValueError(msg)
            if not hasattr(self, method_name):
                msg = f"Method '{method_name}' must be defined."
                raise ValueError(msg)

    def validate_auth(self, *args, **kwargs):
        """Base method that all auth components must implement."""
        error_msg = "Auth components must implement validate_auth method"
        raise NotImplementedError(error_msg)
