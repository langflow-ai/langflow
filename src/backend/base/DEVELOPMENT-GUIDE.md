## Flow versioning (checkpointing)

Langflow uses `FlowVersion` to store snapshots of flow edits.

When you mutate a flow (particularly `Flow.data`), you must use `save_flow_checkpoint`. This function handles both the checkpoint creation (if `Flow.data` changes) and the update of the Flow object in the database.

### Required
**ALWAYS use `save_flow_checkpoint` to update flow data.**
`save_flow_checkpoint` updates the Flow row in the database and creates a new checkpoint (if needed) in the FlowVersion table in the same transaction.

`save_flow_checkpoint` compares the `update_data` you pass it against the *current data* in the database. It will:
1. Fetch the current flow from the database.
2. Compare the new data against the stored data.
3. If `Flow.data` (the graph) has changed, create a new `FlowVersion` entry.
4. Update the `Flow` object with the new values from `update_data`.
5. Return the updated `Flow` object.

### Example: Updating a Flow

#### ✅ DO THIS
Pass the session (optional), user ID, flow ID, and the dictionary of updates to `save_flow_checkpoint`.

```python
# 1. Prepare your new data (e.g. from a FlowUpdate model)
# update_data = flow_update.model_dump(exclude_unset=True, exclude_none=True)
update_data = {"data": {...}, "name": "New Name", "description": "New Desc"}

# 2. Checkpoint and Update
# save_flow_checkpoint updates the Flow row and creates a checkpoint (if needed)
# and returns the updated row in the Flow table
db_flow = await save_flow_checkpoint(
    session=session,
    flow_id=flow_id,
    user_id=user.id,
    update_data=update_data
)

# 3. Flush/Refresh if needed (e.g. to get updated timestamps or IDs)
await session.flush()
await session.refresh(db_flow)
```

#### ❌ DO NOT DO THIS
Do not update the database object manually before calling checkpoint, and do not expect `save_flow_checkpoint` to only handle versioning without updating the flow. (save_flow_checkpoint does both).

```python
# 1. Update the DB object first (BAD!)
flow.data = new_flow_data
session.add(flow)

# 2. Checkpoint too late or with wrong arguments
# The session might already see flow.data as the "current" state, missing the change.
await save_flow_checkpoint(...)
```
