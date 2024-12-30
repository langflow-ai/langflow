from pathlib import Path
from langflow.custom import Component
from langflow.io import (
    HandleInput,
    MessageTextInput,
    DataFrameInput,
    MultilineInput,
    StrInput,
    Output,
)
from langflow.schema.message import Message
from langflow.schema import DataFrame
from langflow.field_typing import LanguageModel


class BatchRunComponent(Component):
    display_name = "Batch Run"
    description = (
        "Runs a language model over each row of a DataFrame’s text column and returns a DataFrame containing one model response per row."
    )
    icon = "List"
    beta = True

    inputs = [
        HandleInput(
            name="model",
            display_name="Language Model",
            info="Connect the 'Language Model' output from your LLM component here.",
            input_types=["LanguageModel"],
        ),
        MultilineInput(
            name="system_message",
            display_name="System Message",
            info="Multi-line system instruction for all items in the DataFrame.",
            required=False,
        ),
        DataFrameInput(
            name="df",
            display_name="DataFrame",
            info="The DataFrame whose column (specified by 'column_name') we'll treat as text messages.",
        ),
        StrInput(
            name="column_name",
            display_name="Column Name",
            info="The name of the DataFrame column to treat as text messages. Default='text'.",
            value="text",
        ),
    ]

    outputs = [
        Output(
            display_name="Batch Results",
            name="batch_results",
            method="run_batch",
            info="A list of processed messages returned by the model, one per row in the chosen DataFrame column.",
        ),
    ]

    def run_batch(self) -> DataFrame:
        """
        For each row in df[column_name], combine that text with system_message
        and invoke the model, returning a list of responses as Langflow Messages.
        """
        # Retrieve inputs
        model: LanguageModel = self.model
        system_msg: str = self.system_message or ""
        df: DataFrame = self.df
        col_name: str = self.column_name or "text"


        if col_name not in df.columns:
            raise ValueError(f"Column '{col_name}' not found in the DataFrame.")

        # We'll treat each row's text as a user message
        user_texts = df[col_name].astype(str).tolist()

        results: list[Message] = []

        for text in user_texts:
            # Build conversation array: system + user
            conversation = []
            if system_msg:
                conversation.append({"role": "system", "content": system_msg})
            conversation.append({"role": "user", "content": text})

            # Invoke the model
            response = model.invoke(conversation)

            # Convert response to a Langflow Message
            if hasattr(response, "content"):
                # If the model returns an object with .content (e.g. AIMessage)
                new_message = Message(text=response.content)
            else:
                # Otherwise assume it's raw text or a dict
                new_message = Message(text=str(response))

            results.append(new_message)


        return DataFrame(results)