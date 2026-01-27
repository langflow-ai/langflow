# Plan: Make run_flow Accept DataFrame and Data Types

## Problem Statement
The `run_flow` component only accepts text/message inputs. When connecting DataFrame or Data objects, they get converted to strings via `_normalize_input_value()`, losing type information. This prevents proper data passthrough to subflows that expect non-string inputs.

## Type Information

### Key Types
- **Data** (`lfx.schema.data.Data`): Extends `CrossModuleModel`, contains `data: dict`, `text_key: str`
- **DataFrame** (`lfx.schema.dataframe.DataFrame`): Extends `pandas.DataFrame`, stores tabular data
- **Message** (`lfx.schema.message.Message`): Extends `Data`, has explicit `text: str` field

### CrossModuleModel
The `CrossModuleModel` base class enables `isinstance()` checks across module boundaries via a custom metaclass that checks class name and model fields rather than strict class identity.

---

## Solution Overview

### Phase 1: Smart Value Normalization
**File: `src/lfx/src/lfx/base/tools/run_flow.py`**

1. **Add type imports at the top**
   ```python
   from lfx.schema.data import Data
   from lfx.schema.dataframe import DataFrame
   ```

2. **Modify `_normalize_input_value()` to preserve Data/DataFrame types**

   Current behavior (line 738-770):
   - Extracts `.text` from objects and converts everything to strings
   - Falls back to `str(value)` for unknown types

   New behavior:
   ```python
   def _normalize_input_value(self, value: Any) -> Any:
       """Normalize input value, preserving Data/DataFrame types.

       - Data/DataFrame objects: preserved as-is for subflow passthrough
       - Message objects: extract text for text/chat inputs
       - dict with text keys: extract text value
       - Other objects: convert to string
       """
       if value is None:
           return ""
       if isinstance(value, str):
           return value
       # Preserve lists as-is
       if isinstance(value, list):
           return value
       # Preserve DataFrame objects - pass through intact
       if isinstance(value, DataFrame):
           return value
       # Preserve Data objects (but not Message for text extraction)
       # Check for DataFrame first since Data check may match other things
       if isinstance(value, Data):
           # If this is a plain Data (not Message), preserve it
           # Message has 'sender' field, plain Data does not
           if not hasattr(value, 'sender') or value.__class__.__name__ == 'Data':
               return value
           # For Message, extract text for text/chat inputs
           if hasattr(value, 'text') and value.text is not None:
               return self._normalize_input_value(value.text)
       # Handle dict-like objects
       if isinstance(value, dict):
           for key in ("text", "content", "message", "input_value"):
               if key in value:
                   return self._normalize_input_value(value[key])
           return value
       # Handle objects with text/content attributes
       for attr in ("text", "content", "message"):
           if hasattr(value, attr):
               attr_value = getattr(value, attr)
               if attr_value is not None:
                   return self._normalize_input_value(attr_value)
       return str(value)
   ```

3. **Update `_extract_tweaks_from_keyed_values()` to conditionally normalize**

   Currently normalizes all values. Update to check the target field's expected type:
   ```python
   def _extract_tweaks_from_keyed_values(
       self,
       values: dict[str, Any] | None,
   ) -> dict[str, dict[str, Any]]:
       tweaks: dict[str, dict[str, Any]] = {}
       if not values:
           return tweaks
       for field_name, field_value in values.items():
           if self.IOPUT_SEP not in field_name:
               continue
           node_id, param_name = field_name.split(self.IOPUT_SEP, 1)
           # Normalize input values - now preserves Data/DataFrame types
           normalized_value = self._normalize_input_value(field_value)
           tweaks.setdefault(node_id, {})[param_name] = normalized_value
       return tweaks
   ```
   (No change needed here - the updated `_normalize_input_value()` handles it)

4. **Update `_build_inputs_from_tweaks()` type handling**

   The method builds payload with `input_value`. Ensure it passes through typed data:
   ```python
   # Line 868: Keep normalization but it now preserves types
   normalized_value = self._normalize_input_value(params["input_value"])
   ```

### Phase 2: Extend Schema Types
**File: `src/lfx/src/lfx/schema/schema.py`**

1. **Update `InputValueRequest.input_value` type annotation**
   ```python
   # From:
   input_value: str | None = Field(default=None, ...)
   # To:
   input_value: str | dict | list | Data | None = Field(default=None, ...)
   ```

   Or use `Any` to be fully flexible:
   ```python
   input_value: Any = Field(default=None, ...)
   ```

### Phase 3: Update Graph Execution Types
**File: `src/lfx/src/lfx/graph/graph/base.py`**

1. **Remove string-only type check in `_run()` (lines 764-766)**
   ```python
   # REMOVE these lines:
   if not isinstance(inputs.get(INPUT_FIELD_NAME, ""), str):
       msg = f"Invalid input value: {inputs.get(INPUT_FIELD_NAME)}. Expected string"
       raise TypeError(msg)
   ```

2. **Update `_set_inputs()` type signature (line ~710)**
   ```python
   # From:
   def _set_inputs(self, input_components: list[str], inputs: dict[str, str], ...)
   # To:
   def _set_inputs(self, input_components: list[str], inputs: dict[str, Any], ...)
   ```

3. **Update `_run()` type signature (line ~740)**
   ```python
   # From:
   async def _run(..., inputs: dict[str, str], ...)
   # To:
   async def _run(..., inputs: dict[str, Any], ...)
   ```

### Phase 4: Update Vertex Parameter Types
**File: `src/lfx/src/lfx/graph/vertex/base.py`**

1. **Update `update_raw_params()` type signature (line ~353)**
   ```python
   # From:
   def update_raw_params(self, new_params: Mapping[str, str | list[str]], ...)
   # To:
   def update_raw_params(self, new_params: Mapping[str, Any], ...)
   ```

### Phase 5: Detect Data Entry Points in Subflows (Optional Enhancement)
**File: `src/lfx/src/lfx/base/tools/run_flow.py`**

1. **Add `_get_data_entry_vertices()` method**
   - Scans all vertices in subflow graph
   - Finds inputs with `input_types` containing "DataFrame" or "Data"
   - Filters to only `required=True` inputs
   - Excludes inputs that are already connected
   - Returns list of (vertex, [field_names]) tuples

2. **Modify `get_new_fields_from_graph()`**
   - Get standard input components via `get_flow_inputs()`
   - Also get data entry points via `_get_data_entry_vertices()`
   - Merge both sets of fields

---

## Files Modified

| File | Changes |
|------|---------|
| `src/lfx/src/lfx/base/tools/run_flow.py` | Add imports, modify `_normalize_input_value()` to preserve Data/DataFrame |
| `src/lfx/src/lfx/schema/schema.py` | Extend `InputValueRequest.input_value` type to allow Any |
| `src/lfx/src/lfx/graph/graph/base.py` | Remove string check, update type annotations to `Any` |
| `src/lfx/src/lfx/graph/vertex/base.py` | Update `update_raw_params()` type annotation to `Any` |

---

## How It Works

1. When data flows from parent component to Run Flow:
   - `_normalize_input_value()` is called with the input
   - If input is `DataFrame` or `Data`, it's preserved as-is
   - If input is `Message`, text is extracted (for text/chat inputs)
   - Other types are converted to string

2. When the subflow is executed:
   - Graph's `_run()` no longer validates string-only input
   - `update_raw_params()` accepts `Any` type
   - The typed object reaches the subflow component intact

3. The subflow component receives:
   - `DataFrame` → unchanged `DataFrame` object
   - `Data` → unchanged `Data` object
   - `Message` → extracted text string (for chat/text inputs)

---

## Test Scenario

**Subflow:** DataFrame Operations with `df` input
**Parent Flow:** Mock Data → Run Flow (pointing to subflow)

The Run Flow component should:
1. Accept DataFrame connection from Mock Data
2. Preserve the DataFrame through `_normalize_input_value()`
3. Pass the DataFrame to the subflow without string conversion
4. Subflow receives the actual DataFrame object with all data intact

---

## Type Check Approach

Use `isinstance()` which works across module boundaries due to `CrossModuleModel`:
```python
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame

# These will work correctly even with re-exported classes
if isinstance(value, DataFrame):
    return value  # Preserve DataFrame
if isinstance(value, Data):
    # Check if it's a plain Data vs Message
    if value.__class__.__name__ == 'Data':
        return value  # Preserve plain Data
    # Otherwise it's Message, extract text
```
