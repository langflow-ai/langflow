from __future__ import annotations

from typing import TYPE_CHECKING

from langflow.custom import Component
from langflow.io import DataFrameInput, HandleInput, MultilineInput, Output, StrInput
from langflow.schema import DataFrame

if TYPE_CHECKING:
    from langchain_core.runnables import Runnable


class BatchRunComponent(Component):
    display_name = "Batch Run"
    description = (
        "Runs a language model over each row of a DataFrame's text column and returns a new "
        "DataFrame with two columns: 'text_input' (the original text) and 'model_response' "
        "containing the model's response."
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
            info="Multi-line system instruction for all rows in the DataFrame.",
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
            info="A DataFrame with two columns: 'text_input' and 'model_response'.",
        ),
    ]

    async def run_batch(self) -> DataFrame:
        """For each row in df[column_name], combine that text with system_message, then invoke the model asynchronously.

        Returns a new DataFrame of the same length, with columns 'text_input' and 'model_response'.
        """
        model: Runnable = self.model
        system_msg = self.system_message or ""
        df: DataFrame = self.df
        col_name = self.column_name or "text"

        if col_name not in df.columns:
            msg = f"Column '{col_name}' not found in the DataFrame."
            raise ValueError(msg)

        # Convert the specified column to a list of strings
        user_texts = df[col_name].astype(str).tolist()

        # Prepare the batch of conversations
        conversations = [
            [{"role": "system", "content": system_msg}, {"role": "user", "content": text}]
            if system_msg
            else [{"role": "user", "content": text}]
            for text in user_texts
        ]
        model = model.with_config(
            {
                "run_name": self.display_name,
                "project_name": self.get_project_name(),
                "callbacks": self.get_langchain_callbacks(),
            }
        )

        responses = await model.abatch(conversations)

        # Build the final data, each row has 'text_input' + 'model_response'
        rows = []
        for original_text, response in zip(user_texts, responses, strict=False):
            resp_text = response.content if hasattr(response, "content") else str(response)

            row = {"text_input": original_text, "model_response": resp_text}
            rows.append(row)

        # Convert to a new DataFrame
        return DataFrame(rows)  # Langflow DataFrame from a list of dicts
