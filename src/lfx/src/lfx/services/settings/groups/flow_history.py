from pydantic import BaseModel, Field


class FlowHistorySettings(BaseModel):
    """Operation history of flow graphs: how accepted edits are stored."""

    flow_op_log_row_ops_limit: int = Field(default=100, ge=1)
    """Maximum operations stored in one flow history row.

    Rows are only ever deleted whole, so smaller rows give compaction finer cut
    points. The default matches the checkpoint cadence so neither is coarser
    than configured.
    """
    flow_op_log_row_bytes_limit: int = Field(default=204800, ge=1024)
    """Maximum stored size of one flow history row's operations, in bytes.

    An operation listing many items (a large paste or import) is split across
    rows to stay within it. A single item is never split, so one node larger
    than the limit gets a row of its own; the default sits above the largest
    node in the starter projects (about 89 KB).
    """
    flow_revision_checkpoint_cadence: int = Field(default=100, ge=1)
    """Operations recorded between automatic checkpoints of a flow's graph.

    Replay starts from the newest checkpoint, so this bounds how far any read
    or save has to replay.
    """
    flow_revision_retention_window: int = Field(default=5000, ge=1)
    """Minimum number of a flow's most recent operations kept in its history.

    Older operations are compacted away behind a checkpoint. Counts operations,
    not rows. Saved versions are kept regardless, as snapshots.
    """
