---
title: Contribute components
slug: /contributing-components
---


New components are added as objects of the [CustomComponent](https://github.com/langflow-ai/langflow/blob/dev/src/backend/base/langflow/custom/custom_component/custom_component.py) class.

Dependencies are added to the [pyproject.toml](https://github.com/langflow-ai/langflow/blob/main/pyproject.toml#L148) file.

## Contribute an example component to Langflow

Anyone can contribute an example component. For example, if you created a new data processor called **DataFrameProcessor**, follow these steps to contribute it to Langflow.

1. Write your processor as an object of the [CustomComponent](https://github.com/langflow-ai/langflow/blob/dev/src/backend/base/langflow/custom/custom_component/custom_component.py) class. You'll create a new class, `DataFrameProcessor`, that will inherit from `CustomComponent` and override the base class's methods.

2. Define attributes to provide information about your custom component:
   * `display_name`: A user-friendly name shown in the UI
   * `description`: A brief description of what your component does
   * `documentation`: Link to detailed documentation
   * `icon`: An emoji or icon identifier for visual representation
   * `priority`: Optional integer to control display order (lower numbers appear first)
   * `name`: Optional internal identifier (defaults to class name)

    For more information, see [Create custom Python components](/components-custom-components).

3. Implement the `build_config` method to define the configuration options for your custom component. This method should return a dictionary of field configurations.

4. Implement the `build` method to define the logic for taking input parameters specified in the `build_config` method and returning the desired output. This method can be synchronous or asynchronous.
   ```python
   def build(self, *args, **kwargs) -> Any:
       # Synchronous implementation
       return result

   async def build(self, *args, **kwargs) -> Any:
       # Asynchronous implementation
       return await result
   ```

5. Add the code to the [/components/data](https://github.com/langflow-ai/langflow/tree/dev/src/backend/base/langflow/components/data) folder.

6. Add the dependency to [/data/__init__.py](https://github.com/langflow-ai/langflow/blob/dev/src/backend/base/langflow/components/data/__init__.py) as `from .DataFrameProcessor import DataFrameProcessor`.

7. Add any new dependencies to the [pyproject.toml](https://github.com/langflow-ai/langflow/blob/main/pyproject.toml#L148) file.

8. Submit documentation for your component. For this example, you'd submit documentation to the [data components page](https://github.com/langflow-ai/langflow/blob/main/docs/docs/Components/components-data.md).

9. Submit your changes as a pull request. The Langflow team will have a look, suggest changes, and add your component to Langflow.

## Best practices for modifying components

When creating or updating components, follow these best practices to maintain backward compatibility and ensure a smooth experience for users.

### Don't rename the class or `name` attribute

Changing the class name or the `name` attribute breaks the component for all existing users. This happens because the frontend tests the `type` attribute, which is set to the class' name or the `name` attribute. If these names change, the component effectively becomes a new component, and the old component disappears.

Instead, do the following:
* Change only the display name if the old name is unclear.
* Change only the display name if functionality changes but remains related
* If a new internal name is necessary, mark the old component as `legacy=true` and create a new component.

For example:
```python
class MyCustomComponent(BaseComponent):
    name = "my_custom_component_internal"
    legacy = True
```

### Don't remove fields and outputs

Removing fields or outputs can cause edges to disconnect and change the behavior of components.

Instead, mark fields as `deprecated` and keep them in the same location. If removal is absolutely necessary, you must define and document a migration plan. Always clearly communicate any changes in the field's information to users.

### Maintain outdated components as legacy

When updating components, create them as completely separate entities while maintaining the old component as a legacy version. Always ensure backward compatibility and never remove methods and attributes from base classes (such as `LCModelComponent`).

### Favor asynchronous methods

Always favor asynchronous methods and functions in your components. When interacting with files, use `aiofile` and `anyio.Path` for better performance and compatibility.

### Include tests with your component

Include tests for your changes using `ComponentTestBase` classes. For more information, see [Contribute component tests](/contributing-component-tests).

### Documentation

When documenting changes in pull requests, clearly explain what changed, such as display name updates or new fields, why it changed (for example, clarity improvements or bug fixes), and the impact on existing users (whether no action is needed or if migration steps are required).

For example:
```markdown
## Pull request with changes to Notify component

### What changed
- Added new `timeout` field to control how long the component waits for a response
- Renamed `message` field to `notification_text` for clarity
- Added support for async operations
- Deprecated the `retry_count` field in favor of `max_retries`

### Why it changed
- `timeout` field addresses user requests for better control over wait times
- `message` to `notification_text` change makes the field's purpose clearer
- Async support improves performance in complex flows
- `retry_count` to `max_retries` aligns with common retry pattern terminology

### Impact on users
- New `timeout` field is optional (defaults to 30 seconds)
- Users will see a deprecation warning for `retry_count`
  - Migration: Replace `retry_count` with `max_retries` in existing flows
  - Both fields will work until version 2.0
- No action needed for async support - it's backward compatible
```

## Example pull request flow

1. Create or update a component.
Maintain the class name and `name` attribute if the purpose remains the same.
Otherwise, create a new component and move the old component to `legacy`.
2. Add tests.
Create tests using one of the `ComponentTestBase` classes.
For more information, see [Contribute component tests](/contributing-component-tests).
3. Mark deprecated elements.
Flag outdated fields and outputs as deprecated.
4. Document your changes.
Include migration instructions if breaking changes occur.