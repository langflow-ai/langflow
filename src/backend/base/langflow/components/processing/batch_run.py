from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import toml  # type: ignore[import-untyped]
from loguru import logger

from langflow.custom.custom_component.component import Component
from langflow.io import BoolInput, DataFrameInput, HandleInput, MessageTextInput, MultilineInput, Output
from langflow.schema.dataframe import DataFrame

if TYPE_CHECKING:
    from langchain_core.runnables import Runnable


class BatchRunComponent(Component):
    display_name = "Batch Run"
    description = "Runs an LLM on each row of a DataFrame column. If no column is specified, all columns are used."
    documentation: str = "https://docs.langflow.org/components-processing#batch-run"
    icon = "List"

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
            display_name="Instructions",
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
            info=(
                "The name of the DataFrame column to treat as text messages. "
                "If empty, all columns will be formatted in TOML."
            ),
            required=False,
            advanced=False,
        ),
        MessageTextInput(
            name="output_column_name",
            display_name="Output Column Name",
            info="Name of the column where the model's response will be stored.",
            value="model_response",
            required=False,
            advanced=True,
        ),
        BoolInput(
            name="enable_metadata",
            display_name="Enable Metadata",
            info="If True, add metadata to the output DataFrame.",
            value=False,
            required=False,
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            display_name="LLM Results",
            name="batch_results",
            method="run_batch",
            info="A DataFrame with all original columns plus the model's response column.",
        ),
    ]

    def _format_row_as_toml(self, row: dict[str, Any]) -> str:
        """Convert a dictionary (row) into a TOML-formatted string."""
        formatted_dict = {str(col): {"value": str(val)} for col, val in row.items()}
        return toml.dumps(formatted_dict)

    def _create_base_row(
        self, original_row: dict[str, Any], model_response: str = "", batch_index: int = -1
    ) -> dict[str, Any]:
        """Create a base row with original columns and additional metadata."""
        row = original_row.copy()
        row[self.output_column_name] = model_response
        row["batch_index"] = batch_index
        return row

    def _add_metadata(
        self, row: dict[str, Any], *, success: bool = True, system_msg: str = "", error: str | None = None
    ) -> None:
        """Add metadata to a row if enabled."""
        if not self.enable_metadata:
            return

        if success:
            row["metadata"] = {
                "has_system_message": bool(system_msg),
                "input_length": len(row.get("text_input", "")),
                "response_length": len(row[self.output_column_name]),
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
                - All original columns
                - The model's response column (customizable name)
                - 'batch_index' column for processing order
                - 'metadata' (optional)

        Raises:
            ValueError: If the specified column is not found in the DataFrame
            TypeError: If the model is not compatible or input types are wrong
        """
        model: Runnable = self.model
        system_msg = self.system_message or ""
        df: DataFrame = self.df
        col_name = self.column_name or ""

        # Validate inputs first
        if not isinstance(df, DataFrame):
            msg = f"Expected DataFrame input, got {type(df)}"
            raise TypeError(msg)

        if col_name and col_name not in df.columns:
            msg = f"Column '{col_name}' not found in the DataFrame. Available columns: {', '.join(df.columns)}"
            raise ValueError(msg)

        try:
            # Determine text input for each row
            if col_name:
                user_texts = df[col_name].astype(str).tolist()
            else:
                user_texts = [
                    self._format_row_as_toml(cast(dict[str, Any], row)) for row in df.to_dict(orient="records")
                ]

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
            responses_with_idx = list(
                zip(
                    range(len(conversations)),
                    await model.abatch(list(conversations)),
                    strict=True,
                )
            )

            # Sort by index to maintain order
            responses_with_idx.sort(key=lambda x: x[0])

            # Build the final data with enhanced metadata
            rows: list[dict[str, Any]] = []
            for idx, (original_row, response) in enumerate(
                zip(df.to_dict(orient="records"), responses_with_idx, strict=False)
            ):
                response_text = response[1].content if hasattr(response[1], "content") else str(response[1])
                row = self._create_base_row(
                    cast(dict[str, Any], original_row), model_response=response_text, batch_index=idx
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
            error_row = self._create_base_row({col: "" for col in df.columns}, model_response="", batch_index=-1)
            self._add_metadata(error_row, success=False, error=str(e))
            return DataFrame([error_row])
