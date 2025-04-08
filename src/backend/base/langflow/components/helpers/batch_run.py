from __future__ import annotations

import operator
from typing import TYPE_CHECKING, Any

from loguru import logger

from langflow.custom import Component
from langflow.io import (
    BoolInput,
    DataFrameInput,
    HandleInput,
    MessageTextInput,
    MultilineInput,
    Output,
)
from langflow.schema import DataFrame

if TYPE_CHECKING:
    from langchain_core.runnables import Runnable


class BatchRunComponent(Component):
    display_name = "Batch Run"
    description = (
        "Runs a language model over each row of a DataFrame's text column and returns a new "
        "DataFrame with three columns: '**text_input**' (the original text),  "
        "'**model_response**' (the model's response),and '**batch_index**' (the processing order)."
    )
    icon = "List"
    beta = True

    inputs = [
        HandleInput(
            name="model",
            display_name="Language Model",
            info="Connect the 'Language Model' output from your LLM component here.",
            input_types=["LanguageModel"],
            required=True,
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
            required=True,
        ),
        MessageTextInput(
            name="column_name",
            display_name="Column Name",
            info="The name of the DataFrame column to treat as text messages. Default='text'.",
            value="text",
            required=True,
            advanced=True,
        ),
        BoolInput(
            name="enable_metadata",
            display_name="Enable Metadata",
            info="If True, add metadata to the output DataFrame.",
            value=True,
            required=False,
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Batch Results",
            name="batch_results",
            method="run_batch",
            info="A DataFrame with columns: 'text_input', 'model_response', 'batch_index', and 'metadata'.",
        ),
    ]

    def _create_base_row(self, text_input: str = "", model_response: str = "", batch_index: int = -1) -> dict[str, Any]:
        """Create a base row with optional metadata."""
        return {
            "text_input": text_input,
            "model_response": model_response,
            "batch_index": batch_index,
        }

    def _add_metadata(
        self, row: dict[str, Any], *, success: bool = True, system_msg: str = "", error: str | None = None
    ) -> None:
        """Add metadata to a row if enabled."""
        if not self.enable_metadata:
            return

        if success:
            row["metadata"] = {
                "has_system_message": bool(system_msg),
                "input_length": len(row["text_input"]),
                "response_length": len(row["model_response"]),
                "processing_status": "success",
            }
        else:
            row["metadata"] = {
                "error": error,
                "processing_status": "failed",
            }

    async def run_batch(self) -> DataFrame:
        """Process each row in df[column_name] with the language model asynchronously.

        Returns:
            DataFrame: A new DataFrame containing:
                - text_input: The original input text
                - model_response: The model's response
                - batch_index: The processing order
                - metadata: Additional processing information

        Raises:
            ValueError: If the specified column is not found in the DataFrame
            TypeError: If the model is not compatible or input types are wrong
        """
        model: Runnable = self.model
        system_msg = self.system_message or ""
        df: DataFrame = self.df
        col_name = self.column_name or "text"

        # Validate inputs first
        if not isinstance(df, DataFrame):
            msg = f"Expected DataFrame input, got {type(df)}"
            raise TypeError(msg)

        if col_name not in df.columns:
            msg = f"Column '{col_name}' not found in the DataFrame. Available columns: {', '.join(df.columns)}"
            raise ValueError(msg)

        try:
            # Convert the specified column to a list of strings
            user_texts = df[col_name].astype(str).tolist()
            total_rows = len(user_texts)

            logger.info(f"Processing {total_rows} rows with batch run")

            # Prepare the batch of conversations
            conversations = [
                [{"role": "system", "content": system_msg}, {"role": "user", "content": text}]
                if system_msg
                else [{"role": "user", "content": text}]
                for text in user_texts
            ]

            # Configure the model with project info and callbacks
            model = model.with_config(
                {
                    "run_name": self.display_name,
                    "project_name": self.get_project_name(),
                    "callbacks": self.get_langchain_callbacks(),
                }
            )

            # Process batches and track progress
            responses_with_idx = [
                (idx, response)
                for idx, response in zip(
                    range(len(conversations)), await model.abatch(list(conversations)), strict=True
                )
            ]

            # Sort by index to maintain order
            responses_with_idx.sort(key=operator.itemgetter(0))

            # Build the final data with enhanced metadata
            rows: list[dict[str, Any]] = []
            for idx, response in responses_with_idx:
                resp_text = response.content if hasattr(response, "content") else str(response)
                row = self._create_base_row(
                    text_input=user_texts[idx],
                    model_response=resp_text,
                    batch_index=idx,
                )
                self._add_metadata(row, success=True, system_msg=system_msg)
                rows.append(row)

                # Log progress
                if (idx + 1) % max(1, total_rows // 10) == 0:
                    logger.info(f"Processed {idx + 1}/{total_rows} rows")

            logger.info("Batch processing completed successfully")
            return DataFrame(rows)

        except (KeyError, AttributeError) as e:
            # Handle data structure and attribute access errors
            logger.error(f"Data processing error: {e!s}")
            error_row = self._create_base_row()
            self._add_metadata(error_row, success=False, error=str(e))
            return DataFrame([error_row])
