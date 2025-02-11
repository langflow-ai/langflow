# Guide to Writing Component Tests

This guide outlines how to structure and implement tests for application components. Follow these guidelines to ensure consistency and adequate coverage when creating tests for components in Langflow.

## General Structure (Boilerplate)

### 1. File Naming:

- The test file should follow the same directory structure as the component being tested but should be placed in the corresponding unit tests folder.
- For example, if the file path for the component is:

  ```
  src/backend/base/langflow/components/prompts/
  ```

  then the test file should be located in:

  ```
  src/backend/tests/unit/components/prompts/
  ```

- The test file name should follow the pattern `test_<file_name>.py` changing the name of the file to snake case if it isn't already.
- Example: If the file to be tested is `PromptComponent.py`, the test file should be named `test_prompt_component.py`.

### 2. File Structure:

- Each test file should group tests into classes by component. There should be no standalone test functions in the file—only test methods within classes.
- Class names should follow the pattern `Test<ClassName>`.
- Example: If the component being tested is `PromptComponent`, the test class should be named `TestPromptComponent`.

### 3. Imports, Inheritance, and Mandatory Methods:

To standardize the tests, base test classes have been created and should be imported and inherited by all component test classes. These base classes are located in the file:

```
src/backend/tests/unit/base.py
```

```python
from tests.base import ComponentTestBaseWithClient
from tests.base import ComponentTestBaseWithoutClient
```

These base classes enforce mandatory methods that the component test classes must implement and ensure the Component built in previous versions continues to work in the current version. By inheriting from one of these base classes, the developer must define the following methods decorated with `@pytest.fixture`:

#### `component_class:` Returns the class of the component to be tested.

Example:

```python
@pytest.fixture
def component_class(self):
    return PromptComponent
```

#### `default_kwargs:` Returns a dictionary with the default arguments required to instantiate the component.

Example:

```python
@pytest.fixture
def default_kwargs(self):
    return {"template": "Hello {name}!", "name": "John", "_session_id": "123"}
```

#### `file_names_mapping:` Returns a list of dictionaries representing the relationship between version, module, and file_name that the tested component has had over time. This can be left empty in case it is an unreleased component.

Example:

```python
@pytest.fixture
def file_names_mapping(self):
    return [
        {"version": "1.0.15", "module": "prompts", "file_name": "Prompt"},
        {"version": "1.0.16", "module": "prompts", "file_name": "Prompt"},
        {"version": "1.0.17", "module": "prompts", "file_name": "Prompt"},
        {"version": "1.0.18", "module": "prompts", "file_name": "Prompt"},
        {"version": "1.0.19", "module": "prompts", "file_name": "Prompt"},
    ]
```

---

## Testing Component Functionalities

Once the basic structure of the test file is defined, the developer should implement test methods for the component's functionalities. The following guidelines must be followed:

1. Test method names should be descriptive and follow the pattern `test_<case_name>`.
2. Each test should follow the AAA pattern (**Arrange, Act, Assert**):
   - **Arrange**: Prepare the data.
   - **Act**: Execute the component.
   - **Assert**: Verify the result.

### Example:

#### **Arrange:**
Whenever possible, it is recommended to use the fixtures defined in the basic structure, but this is not mandatory.

```python
def test_post_code_processing(self, component_class, default_kwargs):
    component = component_class(**default_kwargs)
```

#### **Act:**
Once everything is set up, call the `.to_frontend_node()` method of the component prepared during the Arrange step.

```python
def test_post_code_processing(self, component_class, default_kwargs):
    component = component_class(**default_kwargs)

    frontend_node = component.to_frontend_node()
```

#### **Assert:**
After executing the `.to_frontend_node()` method, the resulting data will be available for verification in the dictionary `frontend_node["data"]["node"]`. Assertions should be clear and cover the expected outcomes.

```python
def test_post_code_processing(self, component_class, default_kwargs):
    component = component_class(**default_kwargs)

    frontend_node = component.to_frontend_node()

    node_data = frontend_node["data"]["node"]
    assert node_data["template"]["template"]["value"] == "Hello {name}!"
    assert "name" in node_data["custom_fields"]["template"]
    assert "name" in node_data["template"]
    assert node_data["template"]["name"]["value"] == "John"
```
