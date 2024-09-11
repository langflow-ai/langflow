import ast
import operator
from typing import List
from pydantic import BaseModel, Field
from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.inputs import MessageTextInput
from langflow.schema import Data
from langflow.field_typing import Tool
from langchain.tools import StructuredTool


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

    def run_model(self) -> List[Data]:
        return self._evaluate_expression(self.expression)

    def build_tool(self) -> Tool:
        return StructuredTool.from_function(
            name="calculator",
            description="Evaluate basic arithmetic expressions. Input should be a string containing the expression.",
            func=self._evaluate_expression,
            args_schema=self.CalculatorToolSchema,
        )

    def _evaluate_expression(self, expression: str) -> List[Data]:
        try:
            # Define the allowed operators
            operators = {
                ast.Add: operator.add,
                ast.Sub: operator.sub,
                ast.Mult: operator.mul,
                ast.Div: operator.truediv,
                ast.Pow: operator.pow,
            }

            def eval_expr(node):
                if isinstance(node, ast.Num):
                    return node.n
                elif isinstance(node, ast.BinOp):
                    return operators[type(node.op)](eval_expr(node.left), eval_expr(node.right))
                elif isinstance(node, ast.UnaryOp):
                    return operators[type(node.op)](eval_expr(node.operand))
                else:
                    raise TypeError(node)

            # Parse the expression and evaluate it
            tree = ast.parse(expression, mode="eval")
            result = eval_expr(tree.body)

            # Format the result to a reasonable number of decimal places
            formatted_result = f"{result:.6f}".rstrip("0").rstrip(".")

            self.status = formatted_result
            return [Data(data={"result": formatted_result})]

        except (SyntaxError, TypeError, KeyError) as e:
            error_message = f"Invalid expression: {str(e)}"
            self.status = error_message
            return [Data(data={"error": error_message})]
        except ZeroDivisionError:
            error_message = "Error: Division by zero"
            self.status = error_message
            return [Data(data={"error": error_message})]
        except Exception as e:
            error_message = f"Error: {str(e)}"
            self.status = error_message
            return [Data(data={"error": error_message})]
