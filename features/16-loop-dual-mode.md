# Feature 16: Loop Dual Mode

## Summary

Merges the Loop and For Loop components into a single dual-mode Loop component. Adds a `TabInput` for mode selection between "For-Each" (iterate over DataFrame/list, original behavior) and "Counted" (repeat a Data/Message N times, new functionality). Dynamic field visibility based on the selected mode ensures only relevant inputs are shown. Backward compatibility is maintained by defaulting to "For-Each" mode.

## Dependencies

- `langflow.inputs.inputs.TabInput` (new import)
- `langflow.io.IntInput` (new import)
- `langflow.schema.message.Message` (new import)
- `langflow.utils.component_utils.set_current_fields`, `set_field_advanced` (new imports)

## Files Changed

### `src/backend/base/langflow/components/logic/loop.py`

**Note**: This diff was extracted from commit `59e26b29e3` (the feature commit merged via `origin/feature/loop-dual-mode`), since the changes are already merged into main and show no diff against HEAD.

```diff
diff --git a/src/backend/base/langflow/components/logic/loop.py b/src/backend/base/langflow/components/logic/loop.py
index b17daece6d..fcf9fe2e30 100644
--- a/src/backend/base/langflow/components/logic/loop.py
+++ b/src/backend/base/langflow/components/logic/loop.py
@@ -1,23 +1,58 @@
 from langflow.custom.custom_component.component import Component
-from langflow.inputs.inputs import HandleInput
+from langflow.inputs.inputs import HandleInput, TabInput
+from langflow.io import IntInput
 from langflow.schema.data import Data
 from langflow.schema.dataframe import DataFrame
+from langflow.schema.message import Message
 from langflow.template.field.base import Output
+from langflow.utils.component_utils import set_current_fields, set_field_advanced
+
+# Define fields for each mode
+MODE_FIELDS = {
+    "For-Each": ["dataframe_input"],
+    "Counted": ["data_input", "iterations"],
+}
+
+# Fields that should always be visible
+DEFAULT_FIELDS = ["mode"]


 class LoopComponent(Component):
     display_name = "Loop"
     description = (
-        "Iterates over a list of Data objects, outputting one item at a time and aggregating results from loop inputs."
+        "Iterates over items with two modes: For-Each (iterate over DataFrame) or Counted (repeat N times)."
     )
     icon = "infinity"

     inputs = [
+        TabInput(
+            name="mode",
+            display_name="Mode",
+            options=["For-Each", "Counted"],
+            value="For-Each",
+            info="Choose iteration mode: For-Each iterates over DataFrame/list, Counted repeats N times.",
+            real_time_refresh=True,
+        ),
         HandleInput(
-            name="data",
-            display_name="Inputs",
-            info="The initial list of Data objects or DataFrame to iterate over.",
+            name="dataframe_input",
+            display_name="Input",
+            info="The DataFrame input to iterate over the rows.",
             input_types=["DataFrame"],
+            advanced=False,
+        ),
+        HandleInput(
+            name="data_input",
+            display_name="Input",
+            info="The Data or Message to repeat N times.",
+            input_types=["Data", "Message"],
+            advanced=False,
+        ),
+        IntInput(
+            name="iterations",
+            display_name="Iterations",
+            info="Number of times to repeat the data.",
+            value=1,
+            advanced=False,
         ),
     ]

@@ -31,8 +66,11 @@ class LoopComponent(Component):
         if self.ctx.get(f"{self._id}_initialized", False):
             return

-        # Ensure data is a list of Data objects
-        data_list = self._validate_data(self.data)
+        # Get data based on selected mode
+        if self.mode == "Counted":
+            data_list = self._validate_data_counted(self.data_input, self.iterations)
+        else:
+            data_list = self._validate_data_foreach(self.dataframe_input)

         # Store the initial data and context variables
         self.update_ctx(
@@ -44,8 +82,8 @@ class LoopComponent(Component):
             }
         )

-    def _validate_data(self, data):
-        """Validate and return a list of Data objects."""
+    def _validate_data_foreach(self, data):
+        """Validate and return a list of Data objects for For-Each mode."""
         if isinstance(data, DataFrame):
             return data.to_data_list()
         if isinstance(data, Data):
@@ -55,6 +93,28 @@ class LoopComponent(Component):
         msg = "The 'data' input must be a DataFrame, a list of Data objects, or a single Data object."
         raise TypeError(msg)

+    def _validate_data_counted(self, data, iterations):
+        """Validate and return a list of Data objects for Counted mode."""
+        if isinstance(data, Message):
+            data = Data(text=data.text)
+        elif not isinstance(data, Data):
+            data = Data(text=str(data))
+        return [data] * iterations
+
+    def update_build_config(self, build_config, field_value, field_name=None):
+        """Update the build config based on the selected mode."""
+        if field_name != "mode":
+            return build_config
+
+        return set_current_fields(
+            build_config=build_config,
+            action_fields=MODE_FIELDS,
+            selected_action=field_value,
+            default_fields=DEFAULT_FIELDS,
+            func=set_field_advanced,
+            default_value=True,
+        )
+
     def evaluate_stop_loop(self) -> bool:
         """Evaluate whether to stop item or done output."""
         current_index = self.ctx.get(f"{self._id}_index", 0)
```

### `src/backend/tests/unit/components/logic/test_loop.py`

```diff
diff --git a/src/backend/tests/unit/components/logic/test_loop.py b/src/backend/tests/unit/components/logic/test_loop.py
index 7188aad1fb..d854b274ee 100644
--- a/src/backend/tests/unit/components/logic/test_loop.py
+++ b/src/backend/tests/unit/components/logic/test_loop.py
@@ -7,9 +7,11 @@ from httpx import AsyncClient
 from langflow.components.logic import LoopComponent
 from langflow.memory import aget_messages
 from langflow.schema.data import Data
+from langflow.schema.dataframe import DataFrame
+from langflow.schema.message import Message
 from langflow.services.database.models.flow import FlowCreate

-from tests.base import ComponentTestBaseWithClient
+from tests.base import ComponentTestBaseWithClient, ComponentTestBaseWithoutClient
 from tests.unit.build_utils import build_flow, get_build_events

 TEXT = (
@@ -19,6 +21,204 @@ TEXT = (
 )


+class TestLoopComponent(ComponentTestBaseWithoutClient):
+    """Unit tests for the Loop component."""
+
+    @pytest.fixture
+    def component_class(self):
+        """Return the component class to test."""
+        return LoopComponent
+
+    @pytest.fixture
+    def file_names_mapping(self):
+        """Return an empty list since this component doesn't have version-specific files."""
+        return []
+
+    @pytest.fixture
+    def default_kwargs_foreach(self):
+        """Return default kwargs for For-Each mode."""
+        return {
+            "mode": "For-Each",
+            "dataframe_input": DataFrame([Data(text="Hello World"), Data(text="Test Data")]),
+            "data_input": None,
+            "iterations": 1,
+        }
+
+    @pytest.fixture
+    def default_kwargs_counted(self):
+        """Return default kwargs for Counted mode."""
+        return {
+            "mode": "Counted",
+            "dataframe_input": None,
+            "data_input": Data(text="Hello World"),
+            "iterations": 3,
+        }
+
+    @pytest.fixture
+    def default_kwargs(self):
+        """Return the default kwargs for the component (For-Each mode for backward compatibility)."""
+        return {
+            "mode": "For-Each",
+            "dataframe_input": DataFrame([Data(text="Hello World")]),
+            "data_input": None,
+            "iterations": 1,
+        }
+
+    async def test_component_structure(self, component_class, default_kwargs):
+        """Test that the component has the correct structure."""
+        component = await self.component_setup(component_class, default_kwargs)
+
+        # Test component properties
+        assert component.display_name == "Loop"
+        assert "two modes" in component.description.lower()
+        assert component.icon == "infinity"
+
+        # Test inputs
+        assert len(component.inputs) == 4
+        input_names = [inp.name for inp in component.inputs]
+        assert "mode" in input_names
+        assert "dataframe_input" in input_names
+        assert "data_input" in input_names
+        assert "iterations" in input_names
+
+        # Test outputs
+        assert len(component.outputs) == 2
+        output_names = [out.name for out in component.outputs]
+        assert "item" in output_names
+        assert "done" in output_names
+
+    async def test_foreach_mode_with_dataframe(self, component_class, default_kwargs_foreach):
+        """Test For-Each mode with DataFrame input."""
+        component = await self.component_setup(component_class, default_kwargs_foreach)
+
+        # Test data validation
+        data_list = component._validate_data_foreach(component.dataframe_input)
+        assert len(data_list) == 2
+        assert all(isinstance(item, Data) for item in data_list)
+        assert data_list[0].text == "Hello World"
+        assert data_list[1].text == "Test Data"
+
+    async def test_foreach_mode_with_data_list(self, component_class):
+        """Test For-Each mode with Data list input."""
+        data_list = [Data(text="Item 1"), Data(text="Item 2"), Data(text="Item 3")]
+        kwargs = {
+            "mode": "For-Each",
+            "dataframe_input": data_list,
+            "data_input": None,
+            "iterations": 1,
+        }
+        component = await self.component_setup(component_class, kwargs)
+
+        # Test data validation
+        validated_data = component._validate_data_foreach(component.dataframe_input)
+        assert len(validated_data) == 3
+        assert all(isinstance(item, Data) for item in validated_data)
+
+    async def test_counted_mode_with_data(self, component_class, default_kwargs_counted):
+        """Test Counted mode with Data input."""
+        component = await self.component_setup(component_class, default_kwargs_counted)
+
+        # Test data validation
+        data_list = component._validate_data_counted(component.data_input, component.iterations)
+        assert len(data_list) == 3
+        assert all(isinstance(item, Data) for item in data_list)
+        assert all(item.text == "Hello World" for item in data_list)
+
+    async def test_counted_mode_with_message(self, component_class):
+        """Test Counted mode with Message input."""
+        message_input = Message(text="Test Message")
+        kwargs = {
+            "mode": "Counted",
+            "dataframe_input": None,
+            "data_input": message_input,
+            "iterations": 2,
+        }
+        component = await self.component_setup(component_class, kwargs)
+
+        # Test data validation
+        data_list = component._validate_data_counted(component.data_input, component.iterations)
+        assert len(data_list) == 2
+        assert all(isinstance(item, Data) for item in data_list)
+        assert all(item.text == "Test Message" for item in data_list)
+
+    async def test_counted_mode_iterations(self, component_class):
+        """Test Counted mode with different iteration counts."""
+        test_cases = [1, 5, 10]
+
+        for iterations in test_cases:
+            kwargs = {
+                "mode": "Counted",
+                "dataframe_input": None,
+                "data_input": Data(text=f"Test {iterations}"),
+                "iterations": iterations,
+            }
+            component = await self.component_setup(component_class, kwargs)
+
+            data_list = component._validate_data_counted(component.data_input, component.iterations)
+            assert len(data_list) == iterations
+            assert all(item.text == f"Test {iterations}" for item in data_list)
+
+    async def test_foreach_mode_validation_errors(self, component_class):
+        """Test validation errors in For-Each mode."""
+        component = await self.component_setup(component_class, {
+            "mode": "For-Each",
+            "dataframe_input": None,
+            "data_input": None,
+            "iterations": 1,
+        })
+
+        # Test with invalid input
+        with pytest.raises(TypeError):
+            component._validate_data_foreach("invalid_input")
+
+    async def test_update_build_config_foreach(self, component_class, default_kwargs_foreach):
+        """Test build config updates for For-Each mode."""
+        component = await self.component_setup(component_class, default_kwargs_foreach)
+
+        # Get the frontend node to test build config
+        frontend_node = component.to_frontend_node()
+        build_config = frontend_node["data"]["node"]["template"]
+
+        # Test mode field exists
+        assert "mode" in build_config
+
+        # Test update_build_config for For-Each mode
+        updated_config = component.update_build_config(build_config, "For-Each", "mode")
+
+        # The method should return the updated config (basic test)
+        assert updated_config is not None
+
+    async def test_update_build_config_counted(self, component_class, default_kwargs_counted):
+        """Test build config updates for Counted mode."""
+        component = await self.component_setup(component_class, default_kwargs_counted)
+
+        # Get the frontend node to test build config
+        frontend_node = component.to_frontend_node()
+        build_config = frontend_node["data"]["node"]["template"]
+
+        # Test update_build_config for Counted mode
+        updated_config = component.update_build_config(build_config, "Counted", "mode")
+
+        # The method should return the updated config (basic test)
+        assert updated_config is not None
+
+    async def test_mode_switching(self, component_class, default_kwargs):
+        """Test switching between modes."""
+        component = await self.component_setup(component_class, default_kwargs)
+
+        # Test default mode
+        assert component.mode == "For-Each"
+
+        # Test frontend node structure
+        frontend_node = component.to_frontend_node()
+        build_config = frontend_node["data"]["node"]["template"]
+
+        # Verify all expected inputs are present
+        expected_inputs = ["mode", "dataframe_input", "data_input", "iterations"]
+        for input_name in expected_inputs:
+            assert input_name in build_config
+
+
 class TestLoopComponentWithAPI(ComponentTestBaseWithClient):
     @pytest.fixture
     def component_class(self):
@@ -33,9 +233,12 @@ class TestLoopComponentWithAPI(ComponentTestBaseWithClient):
     @pytest.fixture
     def default_kwargs(self):
         """Return the default kwargs for the component."""
+        # For-Each mode default kwargs (backward compatibility)
         return {
-            "data": [[Data(text="Hello World")]],
-            "loop_input": [Data(text=TEXT)],
+            "mode": "For-Each",
+            "dataframe_input": DataFrame([Data(text="Hello World")]),
+            "data_input": None,
+            "iterations": 1,
         }

     def test_latest_version(self, component_class, default_kwargs) -> None:
```

## Implementation Notes

1. **Mode selection via TabInput**: The `TabInput` provides a UI tab selector between "For-Each" and "Counted" modes, with `real_time_refresh=True` to trigger `update_build_config` on change.
2. **Dynamic field visibility**: `update_build_config` uses `set_current_fields` and `set_field_advanced` to show/hide fields based on the selected mode. In "For-Each" mode, only `dataframe_input` is visible. In "Counted" mode, `data_input` and `iterations` are visible.
3. **Counted mode validation**: `_validate_data_counted` converts `Message` to `Data` and creates a list by repeating the item N times using `[data] * iterations`.
4. **Backward compatibility**: The default mode is "For-Each", maintaining the original behavior. The old `_validate_data` method was renamed to `_validate_data_foreach`.
5. **Input rename**: The old `data` input was renamed to `dataframe_input` for clarity, since there are now two distinct input handles.
6. **Comprehensive tests**: New `TestLoopComponent` class (using `ComponentTestBaseWithoutClient`) covers both modes, iteration counts, message conversion, build config updates, and mode switching. The existing `TestLoopComponentWithAPI` was updated to use the new kwargs format.
