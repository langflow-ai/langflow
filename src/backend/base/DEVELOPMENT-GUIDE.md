## Flow versioning (checkpointing)

Langflow uses `FlowVersion` to store immutable checkpoints of flow edits.

When you mutate a flow (especially `Flow.data`, `Flow.name`, `Flow.description`), you must also create a checkpoint in the **same database session/transaction** as the flow update.

### Required
**ALWAYS call `save_flow_checkpoint` BEFORE updating the database object.**

`save_flow_checkpoint` works by comparing the *new data* you pass it against the *current data* in the database. If you update the database object first, the "old" data is lost (or the session sees the new data as the current data), and no change will be detected.

### Example: Updating a Flow

#### ✅ DO THIS
Create the checkpoint *before* applying changes to the DB object.

```python
# 1. Prepare your new data
new_flow_data = {...}
flow_update = FlowUpdate(data=new_flow_data)

# 2. Checkpoint FIRST (compares new_flow_data vs DB state)
await save_flow_checkpoint(
    session=session,
    flow_id=flow.id,
    user_id=user.id,
    flow=flow_update
)

# 3. Update the DB object
flow.data = new_flow_data
session.add(flow)
await session.commit()
```

#### ❌ DO NOT DO THIS
If you update the object first, SQLAlchemy may flush that change before the checkpoint query runs, making the DB look identical to your new data.

```python
# 1. Update the DB object first (BAD!)
flow.data = new_flow_data

# 2. Checkpoint too late
# The session now sees flow.data as the "current" state.
# save_flow_checkpoint will compare new_flow_data vs new_flow_data -> No Change detected.
await save_flow_checkpoint(
    session=session,
    flow_id=flow.id,
    user_id=user.id,
    flow=FlowUpdate(data=new_flow_data)
)
```
