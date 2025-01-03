from langchain_core.runnables import RunnableLambda

from langflow.custom import Component
from langflow.field_typing import LanguageModel
from langflow.io import (
    DataFrameInput,
    HandleInput,
    MultilineInput,
    Output,
    StrInput,
)
from langflow.schema import DataFrame


class BatchRunComponent(Component):
    display_name = "Batch Run"
    description = (
        "Runs a language model over each row of a DataFrame’s text column and returns a new "
        "DataFrame with two columns: 'text_input' (the original text) and 'model_response' "
        "containing the model’s response."
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
        """For each row in df[column_name], combine that text with system_message, then
        invoke the model asynchronously. Returns a new DataFrame of the same length,
        with columns 'text_input' and 'model_response'.
        """
        model: LanguageModel = self.model
        system_msg = self.system_message or ""
        df: DataFrame = self.df
        col_name = self.column_name or "text"

        if col_name not in df.columns:
            raise ValueError(f"Column '{col_name}' not found in the DataFrame.")

        # Convert the specified column to a list of strings
        user_texts = df[col_name].astype(str).tolist()

        # 1) Synchronous fallback
        def invoke_model_sync(conversation):
            return model.invoke(conversation)

        # 2) Asynchronous usage
        async def invoke_model_async(conversation):
            return await model.ainvoke(conversation)

        # Build a RunnableLambda with both sync and async
        runnable = RunnableLambda(func=invoke_model_sync, afunc=invoke_model_async)

        # Prepare the batch of conversations
        conversations = [
            [{"role": "system", "content": system_msg}, {"role": "user", "content": text}]
            if system_msg
            else [{"role": "user", "content": text}]
            for text in user_texts
        ]

        # Process the batch asynchronously
        async def process_batch():
            return await runnable.abatch(conversations)

        responses = await process_batch()

        # Build the final data, each row has 'text_input' + 'model_response'
        rows = []
        for original_text, response in zip(user_texts, responses, strict=False):
            if hasattr(response, "content"):
                resp_text = response.content
            else:
                resp_text = str(response)

            row = {"text_input": original_text, "model_response": resp_text}
            rows.append(row)

        # Convert to a new DataFrame
        results_df = DataFrame(rows)  # Langflow DataFrame from a list of dicts
        return results_df
