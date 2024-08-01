---
title: Data & Message
sidebar_position: 2
slug: /guides-data-message
---



In Langflow, the `Data` and `Message` objects serve as structured, functional representations of data that enhance the capabilities and reliability of the platform.


## The Data Object {#e0d56e463d2f483bb1b5df09d88bf309}


---


The `Data` object is a Pydantic model that serves as a container for storing and manipulating data. It carries `data`—a dictionary that can be accessed as attributes—and uses `text_key` to specify which key in the dictionary should be considered the primary text content.


- **Main Attributes:**
	- `text_key`: Specifies the key to retrieve the primary text data.
	- `data`: A dictionary to store additional data.
	- `default_value`:  default value when the `text_key` is not present in the `data` dictionary.

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


## The Message Object {#f4f17cad02a545068f407d515cbc2902}


---


The `Message` object extends the functionality of `Data` and includes additional attributes and methods for chat interactions.

- **Main Attributes:**
	- `text_key`: Key to retrieve the primary text data.
	- `text`: The main text content of the message.
	- `sender`: Identifier for the sender (e.g., "User" or "AI").
	- `sender_name`: Name of the sender.
	- `files`: List of files associated with the message.
	- `session_id`: Identifier for the chat session.
	- `timestamp`: Timestamp when the message was created.
	- `flow_id`: Identifier for the flow.

The `Message` object can be used to send, store and manipulate chat messages within Langflow. You can create a `Message` object by directly assigning key-value pairs to it. For example:


```python
from langflow.schema.message import Message

message = Message(text="Hello, AI!", sender="User", sender_name="John Doe")
```


To receive `Message` objects in a component input, you can use the `MessageInput` input type or `MessageTextInput` when the goal is to extract just the `text` field of the `Message` object.

