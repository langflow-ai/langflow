---
title: Data Object
sidebar_position: 1
slug: /types-data
---

The `Data` object is a Pydantic model that serves as a container for storing and manipulating data. It carries `data`—a dictionary that can be accessed as attributes—and uses `text_key` to specify which key in the dictionary should be considered the primary text content.

- **Main Attributes:**
  - `text_key`: Specifies the key to retrieve the primary text data.
  - `data`: A dictionary to store additional data.
  - `default_value`: default value when the `text_key` is not present in the `data` dictionary.

### Creating a Data Object {#3540b7e651f74b558febebbe43380660}

You can create a `Data` object by directly assigning key-value pairs to it. For example:

```python
from langflow.schema import Data

# Creating a Data object with specified key-value pairs
data = Data(text="my_string", bar=3, foo="another_string")

# Outputs:
print(data.text)  # Outputs: "my_string"
print(data.bar)   # Outputs: 3
print(data.foo)   # Outputs: "another_string"
```

The `text_key` specifies which key in the `data` dictionary should be considered the primary text content. The `default_value` provides a fallback if the `text_key` is not present.

```python
# Creating a Data object with a specific text_key and default_value
data = Data(data={"title": "Hello, World!"}, text_key="content", default_value="No content available")

# Accessing the primary text using text_key and default_value
print(data.get_text())  # Outputs: "No content available" because "content" key is not in the data dictionary

# Accessing data keys by calling the attribute directly
print(data.title)  # Outputs: "Hello, World!" because "title" key is in the data dictionary
```

The `Data` object is also convenient for visualization of outputs, since the output preview has visual elements to inspect data as a table and its cells as pop ups for basic types. The idea is to create a unified way to work and visualize complex information in Langflow.

To receive `Data` objects in a component input, you can use the `DataInput` input type.
