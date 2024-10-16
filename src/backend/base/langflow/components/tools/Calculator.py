import ast
import operator

from langchain.tools import StructuredTool
from loguru import logger
from pydantic import BaseModel, Field

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.field_typing import Tool
from langflow.inputs import MessageTextInput
from langflow.schema import Data


class CalculatorToolComponent(LCToolComponent):
    display_name = "Calculator"
    description = "Perform basic arithmetic operations on a given expression."
    icon = "calculator"
    name = "CalculatorTool"

    inputs = [
        MessageTextInput(
            name="expression",
            display_name="Expression",
            info="The arithmetic expression to evaluate (e.g., '4*4*(33/22)+12-20').",
        ),
    ]

    class CalculatorToolSchema(BaseModel):
        expression: str = Field(..., description="The arithmetic expression to evaluate.")

    def run_model(self) -> list[Data]:
        return self._evaluate_expression(self.expression)

    def build_tool(self) -> Tool:
        return StructuredTool.from_function(
            name="calculator",
            description="Evaluate basic arithmetic expressions. Input should be a string containing the expression.",
            func=self._evaluate_expression,
            args_schema=self.CalculatorToolSchema,
        )

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
        raise TypeError(node)

    def _evaluate_expression(self, expression: str) -> list[Data]:
        try:
            # Parse the expression and evaluate it
            tree = ast.parse(expression, mode="eval")
            result = self._eval_expr(tree.body)

            # Format the result to a reasonable number of decimal places
            formatted_result = f"{result:.6f}".rstrip("0").rstrip(".")

            self.status = formatted_result
            return [Data(data={"result": formatted_result})]

        except (SyntaxError, TypeError, KeyError) as e:
            error_message = f"Invalid expression: {e}"
            self.status = error_message
            return [Data(data={"error": error_message})]
        except ZeroDivisionError:
            error_message = "Error: Division by zero"
            self.status = error_message
            return [Data(data={"error": error_message})]
        except Exception as e:  # noqa: BLE001
            logger.opt(exception=True).debug("Error evaluating expression")
            error_message = f"Error: {e}"
            self.status = error_message
            return [Data(data={"error": error_message})]
