---
title: Langflow objects
slug: /concepts-objects
---

In Langflow, objects are [Pydantic](https://docs.pydantic.dev/latest/api/base_model/) models that serve as structured, functional representations of data.

## Data object

The `Data` object is a [Pydantic](https://docs.pydantic.dev/latest/api/base_model/) model that serves as a container for storing and manipulating data. It carries `data`—a dictionary that can be accessed as attributes—and uses `text_key` to specify which key in the dictionary should be considered the primary text content.

- **Main Attributes:**
  - `text_key`: Specifies the key to retrieve the primary text data.
  - `data`: A dictionary to store additional data.
  - `default_value`: default value when the `text_key` is not present in the `data` dictionary.

### Create a Data Object

Create a `Data` object by directly assigning key-value pairs to it. For example:

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

To receive `Data` objects in a component input, use the `DataInput` input type.

```python
inputs = [
        DataInput(name="data", display_name="Data", info="Helpful info about the incoming data object.", is_list=True),
]
```

## Message object

The `Message` object extends the functionality of `Data` and includes additional attributes and methods for chat interactions.

- **Core message data:**

  - `text`: The main text content of the message
  - `sender`: Identifier for the sender ("User" or "AI")
  - `sender_name`: Name of the sender
  - `session_id`: Identifier for the chat session (`string` or `UUID`)
  - `timestamp`: Timestamp when the message was created (UTC)
  - `flow_id`: Identifier for the flow (`string` or `UUID`)
  - `id`: Unique identifier for the message

- **Content and files:**

  - `files`: List of files or images associated with the message
  - `content_blocks`: List of structured content block objects
  - `properties`: Additional properties including visual styling and source information

- **Message state:**
  - `error`: Boolean indicating if there was an error
  - `edit`: Boolean indicating if the message was edited
  - `category`: Message category ("message", "error", "warning", "info")

The `Message` object can be used to send, store, and manipulate chat messages within Langflow.

### Create a Message object

You can create a `Message` object by directly assigning key-value pairs to it. For example:

```python
from langflow.schema.message import Message

message = Message(text="Hello, AI!", sender="User", sender_name="John Doe")
```

To receive `Message` objects in a component input, you can use the `MessageInput` input type or `MessageTextInput` when the goal is to extract just the `text` field of the `Message` object.

## ContentBlock object

The `ContentBlock` object is a list of multiple `ContentTypes`. It allows you to include multiple types of content within a single `Message`, including images, videos, and text.

Content types are Pydantic base classes constructed from the types in [content_types.py](https://github.com/langflow-ai/langflow/blob/main/src/backend/base/langflow/schema/content_types.py).

Each content type has specific fields related to its data type. For example:

* `TextContent` has a `text` field for storing strings of text
* `MediaContent` has a `urls` field for storing media file URLs
* `CodeContent` has `code` and `language` fields for code snippets
* `JSONContent` has a `data` field for storing arbitrary JSON data
* `ToolContent` has a `tool_input` field for storing input parameters for the tool

### Create a ContentBlock object

Create a `ContentBlock` object with a list of different content types.

```python
content_block = ContentBlock(
    title="Mixed Content Example",
    contents=[
        TextContent(text="This is a text content"),
        MediaContent(urls=["http://example.com/image.jpg"]),
        JSONContent(data={"key": "value"}),
        CodeContent(code="print('Hello')", language="python")
    ],
    media_url=["http://example.com/additional_image.jpg"]
)
```

### Add ContentBlocks objects to a message

In this example, a text and a media `ContentBlock` are added to a message.

```python
from langflow.schema.message import Message
from langflow.schema.content_block import ContentBlock
from langflow.schema.content_types import TextContent, MediaContent

message = Message(
    text="Main message text",
    sender="User",
    sender_name="John Doe",
    content_blocks=[
        ContentBlock(
            title="Text Block",
            contents=[
                TextContent(type="text", text="This is some text content")
            ]
        ),
        ContentBlock(
            title="Media Block",
            contents=[
                MediaContent(type="media", urls=["http://example.com/image.jpg"])
            ]
        )
    ]
)
```

## DataFrame object

The `DataFrame` class is a custom extension of the Pandas [DataFrame](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.html) class, specifically designed to work seamlessly with Langflow's `Data` objects. The class includes methods for converting between `DataFrame` and lists of `Data` objects.

A `DataFrame` object accepts various input formats, including lists of `Data` objects, dictionaries, and existing `DataFrames`.

### Create a DataFrame object

You can create a DataFrame object using different data formats:

```python
from langflow.schema import Data
from langflow.schema.data import DataFrame

# From a list of Data objects
data_list = [Data(data={"name": "John"}), Data(data={"name": "Jane"})]
df = DataFrame(data_list)

# From a list of dictionaries
dict_list = [{"name": "John"}, {"name": "Jane"}]
df = DataFrame(dict_list)

# From a dictionary of lists
data_dict = {"name": ["John", "Jane"], "age": [30, 25]}
df = DataFrame(data_dict)
Key Methods
to_data_list(): Converts the DataFrame back to a list of Data objects.
add_row(data): Adds a single row (either a Data object or a dictionary) to the DataFrame.
add_rows(data): Adds multiple rows (list of Data objects or dictionaries) to the DataFrame.
Usage Example
python
# Create a DataFrame
df = DataFrame([Data(data={"name": "John"}), Data(data={"name": "Jane"})])

# Add a new row
df = df.add_row({"name": "Alice"})

# Convert back to a list of Data objects
data_list = df.to_data_list()

# Use pandas functionality
filtered_df = df[df["name"].str.startswith("J")]
```

To use DataFrame objects in a component input,use the DataFrameInput input type.

```python
DataFrameInput(
    name="dataframe_input", display_name="DataFrame Input", info="Input for DataFrame objects.", tool_mode=True
),
```

## See also

- [Session ID](/session-id)