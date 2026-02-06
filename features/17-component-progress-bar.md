# Feature 17: Component Progress Bar

## Summary

Adds a progress bar system that allows backend components to report progress during long-running operations. A new `set_progress(current, total, message)` method on the `Component` base class sends progress events through the event manager to the frontend, where they are stored in the flow store and can be rendered as progress indicators on nodes. Includes a `ProgressTestComponent` for testing the feature end-to-end.

## Dependencies

- `src/lfx/src/lfx/events/event_manager.py` (existing -- registers the new `on_progress` event)
- `src/frontend/src/stores/flowStore.ts` (existing -- stores per-node progress state)
- `src/frontend/src/utils/buildUtils.ts` (existing -- handles SSE progress events)

## File Diffs

### `src/lfx/src/lfx/components/processing/progress_test.py` (new)

```diff
diff --git a/src/lfx/src/lfx/components/processing/progress_test.py b/src/lfx/src/lfx/components/processing/progress_test.py
new file mode 100644
index 0000000000..90a1062fe1
--- /dev/null
+++ b/src/lfx/src/lfx/components/processing/progress_test.py
@@ -0,0 +1,54 @@
+"""Test component for progress bar functionality."""
+
+import time
+
+from lfx.custom import Component
+from lfx.io import IntInput, Output
+from lfx.schema.data import Data
+
+
+class ProgressTestComponent(Component):
+    """Test component to demonstrate progress bar functionality."""
+
+    display_name = "Progress Test"
+    description = "Test component that simulates a long-running task with progress."
+    icon = "loader"
+    name = "ProgressTest"
+
+    inputs = [
+        IntInput(
+            name="num_steps",
+            display_name="Number of Steps",
+            info="Number of steps to simulate.",
+            value=10,
+        ),
+        IntInput(
+            name="delay_ms",
+            display_name="Delay (ms)",
+            info="Delay between steps in milliseconds.",
+            value=500,
+            advanced=True,
+        ),
+    ]
+
+    outputs = [
+        Output(
+            name="result",
+            display_name="Result",
+            method="run_test",
+        ),
+    ]
+
+    def run_test(self) -> Data:
+        """Run test loop with progress updates."""
+        total_steps = self.num_steps
+        delay_seconds = self.delay_ms / 1000
+
+        for step in range(1, total_steps + 1):
+            # Send progress update to frontend
+            self.set_progress(step, total_steps, f"Step {step}/{total_steps}")
+
+            # Simulate work
+            time.sleep(delay_seconds)
+
+        return Data(data={"completed_steps": total_steps, "status": "done"})
```

### `src/lfx/src/lfx/events/event_manager.py` (modified)

```diff
diff --git a/src/lfx/src/lfx/events/event_manager.py b/src/lfx/src/lfx/events/event_manager.py
index c154a4b3a0..b0120ab362 100644
--- a/src/lfx/src/lfx/events/event_manager.py
+++ b/src/lfx/src/lfx/events/event_manager.py
@@ -99,6 +99,7 @@ def create_default_event_manager(queue=None):
     manager.register_event("on_end_vertex", "end_vertex")
     manager.register_event("on_build_start", "build_start")
     manager.register_event("on_build_end", "build_end")
+    manager.register_event("on_progress", "progress")
     return manager
```

### `src/lfx/src/lfx/custom/custom_component/component.py` (modified -- `set_progress` method and context changes)

Note: This diff also contains changes to the `ctx` property (context getter/setter) and `_store_message` method which support stateless mode. The progress-specific addition is the `set_progress` method.

```diff
diff --git a/src/lfx/src/lfx/custom/custom_component/component.py b/src/lfx/src/lfx/custom/custom_component/component.py
index ca94821311..7744cdc583 100644
--- a/src/lfx/src/lfx/custom/custom_component/component.py
+++ b/src/lfx/src/lfx/custom/custom_component/component.py
@@ -298,10 +298,27 @@ class Component(CustomComponent):

     @property
     def ctx(self):
-        if not hasattr(self, "graph") or self.graph is None:
-            msg = "Graph not found. Please build the graph first."
-            raise ValueError(msg)
-        return self.graph.context
+        # First try: use the local _ctx if it exists and is not empty
+        if hasattr(self, "_ctx") and self._ctx:
+            return self._ctx
+        # Second try: use the graph context if available
+        if hasattr(self, "graph") and self.graph is not None:
+            return self.graph.context
+        # Fallback: return empty dict instead of raising error
+        # This allows components to work in isolation without a graph
+        return {}
+
+    @ctx.setter
+    def ctx(self, value: dict):
+        """Set the component's local context.
+
+        This allows passing context directly to a component without needing the full graph.
+        Useful for child components that need to inherit context from parent components.
+
+        Args:
+            value (dict): The context dictionary to set.
+        """
+        self._ctx = value

     def add_to_ctx(self, key: str, value: Any, *, overwrite: bool = False) -> None:
         """Add a key-value pair to the context.
@@ -1539,6 +1556,25 @@ class Component(CustomComponent):
             data["component_id"] = self._id
             self._event_manager.on_log(data=data)

+    def set_progress(self, current: int, total: int, message: str | None = None) -> None:
+        """Set progress for long-running operations (like batch processing).
+
+        Sends a progress event to the frontend to display a progress bar.
+
+        Args:
+            current: Current step number (1-indexed).
+            total: Total number of steps.
+            message: Optional message to display (e.g., "Processing batch 3/10").
+        """
+        if self._event_manager is not None:
+            progress_data = {
+                "id": self._id,
+                "current": current,
+                "total": total,
+                "message": message or f"Step {current}/{total}",
+            }
+            self._event_manager.on_progress(data=progress_data)
+
     def _append_tool_output(self) -> None:
         if next((output for output in self.outputs if output.name == TOOL_OUTPUT_NAME), None) is None:
             self.outputs.append(
@@ -1715,10 +1751,12 @@ class Component(CustomComponent):

     async def _store_message(self, message: Message) -> Message:
         flow_id: str | None = None
-        if hasattr(self, "graph"):
+        if hasattr(self, "graph") and self.graph:
             # Convert UUID to str if needed
             flow_id = str(self.graph.flow_id) if self.graph.flow_id else None
-        stored_messages = await astore_message(message, flow_id=flow_id)
+        # Get context for stateless mode support (ctx property always returns a dict)
+        context = self.ctx
+        stored_messages = await astore_message(message, flow_id=flow_id, context=context)
         if len(stored_messages) != 1:
             msg = "Only one message can be stored at a time."
             raise ValueError(msg)
```

### `src/frontend/src/stores/flowStore.ts` (modified -- nodeProgress state)

Note: This diff is large because it also contains HandleInput dynamic output updates and inspection panel visibility state. The progress-specific portions are the `nodeProgress`, `setNodeProgress`, and `clearAllNodeProgress` state entries.

```diff
diff --git a/src/frontend/src/stores/flowStore.ts b/src/frontend/src/stores/flowStore.ts
index 73c985bce5..7b6cbcd73c 100644
--- a/src/frontend/src/stores/flowStore.ts
+++ b/src/frontend/src/stores/flowStore.ts
@@ -11,6 +11,8 @@ import { create } from "zustand";
 import { checkCodeValidity } from "@/CustomNodes/helpers/check-code-validity";
 import { MISSED_ERROR_ALERT } from "@/constants/alerts_constants";
 import { BROKEN_EDGES_WARNING } from "@/constants/constants";
+import { api } from "@/controllers/API/api";
+import { getURL } from "@/controllers/API/helpers/constants";
 import { ENABLE_DATASTAX_LANGFLOW } from "@/customization/feature-flags";
 import {
   track,
@@ -57,7 +59,65 @@ import { useTweaksStore } from "./tweaksStore";
 import { useTypesStore } from "./typesStore";

 // this is our useStore hook that we can use in our components to get parts of the store and call actions
+// Helper function to update HandleInput outputs
+const updateHandleInputOutputs = (
+  targetNode: any,
+  targetHandle: any,
+  toolsValue: any[],
+  getState: () => any,
+  setState: (updates: any) => void,
+) => {
+  api
+    .post(getURL("CUSTOM_COMPONENT", { update: "update" }), {
+      code: targetNode.data.node.template.code?.value || "",
+      template: targetNode.data.node.template,
+      field: targetHandle.fieldName,
+      field_value: toolsValue,
+      tool_mode: targetNode.data.node.tool_mode || false,
+    })
+    .then((response) => {
+      const newTemplate = response.data;
+      newTemplate.last_updated = new Date().toISOString();
+
+      const updatedNode = cloneDeep(targetNode.data.node);
+      if ("template" in updatedNode) {
+        updatedNode.template = newTemplate.template;
+        updatedNode.outputs = newTemplate.outputs;
+        (updatedNode as any).last_updated = newTemplate.last_updated;
+      }
+
+      getState().setNode(targetNode.id, (oldNode) => ({
+        ...oldNode,
+        data: {
+          ...oldNode.data,
+          node: updatedNode,
+        },
+      }));
+    })
+    .catch((error) => {
+      console.error("Failed to update HandleInput outputs:", error);
+    });
+};
+
 const useFlowStore = create<FlowStoreType>((set, get) => ({
+  nodeProgress: {},
+  setNodeProgress: (nodeId, progress) => {
+    if (progress === null) {
+      const newProgress = { ...get().nodeProgress };
+      delete newProgress[nodeId];
+      set({ nodeProgress: newProgress });
+    } else {
+      set({
+        nodeProgress: {
+          ...get().nodeProgress,
+          [nodeId]: progress,
+        },
+      });
+    }
+  },
+  clearAllNodeProgress: () => {
+    set({ nodeProgress: {} });
+  },
   playgroundPage: false,
   setPlaygroundPage: (playgroundPage) => {
     set({ playgroundPage });
@@ -1076,6 +1249,7 @@ const useFlowStore = create<FlowStoreType>((set, get) => ({
       positionDictionary: {},
       componentsToUpdate: [],
       rightClickedNodeId: null,
+      nodeProgress: {},
     });
   },
```

### `src/frontend/src/utils/buildUtils.ts` (modified -- progress event handling)

Note: This diff also includes the coercion settings injection (Feature 12). The progress-specific portions are the `"progress"` case handler, the `end_vertex` progress clear, and the `"end"` event `clearAllNodeProgress` call.

```diff
diff --git a/src/frontend/src/utils/buildUtils.ts b/src/frontend/src/utils/buildUtils.ts
index 6e0237318c..8622400011 100644
--- a/src/frontend/src/utils/buildUtils.ts
+++ b/src/frontend/src/utils/buildUtils.ts
@@ -499,6 +509,9 @@ async function onEvent(
     }
     case "end_vertex": {
       const buildData = data.build_data;
+      // Clear progress for this node when it finishes
+      useFlowStore.getState().setNodeProgress(buildData.id, null);
+
       const startTimeMs = verticesStartTimeMs.get(buildData.id);
       if (startTimeMs) {
         const delta = Date.now() - startTimeMs;
@@ -577,6 +590,8 @@ async function onEvent(
       const allNodesValid = buildResults.every((result) => result);
       onBuildComplete && onBuildComplete(allNodesValid);
       useFlowStore.getState().setIsBuilding(false);
+      // Clear all progress when build ends
+      useFlowStore.getState().clearAllNodeProgress();
       return true;
     }
     case "error": {
@@ -598,6 +613,14 @@ async function onEvent(
     case "build_end":
       useFlowStore.getState().updateBuildStatus([data.id], BuildStatus.BUILT);
       break;
+    case "progress": {
+      // Handle progress events from components (e.g., batch processing)
+      const { id, current, total, message } = data;
+      if (id && typeof current === "number" && typeof total === "number") {
+        useFlowStore.getState().setNodeProgress(id, { current, total, message });
+      }
+      return true;
+    }
     default:
       return true;
   }
```

### `src/frontend/src/components/core/logCanvasControlsComponent/index.tsx` (modified)

```diff
diff --git a/src/frontend/src/components/core/logCanvasControlsComponent/index.tsx b/src/frontend/src/components/core/logCanvasControlsComponent/index.tsx
index 0d3f182f4d..e35cf3d9f8 100644
--- a/src/frontend/src/components/core/logCanvasControlsComponent/index.tsx
+++ b/src/frontend/src/components/core/logCanvasControlsComponent/index.tsx
@@ -1,25 +1,33 @@
 import { Panel } from "@xyflow/react";
 import ForwardedIconComponent from "@/components/common/genericIconComponent";
 import { Button } from "@/components/ui/button";
-import FlowLogsModal from "@/modals/flowLogsModal";
+import { useSidebar } from "@/components/ui/sidebar";

 const LogCanvasControls = () => {
+  const { setActiveSection, open, toggleSidebar } = useSidebar();
+
+  const handleOpenLogs = () => {
+    setActiveSection("logs");
+    if (!open) {
+      toggleSidebar();
+    }
+  };
+
   return (
     <Panel
       data-testid="canvas_controls"
       className="react-flow__controls !m-2 rounded-md"
       position="bottom-left"
     >
-      <FlowLogsModal>
-        <Button
-          variant="primary"
-          size="sm"
-          className="flex items-center !gap-1.5"
-        >
-          <ForwardedIconComponent name="Terminal" className="text-primary" />
-          <span className="text-mmd font-normal">Logs</span>
-        </Button>
-      </FlowLogsModal>
+      <Button
+        variant="primary"
+        size="sm"
+        className="flex items-center !gap-1.5"
+        onClick={handleOpenLogs}
+      >
+        <ForwardedIconComponent name="Terminal" className="text-primary" />
+        <span className="text-mmd font-normal">Logs</span>
+      </Button>
     </Panel>
   );
 };
```

## Implementation Notes

1. **Backend Event Flow**: The `set_progress` method on `Component` sends a progress event via `self._event_manager.on_progress(data=progress_data)`. The event manager has a new registered event `"on_progress"` that maps to the SSE event type `"progress"`.

2. **Frontend Event Handling**: In `buildUtils.ts`, the `onEvent` function handles `case "progress"` by extracting `{id, current, total, message}` from the event data and calling `useFlowStore.getState().setNodeProgress(id, { current, total, message })`.

3. **Progress Lifecycle**:
   - Progress is set during component execution via `set_progress(current, total, message)`
   - Progress is cleared for individual nodes on `end_vertex` events
   - All progress is cleared globally on `"end"` (build complete) events
   - The `nodeProgress` state is also cleared during store reset

4. **Store Shape**: The `nodeProgress` state in `flowStore` is a `Record<string, { current: number, total: number, message?: string } | null>` keyed by node ID. Setting progress to `null` removes the entry.

5. **Log Canvas Controls Change**: The `LogCanvasControls` component was refactored from using a `FlowLogsModal` wrapper to directly using the sidebar API (`useSidebar`). Clicking the "Logs" button now opens the sidebar's "logs" section instead of opening a separate modal. This is tangentially related to the progress feature since logs and progress are both displayed in the flow canvas area.

6. **Test Component**: `ProgressTestComponent` provides a simple way to verify the feature works end-to-end. It takes `num_steps` and `delay_ms` inputs and calls `self.set_progress()` in a loop with `time.sleep()` between steps.
