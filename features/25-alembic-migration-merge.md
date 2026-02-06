# Feature 25: Alembic Migration Merge + Memory Path Migration

## Summary

Two new Alembic migration scripts:

1. **Memory Path Migration** (`bcbbf8c17c25`) -- Updates the memory component's module path in saved flows from `lfx.components.helpers.memory` to `lfx.components.models_agents.memory`, reflecting a reorganization of the component hierarchy.

2. **Branch Merge Migration** (`23c16fac4a0d`) -- A merge migration that reconciles three branch heads (`3671f35245e5`, `369268b9af8b`, `bcbbf8c17c25`) into a single migration lineage.

## Dependencies

- Depends on existing Alembic revisions: `d37bc4322900` (for memory path), and `3671f35245e5`, `369268b9af8b`, `bcbbf8c17c25` (for merge)
- Uses `langflow.utils.migration` utilities

## Files Changed

### 1. `src/backend/base/langflow/alembic/versions/23c16fac4a0d_merge_experimental_branches.py` (NEW)

Merge migration that unifies three migration heads into one. The `upgrade()` and `downgrade()` functions are no-ops since this is purely a structural merge.

```diff
diff --git a/src/backend/base/langflow/alembic/versions/23c16fac4a0d_merge_experimental_branches.py b/src/backend/base/langflow/alembic/versions/23c16fac4a0d_merge_experimental_branches.py
new file mode 100644
index 0000000000..d317cfba6d
--- /dev/null
+++ b/src/backend/base/langflow/alembic/versions/23c16fac4a0d_merge_experimental_branches.py
@@ -0,0 +1,31 @@
+"""merge_experimental_branches
+
+Revision ID: 23c16fac4a0d
+Revises: 3671f35245e5, 369268b9af8b, bcbbf8c17c25
+Create Date: 2026-02-03 23:52:53.170655
+
+"""
+from typing import Sequence, Union
+
+from alembic import op
+import sqlalchemy as sa
+import sqlmodel
+from sqlalchemy.engine.reflection import Inspector
+from langflow.utils import migration
+
+
+# revision identifiers, used by Alembic.
+revision: str = '23c16fac4a0d'
+down_revision: Union[str, None] = ('3671f35245e5', '369268b9af8b', 'bcbbf8c17c25')
+branch_labels: Union[str, Sequence[str], None] = None
+depends_on: Union[str, Sequence[str], None] = None
+
+
+def upgrade() -> None:
+    conn = op.get_bind()
+    pass
+
+
+def downgrade() -> None:
+    conn = op.get_bind()
+    pass
```

### 2. `src/backend/base/langflow/alembic/versions/bcbbf8c17c25_update_memory_component_path_from_.py` (NEW)

Data migration that uses SQL `REPLACE` to update the memory component's module path in the `flow` table's `data` column. Handles both upgrade (helpers -> models_agents) and downgrade (models_agents -> helpers) paths.

```diff
diff --git a/src/backend/base/langflow/alembic/versions/bcbbf8c17c25_update_memory_component_path_from_.py b/src/backend/base/langflow/alembic/versions/bcbbf8c17c25_update_memory_component_path_from_.py
new file mode 100644
index 0000000000..c7aecc6ad9
--- /dev/null
+++ b/src/backend/base/langflow/alembic/versions/bcbbf8c17c25_update_memory_component_path_from_.py
@@ -0,0 +1,73 @@
+"""update_memory_component_path_from_helpers_to_models_agents
+
+Revision ID: bcbbf8c17c25
+Revises: d37bc4322900
+Create Date: 2025-10-03 00:44:35.536421
+
+"""
+from typing import Sequence, Union
+
+from alembic import op
+import sqlalchemy as sa
+import sqlmodel
+from sqlalchemy.engine.reflection import Inspector
+from langflow.utils import migration
+
+
+# revision identifiers, used by Alembic.
+revision: str = 'bcbbf8c17c25'
+down_revision: Union[str, None] = 'd37bc4322900'
+branch_labels: Union[str, Sequence[str], None] = None
+depends_on: Union[str, Sequence[str], None] = None
+
+
+def upgrade() -> None:
+    conn = op.get_bind()
+
+    # Check if the flow table exists
+    inspector = sa.inspect(conn)
+    table_names = inspector.get_table_names()
+
+    if "flow" not in table_names:
+        # If flow table doesn't exist, skip this migration
+        return
+
+    # Update memory component path from helpers to models_agents in flow data
+    update_query = sa.text("""
+        UPDATE flow
+        SET data = REPLACE(data, 'lfx.components.helpers.memory', 'lfx.components.models_agents.memory'),
+            updated_at = CURRENT_TIMESTAMP
+        WHERE data LIKE '%lfx.components.helpers.memory%'
+    """)
+
+    result = conn.execute(update_query)
+
+    # Log the number of updated flows
+    if result.rowcount > 0:
+        print(f"Updated {result.rowcount} flows with new memory component path")
+
+
+def downgrade() -> None:
+    conn = op.get_bind()
+
+    # Check if the flow table exists
+    inspector = sa.inspect(conn)
+    table_names = inspector.get_table_names()
+
+    if "flow" not in table_names:
+        # If flow table doesn't exist, skip this migration
+        return
+
+    # Revert memory component path from models_agents back to helpers
+    update_query = sa.text("""
+        UPDATE flow
+        SET data = REPLACE(data, 'lfx.components.models_agents.memory', 'lfx.components.helpers.memory'),
+            updated_at = CURRENT_TIMESTAMP
+        WHERE data LIKE '%lfx.components.models_agents.memory%'
+    """)
+
+    result = conn.execute(update_query)
+
+    # Log the number of reverted flows
+    if result.rowcount > 0:
+        print(f"Reverted {result.rowcount} flows to old memory component path")
```

## Implementation Notes

1. **Memory path migration** -- This is a data-only migration (no schema changes). It uses raw SQL `REPLACE` on the JSON `data` column of the `flow` table. This is efficient but assumes the string `lfx.components.helpers.memory` only appears in the context of the module path and not as user content.

2. **Safety checks** -- Both migrations check for the existence of the `flow` table before executing, which handles fresh installations where the table may not yet exist.

3. **Merge migration** -- The merge migration (`23c16fac4a0d`) reconciles three separate branch heads. The `down_revision` is a tuple of three revision IDs, which is Alembic's standard pattern for merge migrations. The `upgrade()` and `downgrade()` functions are pass-through since no actual schema or data changes are needed at the merge point.

4. **Revision chain**: `d37bc4322900` -> `bcbbf8c17c25` (memory path), then `bcbbf8c17c25` + `3671f35245e5` + `369268b9af8b` -> `23c16fac4a0d` (merge).
