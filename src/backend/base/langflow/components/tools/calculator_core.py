import ast
import operator
from collections.abc import Callable

from langflow.custom import Component
from langflow.inputs import MessageTextInput
from langflow.io import Output
from langflow.schema import Data


class CalculatorComponent(Component):
    display_name = "Calculator"
    description = "Perform basic arithmetic operations on a given expression."
    icon = "calculator"

    # Cache operators dictionary as a class variable
    OPERATORS: dict[type[ast.operator], Callable] = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
    }

    inputs = [
        MessageTextInput(
            name="expression",
            display_name="Expression",
            info="The arithmetic expression to evaluate (e.g., '4*4*(33/22)+12-20').",
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Data", name="result", type_=Data, method="evaluate_expression"),
    ]

    def _eval_expr(self, node: ast.AST) -> float:
        """Evaluate an AST node recursively."""
        if isinstance(node, ast.Constant):
            if isinstance(node.value, int | float):
                return float(node.value)
            error_msg = f"Unsupported constant type: {type(node.value).__name__}"
            raise TypeError(error_msg)
        if isinstance(node, ast.Num):  # For backwards compatibility
            if isinstance(node.n, int | float):
                return float(node.n)
            error_msg = f"Unsupported number type: {type(node.n).__name__}"
            raise TypeError(error_msg)

        if isinstance(node, ast.BinOp):
            op_type = type(node.op)
            if op_type not in self.OPERATORS:
                error_msg = f"Unsupported binary operator: {op_type.__name__}"
                raise TypeError(error_msg)

            left = self._eval_expr(node.left)
            right = self._eval_expr(node.right)
            return self.OPERATORS[op_type](left, right)

        error_msg = f"Unsupported operation or expression type: {type(node).__name__}"
        raise TypeError(error_msg)

    def evaluate_expression(self) -> Data:
        """Evaluate the mathematical expression and return the result."""
        try:
            tree = ast.parse(self.expression, mode="eval")
            result = self._eval_expr(tree.body)

            formatted_result = f"{float(result):.6f}".rstrip("0").rstrip(".")
            self.log(f"Calculation result: {formatted_result}")

            self.status = formatted_result
            return Data(data={"result": formatted_result})

        except ZeroDivisionError:
            error_message = "Error: Division by zero"
            self.status = error_message
            return Data(data={"error": error_message, "input": self.expression})

        except (SyntaxError, TypeError, KeyError, ValueError, AttributeError, OverflowError) as e:
            error_message = f"Invalid expression: {e!s}"
            self.status = error_message
            return Data(data={"error": error_message, "input": self.expression})

    def build(self):
        """Return the main evaluation function."""
        return self.evaluate_expression
