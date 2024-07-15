---
title: Helpers
sidebar_position: 4
slug: /components-helpers
---



:::info

This page may contain outdated information. It will be updated as soon as possible.

:::




## Chat memory {#304dc4a3bea74efb9068093ff18a56ad}


This component retrieves stored chat messages based on a specific session ID.


### Parameters {#e0af57d97f844ce99789958161d19767}

- **Sender type:** Choose the sender type from options like "Machine", "User", or "Both".
- **Sender name:** (Optional) The name of the sender.
- **Number of messages:** Number of messages to retrieve.
- **Session ID:** The session ID of the chat history.
- **Order:** Choose the message order, either "Ascending" or "Descending".
- **Data template:** (Optional) Template to convert a record to text. If left empty, the system dynamically sets it to the record's text key.

---


### Combine text {#13443183e6054d0694d65f8df08833d5}


This component concatenates two text sources into a single text chunk using a specified delimiter.


### Parameters {#246676d119604fc5bf1be85fe93044aa}

- **First text:** The first text input to concatenate.
- **Second text:** The second text input to concatenate.
- **Delimiter:** A string used to separate the two text inputs. Defaults to a space.

---


### Create record {#506f43345854473b8199631bf68a3b4a}


This component dynamically creates a record with a specified number of fields.


### Parameters {#08735e90bd10406695771bad8a95976a}

- **Number of fields:** Number of fields to be added to the record.
- **Text key:** Key used as text.

---


### Custom component {#cda421d4bccb4e7db2e48615884ed753}


Use this component as a template to create your custom component.


### Parameters {#04f9eb5e6da4431593a5bee8831f2327}

- **Parameter:** Describe the purpose of this parameter.

INFO


Customize the `build_config` and `build` methods according to your requirements.


Learn more about creating custom components at [Custom Component](http://docs.langflow.org/components/custom).


---


### Documents to Data {#53a6a99a54f0435e9209169cf7730c55}


Convert LangChain documents into Data.


### Parameters {#0eb5fce528774c2db4a3677973e75cf8}

- **Documents:** Documents to be converted into Data.

---


### ID generator {#4a8fbfb95ebe44ee8718725546db5393}


Generates a unique ID.


### Parameters {#4629dd15594c47399c97d9511060e114}

- **Value:** Unique ID generated.

---


### Message history {#6a1a60688641490197c6443df573960e}


Retrieves stored chat messages based on a specific session ID.


### Parameters {#31c7fc2a3e8c4f7c89f923e700f4ea34}

- **Sender type:** Options for the sender type.
- **Sender name:** Sender name.
- **Number of messages:** Number of messages to retrieve.
- **Session ID:** Session ID of the chat history.
- **Order:** Order of the messages.

---


### Data to text {#f60ab5bbc0db4b27b427897eba97fe29}


Convert Data into plain text following a specified template.


### Parameters {#01b91376569149a49cfcfd9321323688}

- **Data:** The Data to convert to text.
- **Template:** The template used for formatting the Data. It can contain keys like `{text}`, `{data}`, or any other key in the record.

---


### Split text {#210be0ae518d411695d6caafdd7700eb}


Split text into chunks of a specified length.


### Parameters {#04197fcd05e64e10b189de1171a32682}

- **Texts:** Texts to split.
- **Separators:** Characters to split on. Defaults to a space.
- **Max chunk size:** The maximum length (in characters) of each chunk.
- **Chunk overlap:** The amount of character overlap between chunks.
- **Recursive:** Whether to split recursively.

---


### Update record {#d3b6116dfd8d4af080ad01bc8fd2b0b3}


Update a record with text-based key/value pairs, similar to updating a Python dictionary.


### Parameters {#c830224edc1d486aaaa5e2889f4f6689}

- **Data:** The record to update.
- **New data:** The new data to update the record with.
