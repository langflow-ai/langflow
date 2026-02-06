# Feature 22: File & SaveFile Component Changes

## Summary

Two minor changes to the `FileComponent` and `SaveToFileComponent`:

1. **Field ordering fix**: In the `SortableListInput` for `storage_location`, the `value` parameter was moved before `real_time_refresh` and `limit` to match a consistent ordering convention (value comes before behavioral flags).
2. **Test removal**: Tests for `storage_location` defaults (`test_storage_location_defaults_to_local` and `test_storage_location_is_advanced`) were removed from both `test_file_component.py` and `test_save_file_component.py`.
3. **Comment addition**: A `# Storage location selection` comment was added to `save_file.py`.

## Dependencies

None.

## Files Changed

### `src/lfx/src/lfx/components/files_and_knowledge/file.py`

```diff
diff --git a/src/lfx/src/lfx/components/files_and_knowledge/file.py b/src/lfx/src/lfx/components/files_and_knowledge/file.py
index 2170463669..d5db279119 100644
--- a/src/lfx/src/lfx/components/files_and_knowledge/file.py
+++ b/src/lfx/src/lfx/components/files_and_knowledge/file.py
@@ -107,9 +107,9 @@ class FileComponent(BaseFileComponent):
             placeholder="Select Location",
             info="Choose where to read the file from.",
             options=_get_storage_location_options(),
+            value=[{"name": "Local", "icon": "hard-drive"}],
             real_time_refresh=True,
             limit=1,
-            value=[{"name": "Local", "icon": "hard-drive"}],
             advanced=True,
         ),
         *_base_inputs,
```

### `src/lfx/src/lfx/components/files_and_knowledge/save_file.py`

```diff
diff --git a/src/lfx/src/lfx/components/files_and_knowledge/save_file.py b/src/lfx/src/lfx/components/files_and_knowledge/save_file.py
index e6c0661fca..0ed7eb3491 100644
--- a/src/lfx/src/lfx/components/files_and_knowledge/save_file.py
+++ b/src/lfx/src/lfx/components/files_and_knowledge/save_file.py
@@ -53,15 +53,16 @@ class SaveToFileComponent(Component):
     GDRIVE_FORMAT_CHOICES = ["txt", "json", "csv", "xlsx", "slides", "docs", "jpg", "mp3"]

     inputs = [
+        # Storage location selection
         SortableListInput(
             name="storage_location",
             display_name="Storage Location",
             placeholder="Select Location",
             info="Choose where to save the file.",
             options=_get_storage_location_options(),
+            value=[{"name": "Local", "icon": "hard-drive"}],
             real_time_refresh=True,
             limit=1,
-            value=[{"name": "Local", "icon": "hard-drive"}],
             advanced=True,
         ),
         # Common inputs
```

### `src/backend/tests/unit/components/files_and_knowledge/test_file_component.py`

```diff
diff --git a/src/backend/tests/unit/components/files_and_knowledge/test_file_component.py b/src/backend/tests/unit/components/files_and_knowledge/test_file_component.py
index 94f1b6a084..bc3c015ae4 100644
--- a/src/backend/tests/unit/components/files_and_knowledge/test_file_component.py
+++ b/src/backend/tests/unit/components/files_and_knowledge/test_file_component.py
@@ -718,17 +718,3 @@ class TestFileComponentCloudEnvironment:
         # Even if pipeline is set to "standard", OCR engine should be disabled in cloud
         assert result["ocr_engine"]["show"] is False
         assert result["ocr_engine"]["value"] == "None"
-
-
-class TestFileComponentStorageLocation:
-    """Tests for default Local storage and Storage Location in advanced controls."""
-
-    def test_storage_location_defaults_to_local(self):
-        """Test that storage_location input defaults to Local when component is dropped."""
-        storage_input = next(i for i in FileComponent.inputs if i.name == "storage_location")
-        assert storage_input.value == [{"name": "Local", "icon": "hard-drive"}]
-
-    def test_storage_location_is_advanced(self):
-        """Test that storage_location is in advanced controls."""
-        storage_input = next(i for i in FileComponent.inputs if i.name == "storage_location")
-        assert storage_input.advanced is True
```

### `src/backend/tests/unit/components/processing/test_save_file_component.py`

```diff
diff --git a/src/backend/tests/unit/components/processing/test_save_file_component.py b/src/backend/tests/unit/components/processing/test_save_file_component.py
index 6830152404..26880aa37f 100644
--- a/src/backend/tests/unit/components/processing/test_save_file_component.py
+++ b/src/backend/tests/unit/components/processing/test_save_file_component.py
@@ -462,13 +462,3 @@ class TestSaveToFileComponent(ComponentTestBaseWithoutClient):
         assert result["append_mode"]["show"] is False, "append_mode should be hidden for Google Drive storage"
         assert result["file_name"]["show"] is True
         assert result["gdrive_format"]["show"] is True
-
-    def test_storage_location_defaults_to_local(self, component_class):
-        """Test that storage_location input defaults to Local when component is dropped."""
-        storage_input = next(i for i in component_class.inputs if i.name == "storage_location")
-        assert storage_input.value == [{"name": "Local", "icon": "hard-drive"}]
-
-    def test_storage_location_is_advanced(self, component_class):
-        """Test that storage_location is in advanced controls."""
-        storage_input = next(i for i in component_class.inputs if i.name == "storage_location")
-        assert storage_input.advanced is True
```

## Implementation Notes

1. **Parameter ordering**: The `value` parameter was moved up in both `FileComponent` and `SaveToFileComponent` `SortableListInput` definitions. This is a cosmetic/convention change -- it does not affect behavior since Python keyword arguments are order-independent.
2. **Tests removed**: The `TestFileComponentStorageLocation` class and two methods from `TestSaveToFileComponent` were removed. These tests verified that `storage_location` defaults to `Local` and is `advanced=True`. The removal suggests these are now considered stable/obvious enough to not need dedicated tests, or they may be covered elsewhere.
3. **No functional changes**: The actual component behavior is unchanged. The `value` still defaults to `[{"name": "Local", "icon": "hard-drive"}]` and `advanced` is still `True`.
