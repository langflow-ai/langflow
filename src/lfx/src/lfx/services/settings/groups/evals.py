from pydantic import BaseModel, Field


class EvalsSettings(BaseModel):
    """Limits for dataset evaluations (behind ``LANGFLOW_FEATURE_EVALS``)."""

    evals_max_items: int = Field(default=1000, gt=0)
    """Most dataset items one evaluation run may execute."""
    evals_row_concurrency: int = Field(default=2, gt=0, le=16)
    """Rows of one run that execute at the same time."""
    evals_max_concurrency: int = Field(default=4, gt=0, le=64)
    """Rows that execute at the same time across every run in this process."""
    evals_row_timeout_s: float = Field(default=300.0, gt=0)
    """Seconds a single row (flow run plus scoring) may take before it is recorded as a timeout."""
    evals_actual_output_max_chars: int = Field(default=20000, gt=0)
    """Characters of a row's output kept in the results table; the full output stays in the trace."""
    evals_csv_max_rows: int = Field(default=5000, gt=0)
    """Most rows one CSV import may add to a dataset."""
    evals_csv_max_bytes: int = Field(default=20 * 1024 * 1024, gt=0)
    """Largest CSV upload, in bytes; the whole file is parsed in memory."""
    evals_judge_max_output_tokens: int = Field(default=300, gt=0)
    """Output token cap for each LLM judge call, so a misbehaving judge cannot run up cost."""
    evals_abort_after_identical_failures: int = Field(default=3, ge=0)
    """Stop a run once this many consecutive rows fail with the same error (0 never stops early)."""
