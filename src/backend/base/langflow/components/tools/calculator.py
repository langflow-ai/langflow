import ast
import operator

from loguru import logger

from langflow.custom import Component
from langflow.inputs import MessageTextInput
from langflow.io import Output
from langflow.schema import Data
from langflow.schema.message import Message

class CalculatorToolComponent(Component):
    display_name = "Calculator"
    description = "Perform basic arithmetic operations on a given expression."
    icon = "calculator"

    inputs = [
        MessageTextInput(
            name="expression",
            display_name="Expression",
            info="The arithmetic expression to evaluate (e.g., '4*4*(33/22)+12-20').",
            tool_mode=True,
            required=True,
        ),
    ]

    outputs = [
        Output(display_name="Data", name="result", type_=Data, method="evaluate_expression"),
    ]

    def _eval_expr(self, node):
        # Define the allowed operators
        operators = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Pow: operator.pow,
        }
        if isinstance(node, ast.Num):
            return node.n
        if isinstance(node, ast.BinOp):
            return operators[type(node.op)](self._eval_expr(node.left), self._eval_expr(node.right))
        if isinstance(node, ast.UnaryOp):
            return operators[type(node.op)](self._eval_expr(node.operand))
        if isinstance(node, ast.Call):
            msg = (
                "Function calls like sqrt(), sin(), cos() etc. are not supported. "
                "Only basic arithmetic operations (+, -, *, /, **) are allowed."
            )
            raise TypeError(msg)
        msg = f"Unsupported operation or expression type: {type(node).__name__}"
        raise TypeError(msg)

    def evaluate_expression(self) -> Data:
        try:
            # Parse the expression and evaluate it
            tree = ast.parse(self.expression, mode="eval")
            result = self._eval_expr(tree.body)

            # Format the result to a reasonable number of decimal places
            formatted_result = f"{result:.6f}".rstrip("0").rstrip(".")

            self.status = formatted_result
            return Data(data={"result": formatted_result})

        except (SyntaxError, TypeError, KeyError) as e:
            error_message = f"Invalid expression: {e}"
            self.status = error_message
            return Data(data={"error": error_message, "input": self.expression})
        except ZeroDivisionError:
            error_message = "Error: Division by zero"
            self.status = error_message
            return Data(data={"error": error_message, "input": self.expression})
        except Exception as e:  # noqa: BLE001
            logger.opt(exception=True).debug("Error evaluating expression")
            error_message = f"Error: {e}"
            self.status = error_message
            return Data(data={"error": error_message, "input": self.expression})

    def text_output(self) -> Message:
        data = self.evaluate_expression()
        if "result" in data.data:
            return Message(text=str(data.data["result"]))
        else:
            return Message(text=str(data.data["error"]))

    def build(self):
        return self.evaluate_expression
