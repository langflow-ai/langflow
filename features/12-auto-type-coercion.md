# Feature 12: Auto Type Coercion

## Summary

Adds automatic type coercion between Langflow's three primary data types: `Data`, `Message`, and `DataFrame`. When enabled via a settings page, these types become interchangeable -- handles display in a unified pink color, connections between them are allowed, and runtime values are automatically converted using the same logic as the Type Convert component. All other types (LanguageModel, Tool, Embeddings, Retriever, Memory, etc.) remain strictly typed regardless of the setting.

## Dependencies

- `src/lfx/src/lfx/components/processing/converter.py` (existing -- `parse_structured_data` function used for auto-parse)
- `src/lfx/src/lfx/schema/` (existing -- `Data`, `Message`, `DataFrame` classes and their `to_message()`, `to_data()`, `to_dataframe()` methods)
- `zustand` (frontend state management)
- `localStorage` (persists coercion settings client-side)

## File Diffs

### `src/lfx/src/lfx/graph/coercion.py` (new)

```diff
diff --git a/src/lfx/src/lfx/graph/coercion.py b/src/lfx/src/lfx/graph/coercion.py
new file mode 100644
index 0000000000..ef6f333aae
--- /dev/null
+++ b/src/lfx/src/lfx/graph/coercion.py
@@ -0,0 +1,230 @@
+"""Auto-coercion utilities for converting between Data, Message, and DataFrame types.
+
+This module provides utilities for automatic type coercion between Langflow's
+three primary data types: Data, Message, and DataFrame. The coercion is enabled
+via settings and uses the same conversion logic as the Type Convert component.
+
+IMPORTANT: Auto-coercion ONLY applies to these three types:
+- Data
+- Message
+- DataFrame
+
+All other types (LanguageModel, Tool, Embeddings, Retriever, Memory, etc.)
+remain strictly typed with no coercion, regardless of the setting.
+"""
+
+from __future__ import annotations
+
+from dataclasses import dataclass
+from typing import TYPE_CHECKING, Any
+
+if TYPE_CHECKING:
+    from lfx.schema import Data, DataFrame, Message
+
+# Types that can be coerced to each other
+COERCIBLE_TYPES = frozenset({"Data", "Message", "DataFrame"})
+
+
+@dataclass
+class CoercionSettings:
+    """Settings for auto-coercion behavior.
+
+    Attributes:
+        enabled: Whether auto-coercion is enabled
+        auto_parse: Whether to automatically parse JSON/CSV strings during conversion
+    """
+
+    enabled: bool = False
+    auto_parse: bool = False
+
+
+def is_coercible_type(type_name: str) -> bool:
+    """Check if a type name is a coercible type.
+
+    Args:
+        type_name: The type name to check
+
+    Returns:
+        True if the type is coercible (Data, Message, or DataFrame)
+    """
+    return type_name in COERCIBLE_TYPES
+
+
+def are_types_coercible(source_types: list[str], target_types: list[str]) -> bool:
+    """Check if source and target types can be coerced.
+
+    Args:
+        source_types: List of source output types
+        target_types: List of target input types
+
+    Returns:
+        True if both have at least one coercible type
+    """
+    source_coercible = any(t in COERCIBLE_TYPES for t in source_types)
+    target_coercible = any(t in COERCIBLE_TYPES for t in target_types)
+    return source_coercible and target_coercible
+
+
+def convert_to_message(value: Any) -> Message:
+    """Convert input to Message type.
+
+    Uses the same logic as the Type Convert component.
+
+    Args:
+        value: Input to convert (Message, Data, DataFrame, or dict)
+
+    Returns:
+        Message: Converted Message object
+    """
+    from lfx.schema import Message
+
+    if isinstance(value, Message):
+        return value
+
+    # For Data and DataFrame, use their to_message() method
+    if hasattr(value, "to_message"):
+        return value.to_message()
+
+    # For dicts, create a Message from text if present
+    if isinstance(value, dict):
+        text = value.get("text", str(value))
+        return Message(text=text)
+
+    # Fallback: convert to string
+    return Message(text=str(value))
+
+
+def convert_to_data(value: Any, *, auto_parse: bool = False) -> Data:
+    """Convert input to Data type.
+
+    Uses the same logic as the Type Convert component.
+
+    Args:
+        value: Input to convert (Message, Data, DataFrame, or dict)
+        auto_parse: Enable automatic parsing of structured data (JSON/CSV)
+
+    Returns:
+        Data: Converted Data object
+    """
+    from lfx.components.processing.converter import parse_structured_data
+    from lfx.schema import Data, DataFrame, Message
+
+    if isinstance(value, Data) and not isinstance(value, (Message, DataFrame)):
+        return value
+
+    if isinstance(value, dict):
+        return Data(value)
+
+    if isinstance(value, Message):
+        data = Data(data={"text": value.data.get("text", "")})
+        return parse_structured_data(data) if auto_parse else data
+
+    if isinstance(value, DataFrame):
+        return value.to_data()
+
+    # For other types with to_data method
+    if hasattr(value, "to_data"):
+        return value.to_data()
+
+    # Fallback
+    return Data(data={"value": value})
+
+
+def convert_to_dataframe(value: Any, *, auto_parse: bool = False) -> DataFrame:
+    """Convert input to DataFrame type.
+
+    Uses the same logic as the Type Convert component.
+
+    Args:
+        value: Input to convert (Message, Data, DataFrame, or dict)
+        auto_parse: Enable automatic parsing of structured data (JSON/CSV)
+
+    Returns:
+        DataFrame: Converted DataFrame object
+    """
+    import pandas as pd
+
+    from lfx.components.processing.converter import parse_structured_data
+    from lfx.schema import Data, DataFrame, Message
+
+    if isinstance(value, DataFrame):
+        return value
+
+    if isinstance(value, dict):
+        return DataFrame([value])
+
+    # Handle pandas DataFrame
+    if isinstance(value, pd.DataFrame):
+        return DataFrame(data=value)
+
+    if isinstance(value, Message):
+        data = Data(data={"text": value.data.get("text", "")})
+        if auto_parse:
+            return parse_structured_data(data).to_dataframe()
+        return data.to_dataframe()
+
+    if isinstance(value, Data):
+        return value.to_dataframe()
+
+    # For other types with to_dataframe method
+    if hasattr(value, "to_dataframe"):
+        return value.to_dataframe()
+
+    # Fallback
+    return DataFrame([{"value": value}])
+
+
+def auto_coerce_value(value: Any, expected_type: str, settings: CoercionSettings) -> Any:
+    """Auto-convert between Data, Message, DataFrame when types differ.
+
+    Uses the same conversion logic as the Type Convert component.
+    Only coerces if:
+    1. Settings are enabled
+    2. Expected type is a coercible type
+    3. Actual value type is also a coercible type
+
+    Args:
+        value: The value to potentially coerce
+        expected_type: The expected type name (e.g., "Message", "Data", "DataFrame")
+        settings: The coercion settings
+
+    Returns:
+        The coerced value if coercion applies, otherwise the original value
+    """
+    if not settings.enabled:
+        return value
+
+    if expected_type not in COERCIBLE_TYPES:
+        return value
+
+    # Get actual type name
+    actual_type = type(value).__name__
+    if actual_type == expected_type:
+        return value
+
+    if actual_type not in COERCIBLE_TYPES:
+        return value
+
+    # Apply conversion based on expected type
+    if expected_type == "Message":
+        return convert_to_message(value)
+    if expected_type == "Data":
+        return convert_to_data(value, auto_parse=settings.auto_parse)
+    if expected_type == "DataFrame":
+        return convert_to_dataframe(value, auto_parse=settings.auto_parse)
+
+    return value
+
+
+def auto_coerce_list(values: list, expected_type: str, settings: CoercionSettings) -> list:
+    """Coerce a list of values to the expected type.
+
+    Args:
+        values: List of values to coerce
+        expected_type: The expected type for each value
+        settings: The coercion settings
+
+    Returns:
+        List of coerced values
+    """
+    return [auto_coerce_value(v, expected_type, settings) for v in values]
```

### `src/lfx/src/lfx/graph/edge/base.py` (modified)

```diff
diff --git a/src/lfx/src/lfx/graph/edge/base.py b/src/lfx/src/lfx/graph/edge/base.py
index a053148c90..36c29b1fa6 100644
--- a/src/lfx/src/lfx/graph/edge/base.py
+++ b/src/lfx/src/lfx/graph/edge/base.py
@@ -2,6 +2,7 @@ from __future__ import annotations

 from typing import TYPE_CHECKING, Any, cast

+from lfx.graph.coercion import COERCIBLE_TYPES, are_types_coercible
 from lfx.graph.edge.schema import EdgeData, LoopTargetHandleDict, SourceHandle, TargetHandle, TargetHandleDict
 from lfx.log.logger import logger
 from lfx.schema.schema import INPUT_FIELD_NAME
@@ -81,6 +82,15 @@ class Edge:
             self._validate_handles(source, target)

     def _validate_handles(self, source, target) -> None:
+        # AUTO-COERCION CHECK: If coercion is enabled, allow connection between coercible types
+        coercion_settings = getattr(source.graph, "coercion_settings", None)
+        if coercion_settings and coercion_settings.enabled:
+            source_types = list(self.source_handle.output_types or [])
+            target_types = list(self.target_handle.input_types or [])
+            if are_types_coercible(source_types, target_types):
+                self.valid_handles = True
+                return
+
         if self.target_handle.input_types is None:
             self.valid_handles = self.target_handle.type in self.source_handle.output_types
         elif self.target_handle.type is None:
@@ -150,6 +160,20 @@ class Edge:
         # meaning: check for "types" key in each dictionary
         self.source_types = [output for output in source.outputs if output["name"] == self.source_handle.name]

+        # AUTO-COERCION CHECK: If coercion is enabled, allow connection between coercible types
+        coercion_settings = getattr(source.graph, "coercion_settings", None)
+        if coercion_settings and coercion_settings.enabled:
+            source_output_types = [t for output in self.source_types for t in output.get("types", [])]
+            target_input_types = list(self.target_handle.input_types or [])
+            if are_types_coercible(source_output_types, target_input_types):
+                self.valid = True
+                # Set matched_type to the first coercible source type for runtime conversion
+                self.matched_type = next(
+                    (t for t in source_output_types if t in COERCIBLE_TYPES),
+                    source_output_types[0] if source_output_types else None,
+                )
+                return
+
         # Check if this is an loop input (loop target handle with output_types)
         is_loop_input = hasattr(self.target_handle, "input_types") and self.target_handle.input_types
         loop_input_types = []
```

### `src/lfx/src/lfx/graph/vertex/base.py` (modified)

```diff
diff --git a/src/lfx/src/lfx/graph/vertex/base.py b/src/lfx/src/lfx/graph/vertex/base.py
index 0809777527..3489109e3a 100644
--- a/src/lfx/src/lfx/graph/vertex/base.py
+++ b/src/lfx/src/lfx/graph/vertex/base.py
@@ -12,6 +12,7 @@ from ag_ui.core import StepFinishedEvent, StepStartedEvent

 from lfx.events.observability.lifecycle_events import observable
 from lfx.exceptions.component import ComponentBuildError
+from lfx.graph.coercion import COERCIBLE_TYPES, auto_coerce_list, auto_coerce_value
 from lfx.graph.schema import INPUT_COMPONENTS, OUTPUT_COMPONENTS, InterfaceComponentTypes, ResultData
 from lfx.graph.utils import UnbuiltObject, UnbuiltResult, emit_build_start_event, log_transaction
 from lfx.graph.vertex.param_handler import ParameterHandler
@@ -513,6 +514,10 @@ class Vertex:
                 self.params[key][sub_key] = value
             else:
                 result = await value.get_result(self, target_handle_name=key)
+
+                # AUTO-COERCION: Apply type coercion if enabled and applicable
+                result = self._apply_coercion_if_needed(key, result)
+
                 self.params[key][sub_key] = result

     @staticmethod
@@ -580,11 +585,48 @@ class Vertex:
     async def _build_vertex_and_update_params(self, key, vertex: Vertex) -> None:
         """Builds a given vertex and updates the params dictionary accordingly."""
         result = await vertex.get_result(self, target_handle_name=key)
+
+        # AUTO-COERCION: Apply type coercion if enabled and applicable
+        result = self._apply_coercion_if_needed(key, result)
+
         self._handle_func(key, result)
         if isinstance(result, list):
             self._extend_params_list_with_result(key, result)
         self.params[key] = result

+    def _get_expected_type_for_param(self, key: str) -> str | None:
+        """Get the expected type for a parameter from the template definition."""
+        template_dict = self.data.get("node", {}).get("template", {})
+        field_def = template_dict.get(key, {})
+
+        # Check input_types first (more specific)
+        input_types = field_def.get("input_types", [])
+        if input_types:
+            # Return the first coercible type if any, otherwise first type
+            for t in input_types:
+                if t in COERCIBLE_TYPES:
+                    return t
+            return input_types[0] if input_types else None
+
+        # Fall back to type field
+        return field_def.get("type")
+
+    def _apply_coercion_if_needed(self, key: str, result: Any) -> Any:
+        """Apply auto-coercion to the result if enabled and applicable."""
+        coercion_settings = getattr(self.graph, "coercion_settings", None)
+        if not coercion_settings or not coercion_settings.enabled:
+            return result
+
+        expected_type = self._get_expected_type_for_param(key)
+        if not expected_type:
+            return result
+
+        # Handle list of values
+        if isinstance(result, list):
+            return auto_coerce_list(result, expected_type, coercion_settings)
+
+        return auto_coerce_value(result, expected_type, coercion_settings)
+
     async def _build_list_of_vertices_and_update_params(
         self,
         key,
@@ -594,6 +636,10 @@ class Vertex:
         self.params[key] = []
         for vertex in vertices:
             result = await vertex.get_result(self, target_handle_name=key)
+
+            # AUTO-COERCION: Apply type coercion if enabled and applicable
+            result = self._apply_coercion_if_needed(key, result)
+
             # Weird check to see if the params[key] is a list
             # because sometimes it is a Data and breaks the code
             if not isinstance(self.params[key], list):
```

### `src/lfx/src/lfx/graph/schema.py` (modified)

```diff
diff --git a/src/lfx/src/lfx/graph/schema.py b/src/lfx/src/lfx/graph/schema.py
index 38c6610715..1fae309686 100644
--- a/src/lfx/src/lfx/graph/schema.py
+++ b/src/lfx/src/lfx/graph/schema.py
@@ -52,6 +52,8 @@ class InterfaceComponentTypes(str, Enum, metaclass=ContainsEnumMeta):
     ChatOutput = "ChatOutput"
     TextInput = "TextInput"
     TextOutput = "TextOutput"
+    APIResponse = "APIResponse"
+    JSONInput = "JSONInput"
     DataOutput = "DataOutput"
     WebhookInput = "Webhook"

@@ -62,11 +64,13 @@ INPUT_COMPONENTS = [
     InterfaceComponentTypes.ChatInput,
     InterfaceComponentTypes.WebhookInput,
     InterfaceComponentTypes.TextInput,
+    InterfaceComponentTypes.JSONInput,
 ]
 OUTPUT_COMPONENTS = [
     InterfaceComponentTypes.ChatOutput,
     InterfaceComponentTypes.DataOutput,
     InterfaceComponentTypes.TextOutput,
+    InterfaceComponentTypes.APIResponse,
 ]
```

### `src/lfx/src/lfx/graph/__init__.py` (modified)

```diff
diff --git a/src/lfx/src/lfx/graph/__init__.py b/src/lfx/src/lfx/graph/__init__.py
index 925d463686..96b82e7534 100644
--- a/src/lfx/src/lfx/graph/__init__.py
+++ b/src/lfx/src/lfx/graph/__init__.py
@@ -1,6 +1,16 @@
+from lfx.graph.coercion import COERCIBLE_TYPES, CoercionSettings
 from lfx.graph.edge.base import Edge
 from lfx.graph.graph.base import Graph
 from lfx.graph.vertex.base import Vertex
 from lfx.graph.vertex.vertex_types import CustomComponentVertex, InterfaceVertex, StateVertex

-__all__ = ["CustomComponentVertex", "Edge", "Graph", "InterfaceVertex", "StateVertex", "Vertex"]
+__all__ = [
+    "COERCIBLE_TYPES",
+    "CoercionSettings",
+    "CustomComponentVertex",
+    "Edge",
+    "Graph",
+    "InterfaceVertex",
+    "StateVertex",
+    "Vertex",
+]
```

### `src/frontend/src/stores/coercionStore.ts` (new)

```diff
diff --git a/src/frontend/src/stores/coercionStore.ts b/src/frontend/src/stores/coercionStore.ts
new file mode 100644
index 0000000000..a16829a635
--- /dev/null
+++ b/src/frontend/src/stores/coercionStore.ts
@@ -0,0 +1,103 @@
+import { create } from "zustand";
+
+/**
+ * Types that are interchangeable when auto-coercion is enabled.
+ * Only these three types can be coerced to each other.
+ * All other types (LanguageModel, Tool, Embeddings, etc.) remain strictly typed.
+ */
+export const COERCIBLE_TYPES = ["Data", "Message", "DataFrame"];
+
+type CoercionSettings = {
+  enabled: boolean;
+  autoParse: boolean; // Detect and convert JSON/CSV strings (mirrors Type Convert component)
+};
+
+type CoercionStoreType = {
+  coercionSettings: CoercionSettings;
+  setCoercionEnabled: (value: boolean) => void;
+  setAutoParse: (value: boolean) => void;
+  isCoercibleType: (type: string) => boolean;
+  areTypesCoercible: (sourceTypes: string[], targetTypes: string[]) => boolean;
+};
+
+const DEFAULT_SETTINGS: CoercionSettings = {
+  enabled: false,
+  autoParse: false,
+};
+
+const STORAGE_KEY = "coercionSettings";
+
+const loadSettings = (): CoercionSettings => {
+  try {
+    const stored = window.localStorage.getItem(STORAGE_KEY);
+    if (stored) {
+      const parsed = JSON.parse(stored);
+      // Validate the parsed object has the expected shape
+      if (
+        typeof parsed.enabled === "boolean" &&
+        typeof parsed.autoParse === "boolean"
+      ) {
+        return parsed;
+      }
+    }
+  } catch (e) {
+    console.warn("Failed to load coercion settings from localStorage:", e);
+  }
+  return DEFAULT_SETTINGS;
+};
+
+const saveSettings = (settings: CoercionSettings) => {
+  try {
+    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
+  } catch (e) {
+    console.warn("Failed to save coercion settings to localStorage:", e);
+  }
+};
+
+export const useCoercionStore = create<CoercionStoreType>((set, get) => ({
+  coercionSettings: loadSettings(),
+
+  setCoercionEnabled: (value: boolean) => {
+    const newSettings = { ...get().coercionSettings, enabled: value };
+    saveSettings(newSettings);
+    set({ coercionSettings: newSettings });
+  },
+
+  setAutoParse: (value: boolean) => {
+    const newSettings = { ...get().coercionSettings, autoParse: value };
+    saveSettings(newSettings);
+    set({ coercionSettings: newSettings });
+  },
+
+  /**
+   * Check if a single type is coercible (Data, Message, or DataFrame)
+   */
+  isCoercibleType: (type: string): boolean => {
+    return COERCIBLE_TYPES.includes(type);
+  },
+
+  /**
+   * Check if two sets of types can be coerced to each other.
+   * Returns true only if auto-coercion is enabled AND both have at least one coercible type.
+   */
+  areTypesCoercible: (
+    sourceTypes: string[],
+    targetTypes: string[],
+  ): boolean => {
+    const { coercionSettings } = get();
+    if (!coercionSettings.enabled) {
+      return false;
+    }
+
+    const sourceHasCoercible = sourceTypes.some((t) =>
+      COERCIBLE_TYPES.includes(t),
+    );
+    const targetHasCoercible = targetTypes.some((t) =>
+      COERCIBLE_TYPES.includes(t),
+    );
+
+    return sourceHasCoercible && targetHasCoercible;
+  },
+}));
+
+export default useCoercionStore;
```

### `src/frontend/src/pages/SettingsPage/pages/TypeCoercionPage/index.tsx` (new)

```diff
diff --git a/src/frontend/src/pages/SettingsPage/pages/TypeCoercionPage/index.tsx b/src/frontend/src/pages/SettingsPage/pages/TypeCoercionPage/index.tsx
new file mode 100644
index 0000000000..9dfcf9a9ae
--- /dev/null
+++ b/src/frontend/src/pages/SettingsPage/pages/TypeCoercionPage/index.tsx
@@ -0,0 +1,139 @@
+import ForwardedIconComponent from "@/components/common/genericIconComponent";
+import { Label } from "@/components/ui/label";
+import { Switch } from "@/components/ui/switch";
+import { useCoercionStore } from "@/stores/coercionStore";
+
+export default function TypeCoercionPage() {
+  const { coercionSettings, setCoercionEnabled, setAutoParse } =
+    useCoercionStore();
+
+  return (
+    <div className="flex h-full w-full flex-col gap-6">
+      <div className="flex w-full items-start justify-between gap-6">
+        <div className="flex w-full flex-col">
+          <h2
+            className="flex items-center text-lg font-semibold tracking-tight"
+            data-testid="settings_menu_header"
+          >
+            Type Coercion
+            <ForwardedIconComponent
+              name="Repeat"
+              className="ml-2 h-5 w-5 text-primary"
+            />
+          </h2>
+          <p className="text-sm text-muted-foreground">
+            Configure automatic type conversion between Data, Message, and
+            DataFrame types.
+          </p>
+        </div>
+      </div>
+
+      <div className="grid gap-6 pb-8">
+        {/* Enable Auto-Coercion */}
+        <div className="flex flex-col space-y-4 rounded-lg border border-border p-4">
+          <div className="flex items-center justify-between">
+            <div className="flex flex-col space-y-1">
+              <Label
+                htmlFor="auto-coercion-toggle"
+                className="text-sm font-medium"
+              >
+                Enable Auto-Coercion
+              </Label>
+              <p className="text-sm text-muted-foreground">
+                Allow Data, Message, and DataFrame types to connect
+                interchangeably. When enabled, handles for these types will
+                display with a unified violet color.
+              </p>
+            </div>
+            <Switch
+              id="auto-coercion-toggle"
+              checked={coercionSettings.enabled}
+              onCheckedChange={setCoercionEnabled}
+              data-testid="auto-coercion-toggle"
+            />
+          </div>
+
+          {/* Visual indicator */}
+          {coercionSettings.enabled && (
+            <div className="flex items-center gap-2 rounded-md bg-accent/50 p-3 text-sm">
+              <ForwardedIconComponent
+                name="Info"
+                className="h-4 w-4 text-pink-500"
+              />
+              <span>
+                Coercible types (Data, Message, DataFrame) will now show{" "}
+                <span className="font-medium text-pink-500">pink</span> colored
+                handles and can connect to each other.
+              </span>
+            </div>
+          )}
+        </div>
+
+        {/* Auto Parse (only shown when coercion is enabled) */}
+        {coercionSettings.enabled && (
+          <div className="flex flex-col space-y-4 rounded-lg border border-border p-4">
+            <div className="flex items-center justify-between">
+              <div className="flex flex-col space-y-1">
+                <Label
+                  htmlFor="auto-parse-toggle"
+                  className="text-sm font-medium"
+                >
+                  Auto Parse
+                </Label>
+                <p className="text-sm text-muted-foreground">
+                  Automatically detect and convert JSON/CSV strings when
+                  transforming between types. This mirrors the behavior of the
+                  Type Convert component&apos;s auto_parse option.
+                </p>
+              </div>
+              <Switch
+                id="auto-parse-toggle"
+                checked={coercionSettings.autoParse}
+                onCheckedChange={setAutoParse}
+                data-testid="auto-parse-toggle"
+              />
+            </div>
+          </div>
+        )}
+
+        {/* Information Card */}
+        <div className="rounded-lg border border-border bg-muted/30 p-4">
+          <h3 className="mb-2 flex items-center gap-2 text-sm font-medium">
+            <ForwardedIconComponent name="HelpCircle" className="h-4 w-4" />
+            How Auto-Coercion Works
+          </h3>
+          <div className="space-y-2 text-sm text-muted-foreground">
+            <p>
+              When auto-coercion is enabled, the following conversions happen
+              automatically at runtime:
+            </p>
+            <ul className="list-inside list-disc space-y-1 pl-2">
+              <li>
+                <strong>Data → Message:</strong> Converts using the{" "}
+                <code className="rounded bg-muted px-1">to_message()</code>{" "}
+                method
+              </li>
+              <li>
+                <strong>Message → Data:</strong> Extracts text content into a
+                Data object
+              </li>
+              <li>
+                <strong>DataFrame → Message:</strong> Converts to a markdown
+                table representation
+              </li>
+              <li>
+                <strong>Data → DataFrame:</strong> Creates a single-row
+                DataFrame
+              </li>
+            </ul>
+            <p className="mt-3">
+              <strong>Note:</strong> Other types (LanguageModel, Tool,
+              Embeddings, etc.) remain strictly typed and are not affected by
+              this setting.
+            </p>
+          </div>
+        </div>
+      </div>
+    </div>
+  );
+}
```

### `src/frontend/src/pages/SettingsPage/index.tsx` (modified)

```diff
diff --git a/src/frontend/src/pages/SettingsPage/index.tsx b/src/frontend/src/pages/SettingsPage/index.tsx
index a0ceadf6f4..4975963f57 100644
--- a/src/frontend/src/pages/SettingsPage/index.tsx
+++ b/src/frontend/src/pages/SettingsPage/index.tsx
@@ -89,6 +89,16 @@ export default function SettingsPage(): JSX.Element {
         />
       ),
     },
+    {
+      title: "Type Coercion",
+      href: "/settings/type-coercion",
+      icon: (
+        <ForwardedIconComponent
+          name="Repeat"
+          className="w-4 flex-shrink-0 justify-start stroke-[1.5]"
+        />
+      ),
+    },
   );

   // TODO: Remove this on cleanup
```

### `src/frontend/src/routes.tsx` (modified -- type-coercion route)

Note: This diff also contains routes for other features (datasets, evaluations). The type-coercion-specific change is the `TypeCoercionPage` import and the `/settings/type-coercion` route.

```diff
diff --git a/src/frontend/src/routes.tsx b/src/frontend/src/routes.tsx
index ee83364126..fcca9e892c 100644
--- a/src/frontend/src/routes.tsx
+++ b/src/frontend/src/routes.tsx
@@ -15,6 +15,7 @@ import { CustomNavigate } from "./customization/components/custom-navigate";
 import { BASENAME } from "./customization/config-constants";
 import {
   ENABLE_CUSTOM_PARAM,
+  ENABLE_DATASETS,
   ENABLE_FILE_MANAGEMENT,
   ENABLE_KNOWLEDGE_BASES,
 } from "./customization/feature-flags";
@@ -25,6 +26,8 @@ import { AppInitPage } from "./pages/AppInitPage";
 import { AppWrapperPage } from "./pages/AppWrapperPage";
 import FlowPage from "./pages/FlowPage";
 import LoginPage from "./pages/LoginPage";
+import DatasetDetailPage from "./pages/MainPage/pages/datasetDetailPage";
+import DatasetsPage from "./pages/MainPage/pages/datasetsPage";
 import FilesPage from "./pages/MainPage/pages/filesPage";
 import HomePage from "./pages/MainPage/pages/homePage";
 import KnowledgePage from "./pages/MainPage/pages/knowledgePage";
@@ -37,6 +40,7 @@ import MCPServersPage from "./pages/SettingsPage/pages/MCPServersPage";
 import ModelProvidersPage from "./pages/SettingsPage/pages/ModelProvidersPage";
 import MessagesPage from "./pages/SettingsPage/pages/messagesPage";
 import ShortcutsPage from "./pages/SettingsPage/pages/ShortcutsPage";
+import TypeCoercionPage from "./pages/SettingsPage/pages/TypeCoercionPage";
 import ViewPage from "./pages/ViewPage";

 const AdminPage = lazy(() => import("./pages/AdminPage"));
@@ -44,6 +48,7 @@ const LoginAdminPage = lazy(() => import("./pages/AdminPage/LoginPage"));
 const DeleteAccountPage = lazy(() => import("./pages/DeleteAccountPage"));

 const PlaygroundPage = lazy(() => import("./pages/Playground"));
+const EvaluationPage = lazy(() => import("./pages/EvaluationPage"));

 const SignUp = lazy(() => import("./pages/SignUpPage"));

@@ -97,6 +102,15 @@ const router = createBrowserRouter(
                           element={<KnowledgePage />}
                         />
                       )}
+                      {ENABLE_DATASETS && (
+                        <>
+                          <Route path="datasets" element={<DatasetsPage />} />
+                          <Route
+                            path="datasets/:datasetId"
+                            element={<DatasetDetailPage />}
+                          />
+                        </>
+                      )}
                     </Route>
                   )}
                   <Route
@@ -157,6 +171,7 @@ const router = createBrowserRouter(
                   />
                   <Route path="shortcuts" element={<ShortcutsPage />} />
                   <Route path="messages" element={<MessagesPage />} />
+                  <Route path="type-coercion" element={<TypeCoercionPage />} />
                   {CustomRoutesStore()}
                 </Route>
                 {CustomRoutesStorePages()}
@@ -179,6 +194,9 @@ const router = createBrowserRouter(
                 </Route>
                 <Route path="view" element={<ViewPage />} />
               </Route>
+              <Route path="evaluations/:evaluationId" element={<CustomDashboardWrapperPage />}>
+                <Route path="" element={<EvaluationPage />} />
+              </Route>
             </Route>
           </Route>
           <Route
```

### `src/frontend/src/utils/styleUtils.ts` (modified -- coercion colors)

```diff
diff --git a/src/frontend/src/utils/styleUtils.ts b/src/frontend/src/utils/styleUtils.ts
index cbea3da46e..65c69f95cb 100644
--- a/src/frontend/src/utils/styleUtils.ts
+++ b/src/frontend/src/utils/styleUtils.ts
@@ -188,6 +188,27 @@ export const nodeColorsName: { [char: string]: string } = {
   DataFrame: "pink",
 };

+/**
+ * Colors that correspond to coercible types (Data, Message, DataFrame):
+ * - Data = "red"
+ * - Message = "indigo"
+ * - DataFrame = "pink"
+ */
+const COERCIBLE_COLORS = new Set(["red", "indigo", "pink"]);
+
+/**
+ * Unified color for coercible types when auto-coercion is enabled.
+ */
+export const COERCION_UNIFIED_COLOR_NAME = "pink";
+
+/**
+ * Check if any color in the array is a coercible type's color.
+ * Used to determine if a handle should show the unified coercion color.
+ */
+export const hasCoercibleColor = (colors: string[]): boolean => {
+  return colors.some((c) => COERCIBLE_COLORS.has(c));
+};
+
 export const FILE_ICONS = {
   json: {
     icon: "FileJson",
```

### `src/frontend/src/utils/buildUtils.ts` (modified -- coercion settings injection)

Note: This diff also contains progress bar event handling (Feature 17). The coercion-specific portion is the injection of `coercion_settings` into the build POST data.

```diff
diff --git a/src/frontend/src/utils/buildUtils.ts b/src/frontend/src/utils/buildUtils.ts
index 6e0237318c..8622400011 100644
--- a/src/frontend/src/utils/buildUtils.ts
+++ b/src/frontend/src/utils/buildUtils.ts
@@ -7,6 +7,7 @@ import {
   POLLING_MESSAGES,
 } from "@/constants/constants";
 import { performStreamingRequest } from "@/controllers/API/api";
+import { useCoercionStore } from "@/stores/coercionStore";
 import {
   customBuildUrl,
   customCancelBuildUrl,
@@ -259,6 +260,15 @@ export async function buildFlowVertices({
     postData["inputs"] = inputs;
   }

+  // Add coercion settings if enabled
+  const coercionSettings = useCoercionStore.getState().coercionSettings;
+  if (coercionSettings.enabled) {
+    postData["coercion_settings"] = {
+      enabled: coercionSettings.enabled,
+      auto_parse: coercionSettings.autoParse,
+    };
+  }
+
   try {
     // If event_delivery is direct, we'll stream from the build endpoint directly
     if (eventDelivery === EventDeliveryType.DIRECT) {
```

## Implementation Notes

1. **Backend Architecture**: The `coercion.py` module is a standalone utility module in `src/lfx/src/lfx/graph/`. It defines `CoercionSettings` as a dataclass and provides pure functions for type checking and conversion. The `Graph` object is expected to have a `coercion_settings` attribute (set from the frontend's build request).

2. **Edge Validation**: Two coercion checks are added to `Edge._validate_handles()` and `Edge.validate_edge()`. Both check `source.graph.coercion_settings` early in validation, short-circuiting to `valid=True` if both source and target types are coercible.

3. **Vertex Runtime Coercion**: The `Vertex` class applies coercion at three points where results flow between vertices: `_build_vertex_and_update_params`, `_build_list_of_vertices_and_update_params`, and the dictionary-based param builder. Each calls `_apply_coercion_if_needed()` which looks up the expected type from the template definition.

4. **Frontend Settings**: Settings are persisted in `localStorage` and sent to the backend during build via the `coercion_settings` key in the POST body. The settings page is accessible at `/settings/type-coercion`.

5. **Visual Cues**: When coercion is enabled, coercible type handles show a unified pink color (via `COERCION_UNIFIED_COLOR_NAME` and `hasCoercibleColor` in `styleUtils.ts`).

6. **Schema Changes**: `InterfaceComponentTypes` gains `APIResponse` and `JSONInput` entries, and the `INPUT_COMPONENTS`/`OUTPUT_COMPONENTS` lists are updated. These changes support the broader API response feature but are included in this diff since they modify `schema.py`.
