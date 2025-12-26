## Flow versioning (checkpointing)

Langflow uses `FlowVersion` to store immutable checkpoints of flow edits.

When you mutate a flow (especially `Flow.data`, `Flow.name`, `Flow.description`), you must also create a checkpoint in the **same database session/transaction** as the flow update.

- Call `save_flow_checkpoint(session=..., user_id=..., flow_id=..., flow_data=...)` before the request returns.
- Prefer calling it in the same code path that writes `Flow` to the DB (e.g. `update_flow`), and before the outer `flush()/commit`.
- Do not open a new session for checkpointing when you are already inside a `DbSession`; the checkpoint must commit/rollback atomically with the flow mutation.

Rationale: ensures the flow row and its version history cannot diverge.