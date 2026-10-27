from __future__ import annotations

import asyncio
import math
import time
from http import HTTPStatus
from typing import Any, cast

import toml  # type: ignore[import-untyped]

from lfx.base.models.unified_models import (
    get_llm,
    handle_model_input_update,
)
from lfx.base.models.watsonx_constants import IBM_WATSONX_URLS
from lfx.custom.custom_component.component import Component
from lfx.io import (
    BoolInput,
    DataFrameInput,
    DropdownInput,
    FloatInput,
    IntInput,
    MessageTextInput,
    ModelInput,
    MultilineInput,
    Output,
    SecretStrInput,
    StrInput,
)
from lfx.log.logger import logger
from lfx.schema.dataframe import DataFrame
from lfx.schema.token_usage import accumulate_usage, extract_usage_from_message


class BatchRunComponent(Component):
    MAX_RETRY_AFTER_SECONDS = 300.0

    display_name = "Batch Run"
    description = "Runs an LLM on each row of a DataFrame column. If no column is specified, all columns are used."
    documentation: str = "https://docs.langflow.org/batch-run"
    icon = "List"

    inputs = [
        ModelInput(
            name="model",
            display_name="Language Model",
            info="Select your model provider",
            real_time_refresh=True,
            required=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="Overrides global provider settings. Leave blank to use your pre-configured API Key.",
            real_time_refresh=True,
            advanced=True,
        ),
        DropdownInput(
            name="base_url_ibm_watsonx",
            display_name="watsonx API Endpoint",
            info="The base URL of the API (IBM watsonx.ai only)",
            options=IBM_WATSONX_URLS,
            value=IBM_WATSONX_URLS[0],
            show=False,
            real_time_refresh=True,
        ),
        StrInput(
            name="project_id",
            display_name="watsonx Project ID",
            info="The project ID associated with the foundation model (IBM watsonx.ai only)",
            show=False,
            required=False,
        ),
        MultilineInput(
            name="system_message",
            display_name="Instructions",
            info="Multi-line system instruction for all rows in the DataFrame.",
            required=False,
        ),
        DataFrameInput(
            name="df",
            display_name="Table",
            info="The DataFrame whose column (specified by 'column_name') we'll treat as text messages.",
            required=True,
        ),
        IntInput(
            name="batch_size",
            display_name="Batch Size",
            info=(
                "Maximum number of model requests to run at the same time. "
                "Rate-limit responses reduce this automatically."
            ),
            value=5,
            required=True,
            advanced=True,
        ),
        FloatInput(
            name="delay_between_batches",
            display_name="Delay Between Batches (seconds)",
            info="Optional pause between batches of model requests.",
            value=0.0,
            required=True,
            advanced=True,
        ),
        IntInput(
            name="max_rate_limit_retries",
            display_name="Rate Limit Retries",
            info="Maximum retries for rate-limited requests. The batch size is reduced after each rate-limit response.",
            value=3,
            required=True,
            advanced=True,
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

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None):
        """Dynamically update build config with user-filtered model options."""
        return handle_model_input_update(self, build_config, field_value, field_name)

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

    @staticmethod
    def _is_rate_limit_error(error: Exception) -> bool:
        """Identify common provider rate-limit errors without depending on a provider SDK."""
        status_code = getattr(error, "status_code", None)
        response = getattr(error, "response", None)
        if status_code is None:
            status_code = getattr(response, "status_code", None)
        if status_code is not None:
            return status_code == HTTPStatus.TOO_MANY_REQUESTS

        error_text = f"{type(error).__name__}: {error}".lower()
        return "rate limit" in error_text or "rate_limit" in error_text or "too many requests" in error_text

    @staticmethod
    def _retry_after_seconds(error: Exception) -> float | None:
        """Read a numeric Retry-After value exposed by common HTTP clients and provider SDKs."""
        retry_after = getattr(error, "retry_after", None)
        response = getattr(error, "response", None)
        headers = getattr(response, "headers", None)
        if retry_after is None and headers is not None:
            retry_after = headers.get("Retry-After") or headers.get("retry-after")
        try:
            delay = float(retry_after)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(delay) or delay < 0:
            return None
        return min(delay, BatchRunComponent.MAX_RETRY_AFTER_SECONDS)

    async def _run_conversations(self, model: Any, conversations: list[list[dict[str, str]]]) -> list[Any]:
        """Run conversations in bounded batches, backing off and shrinking after 429s."""
        batch_size = max(1, int(self.batch_size or 1))
        configured_delay = max(0.0, float(self.delay_between_batches or 0.0))
        max_retries = max(0, int(self.max_rate_limit_retries or 0))
        responses: list[Any] = [None] * len(conversations)
        pending = list(range(len(conversations)))
        retry_counts = [0] * len(conversations)
        batch_attempt = 0

        while pending:
            current_indices = pending[:batch_size]
            pending = pending[len(current_indices) :]
            batch_attempt += 1
            batch_started_at = time.perf_counter()

            inputs = [conversations[index] for index in current_indices]
            try:
                batch_responses = await model.abatch(inputs, return_exceptions=True)
            except TypeError as error:
                # Keep support for simple custom Runnable implementations that expose
                # abatch(inputs) without LangChain's optional return_exceptions argument.
                if "unexpected keyword argument 'return_exceptions'" not in str(error):
                    raise
                batch_responses = await model.abatch(inputs)
            if len(batch_responses) != len(current_indices):
                msg = "The model returned a different number of responses than input conversations."
                raise ValueError(msg)

            rate_limited_indices: list[int] = []
            rate_limit_errors: list[Exception] = []
            other_errors: list[Exception] = []
            for index, response in zip(current_indices, batch_responses, strict=True):
                if isinstance(response, Exception):
                    if self._is_rate_limit_error(response):
                        rate_limited_indices.append(index)
                        rate_limit_errors.append(response)
                    else:
                        other_errors.append(response)
                else:
                    responses[index] = response

            batch_failed = len(rate_limit_errors) + len(other_errors)
            batch_succeeded = len(current_indices) - batch_failed
            batch_duration = time.perf_counter() - batch_started_at
            await logger.ainfo(
                f"Batch attempt {batch_attempt}: {batch_succeeded} succeeded, {batch_failed} failed "
                f"in {batch_duration:.2f} seconds"
            )

            if other_errors:
                raise other_errors[0]

            if rate_limited_indices:
                exhausted_error = next(
                    (
                        error
                        for index, error in zip(rate_limited_indices, rate_limit_errors, strict=True)
                        if retry_counts[index] >= max_retries
                    ),
                    None,
                )
                if exhausted_error is not None:
                    raise exhausted_error
                for index in rate_limited_indices:
                    retry_counts[index] += 1
                batch_size = max(1, batch_size // 2)
                retry_after = max(
                    (self._retry_after_seconds(error) or 0.0 for error in rate_limit_errors),
                    default=0.0,
                )
                retry_attempt = max(retry_counts[index] for index in rate_limited_indices)
                backoff = max(configured_delay, retry_after, min(2 ** (retry_attempt - 1), 30))
                await logger.awarning(
                    f"Model rate limit reached; retrying {len(rate_limited_indices)} request(s) "
                    f"with batch size {batch_size} after {backoff:.1f} seconds"
                )
                await asyncio.sleep(backoff)
                pending = rate_limited_indices + pending
            elif pending and configured_delay:
                await asyncio.sleep(configured_delay)

        return responses

    async def run_batch(self) -> DataFrame:
        """Process each row in df[column_name] with the language model asynchronously."""
        # Check if model is already an instance (for testing) or needs to be instantiated
        if isinstance(self.model, list):
            model = get_llm(
                model=self.model,
                user_id=self.user_id,
                api_key=self.api_key,
                watsonx_url=getattr(self, "base_url_ibm_watsonx", None),
                watsonx_project_id=getattr(self, "project_id", None),
            )
        else:
            # Model is already an instance (typically in tests)
            model = self.model

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

        started_at = time.perf_counter()
        total_rows = 0
        try:
            # Determine text input for each row
            if col_name:
                user_texts = df[col_name].astype(str).tolist()
            else:
                user_texts = [
                    self._format_row_as_toml(cast("dict[str, Any]", row)) for row in df.to_dict(orient="records")
                ]

            total_rows = len(user_texts)
            await logger.ainfo(f"Processing {total_rows} rows with batch run")

            # Prepare the batch of conversations
            conversations = [
                [{"role": "system", "content": system_msg}, {"role": "user", "content": text}]
                if system_msg
                else [{"role": "user", "content": text}]
                for text in user_texts
            ]

            # Configure the model with project info and callbacks
            # Some models (e.g., ChatWatsonx) may have serialization issues with with_config()
            # due to SecretStr or other non-serializable attributes
            try:
                model = model.with_config(
                    {
                        "run_name": self.display_name,
                        "project_name": self.get_project_name(),
                        "callbacks": self.get_langchain_callbacks(),
                    }
                )
            except (TypeError, ValueError, AttributeError) as e:
                # Log warning and continue without configuration
                await logger.awarning(
                    f"Could not configure model with callbacks and project info: {e!s}. "
                    "Proceeding with batch processing without configuration."
                )
            # Process bounded batches and track progress. Provider rate-limit responses
            # shrink the active batch size and retry only the requests that were limited.
            batch_responses = await self._run_conversations(model, conversations)
            responses_with_idx = list(zip(range(len(conversations)), batch_responses, strict=True))

            # Sort by index to maintain order
            responses_with_idx.sort(key=lambda x: x[0])

            # Build the final data with enhanced metadata
            rows: list[dict[str, Any]] = []
            for idx, (original_row, response) in enumerate(
                zip(df.to_dict(orient="records"), responses_with_idx, strict=False)
            ):
                response_msg = response[1]
                self._token_usage = accumulate_usage(self._token_usage, extract_usage_from_message(response_msg))
                response_text = response_msg.content if hasattr(response_msg, "content") else str(response_msg)
                row = self._create_base_row(
                    cast("dict[str, Any]", original_row), model_response=response_text, batch_index=idx
                )
                self._add_metadata(row, success=True, system_msg=system_msg)
                rows.append(row)

                # Log progress
                if (idx + 1) % max(1, total_rows // 10) == 0:
                    await logger.ainfo(f"Processed {idx + 1}/{total_rows} rows")

            await logger.ainfo("Batch processing completed successfully")
            success_rate = (len(rows) / total_rows * 100) if total_rows else 100.0
            await logger.ainfo(
                f"Batch processing summary: {len(rows)}/{total_rows} succeeded ({success_rate:.1f}%), "
                f"0 failed in "
                f"{time.perf_counter() - started_at:.2f} seconds"
            )
            return DataFrame(rows)

        except (KeyError, AttributeError) as e:
            # Handle data structure and attribute access errors
            await logger.aerror(f"Data processing error: {e!s}")
            await logger.aerror(
                f"Batch processing summary: 0 succeeded, {total_rows} failed in "
                f"{time.perf_counter() - started_at:.2f} seconds"
            )
            error_row = self._create_base_row(dict.fromkeys(df.columns, ""), model_response="", batch_index=-1)
            self._add_metadata(error_row, success=False, error=str(e))
            return DataFrame([error_row])
        except Exception as e:
            await logger.aerror(
                f"Batch processing aborted with no result table after {time.perf_counter() - started_at:.2f} "
                f"seconds: {e!s}"
            )
            raise
