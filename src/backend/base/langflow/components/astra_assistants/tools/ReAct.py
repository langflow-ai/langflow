from astra_assistants.tools.tool_interface import ToolInterface
from openai import BaseModel
from pydantic import Field


class ReActCompletionDecider(BaseModel):
    """
    This tool evaluates whether the task is complete and provides logic to explain why the task is done or not.
    """

    logic: str = Field(..., description="Explanation of why the task is considered complete or incomplete.")
    is_complete: bool = Field(..., description="Boolean indicating whether the task is complete (True) or not (False).")

    @classmethod
    def check_completion(cls, logic: str) -> bool:
        """
        Determines whether the task is complete based on the provided logic.
        Returns True if the task is complete, otherwise False.
        """
        return "final answer" in logic.lower() or "no further actions" in logic.lower()

    class Config:
        schema_extra = {
            "example": [
                {
                    "logic": "The list comprehension has been correctly implemented and tested. There are no further "
                    "actions required.",
                    "is_complete": True,
                },
                {
                    "logic": "The list comprehension has been implemented, but I need to test if it behaves the same "
                    "as the for loop.",
                    "is_complete": False,
                },
                {
                    "logic": "I have verified that the list comprehension achieves the same results as the original "
                    "for loop. No further actions are needed.",
                    "is_complete": True,
                },
                {
                    "logic": "I need to rewrite the for loop with list comprehension and check for correctness.",
                    "is_complete": False,
                },
            ]
        }


class ReActThoughtGenerator(BaseModel):
    """
    ReAct Chain of Thought Tool / Function, this function provides some additional context  to help answer questions.
    It can be called multiple times to get better context. Continue to call it until the thought process is complete.
    Then use the context to answer the question.
    """

    thought: str = Field(
        ..., description="Your current stream of consciousness step by step thoughts as you analyze this question."
    )
    action: str = Field(..., description="Actions that need to be taken to complete the thought.")
    answer: str | None = Field(
        ...,
        description="A string that represents the final answer to the question. Only provide this if you are sure of "
        "the answer.",
    )

    class Config:
        schema_extra = {
            "example": [
                {
                    "thought": "I want to refactor a function that currently uses a `for` loop to generate a list. \
                    Using list comprehension will make the code more concise.",
                    "action": "Analyze the function to determine what the `for` loop does, and how it can be "
                    "rewritten in a list comprehension.",
                    "answer": None,
                },
                {
                    "thought": "The function is currently looping through a list of numbers, squaring each number, \
                    and appending it to a new list using a `for` loop. A list comprehension can achieve the same "
                    "result in a single line.",
                    "action": "Rewrite the `for` loop as a list comprehension that performs the same operation.",
                    "answer": None,
                },
                {
                    "thought": "The `for` loop is iterating over a list called `numbers`, squaring each element and "
                    "appending it to a new list `squared_numbers`. \
                    The list comprehension would look like this: `squared_numbers = [x ** 2 for x in numbers]`.",
                    "action": "Check that the list comprehension is syntactically correct and performs the same "
                    "operation as the original loop.",
                    "answer": None,
                },
                {
                    "thought": "The refactored list comprehension correctly squares each element of the list and "
                    "returns the same result as the original `for` loop. \
                    The code is now more concise and easier to read.",
                    "action": "None",
                    "answer": "The final refactored code is: `squared_numbers = [x ** 2 for x in numbers]`. This "
                    "replaces the `for` loop in a more concise manner.",
                },
            ]
        }

    def to_string(self):
        if self.answer:
            return f"Thought: {self.thought}\n" f"action: {self.action}\n" f"answer: {self.answer}"
        return f"Thought: {self.thought}\n" f"action: {self.action}\n"


# Define the chain-of-thought tool
class ReActThoughtTool(ToolInterface):
    def __init__(self):
        self.thought_process = []
        self.current_thought = None

    def set_initial_thought(self, thought: ReActThoughtGenerator):
        """Initialize the chain of thought."""
        self.current_thought = thought
        self.thought_process.append(thought)

    def call(self, cot: ReActThoughtGenerator):
        """Executes the chain of thought process until it's complete."""
        instructions = f"## Context:\n" f"{cot.to_string()}\n"

        print(f"providing instructions: \n{instructions}")
        return {"output": instructions, "cot": cot, "tool": self.__class__.__name__}

    # Define the chain-of-thought tool


class ReActDeciderTool(ToolInterface):
    def call(self, decision: ReActCompletionDecider):
        """Executes the chain of thought process until it's complete."""
        if decision.is_complete:
            instructions = (
                f"## Context:\n"
                f"{decision.logic}\n"
                f"## Instructions: now provide your final answer (and only the final answer)\n"
            )
        else:
            instructions = (
                f"## Context:\n"
                f"{decision.logic}\n"
                f"## Instructions: the task is not complete, continue working on it\n"
            )

        print(f"providing instructions: \n{instructions}")
        return {"output": instructions, "decision": decision, "tool": self.__class__.__name__}
