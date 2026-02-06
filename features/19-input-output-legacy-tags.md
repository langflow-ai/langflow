# Feature 19: Input/Output Legacy Tags

## Summary

Marks the `TextInput`, `TextOutput`, and `MCPToolsComponent` components as legacy. `TextInput` is replaced by `input_output.JSONInput`, and `TextOutput` is replaced by `input_output.APIResponse`. `MCPToolsComponent` is simply marked as legacy with no specific replacement listed.

The `legacy = True` flag causes the component to be hidden from the sidebar by default and shown with a deprecation indicator. The `replacement` list tells the UI which component(s) to suggest as alternatives.

## Dependencies

None (uses existing `legacy` and `replacement` class attributes from the component base class).

## Files Changed

### `src/lfx/src/lfx/components/input_output/text.py`

```diff
diff --git a/src/lfx/src/lfx/components/input_output/text.py b/src/lfx/src/lfx/components/input_output/text.py
index 9b17dc066a..279598a46b 100644
--- a/src/lfx/src/lfx/components/input_output/text.py
+++ b/src/lfx/src/lfx/components/input_output/text.py
@@ -11,6 +11,8 @@ class TextInputComponent(TextComponent):
     documentation: str = "https://docs.langflow.org/text-input-and-output"
     icon = "type"
     name = "TextInput"
+    legacy = True
+    replacement = ["input_output.JSONInput"]

     inputs = [
         MultilineInput(
```

### `src/lfx/src/lfx/components/input_output/text_output.py`

```diff
diff --git a/src/lfx/src/lfx/components/input_output/text_output.py b/src/lfx/src/lfx/components/input_output/text_output.py
index 2c044ac6f2..f07075735c 100644
--- a/src/lfx/src/lfx/components/input_output/text_output.py
+++ b/src/lfx/src/lfx/components/input_output/text_output.py
@@ -9,6 +9,8 @@ class TextOutputComponent(TextComponent):
     documentation: str = "https://docs.langflow.org/text-input-and-output"
     icon = "type"
     name = "TextOutput"
+    legacy = True
+    replacement = ["input_output.APIResponse"]

     inputs = [
         MultilineInput(
```

### `src/lfx/src/lfx/components/models_and_agents/mcp_component.py`

```diff
diff --git a/src/lfx/src/lfx/components/models_and_agents/mcp_component.py b/src/lfx/src/lfx/components/models_and_agents/mcp_component.py
index 0a2865c77c..196ba77f86 100644
--- a/src/lfx/src/lfx/components/models_and_agents/mcp_component.py
+++ b/src/lfx/src/lfx/components/models_and_agents/mcp_component.py
@@ -49,6 +49,7 @@ def resolve_mcp_config(


 class MCPToolsComponent(ComponentWithCache):
+    legacy = True
     schema_inputs: list = []
     tools: list[StructuredTool] = []
     _not_load_actions: bool = False
```

## Implementation Notes

1. **`legacy = True`**: This is a class-level attribute recognized by the Langflow component system. Legacy components are hidden from the sidebar by default but still function in existing flows.
2. **`replacement` list**: Contains dot-separated component identifiers in the format `category.ComponentName`. The frontend uses this to suggest alternatives when a user encounters a legacy component.
3. **MCPToolsComponent**: Marked as legacy without a `replacement` attribute, meaning the UI will show it as deprecated but without a specific migration path.
4. **No functional changes**: These changes only affect component metadata/visibility. The actual component logic remains unchanged.
