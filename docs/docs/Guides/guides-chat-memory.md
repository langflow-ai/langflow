---
title: Chat Memory
sidebar_position: 1
slug: /guides-chat-memory
---



Langflow allows every chat message to be stored, and a single flow can have multiple memory sessions. This enables you to create separate _memories_ for agents to store and recall information as needed.


In any project, as long as there are [**Chat**](/components-io) being used, memories are always being stored by default. These are messages from a user to the AI or vice-versa.


To see and access this history of messages, Langflow features a component called **Chat Memory**. It retrieves previous messages and outputs them in structured format or parsed.


To learn the basics about memory in Langflow, check out the [Memory Chatbot](/starter-projects-memory-chatbot) starter example.


Memories can be visualized and managed directly from the **Playground**. You can edit and remove previous messages to inspect and validate the AI’s response behavior. You can remove or edit previous messages to get your models acting just right.


![](/img/playground.png)


Modifying these memories will influence the behavior of the chatbot responses, as long as an agent uses them. Here you have the ability to remove or edit previous messages, allowing them to manipulate and explore how these changes affect model responses.

To modify chat memories, from the playground, click the **Options** menu of any session, and then select **Message Logs**.


![](/img/logs.png)


## Session ID {#4ee86e27d1004e8288a72c633c323703}


---


Chat conversations store messages categorized by a `Session ID`. A single flow can host multiple session IDs, and different flows can also share the same one.


The **Chat Memory** component also retrieves message histories by `Session ID`, which users can change in the component's **Controls** pane.

![](/img/chat-input-controls-pane.png)

By default, if the `Session ID` value is empty, it is set to the same value as `Flow ID`.

You can also display all messages stored across every flow and session by going to **Settings** &gt; **Messages**.

![](/img/settings-messages.png)



## Store chat memory in an external database

Chat memory is retrieved from an external database or vector store using the [**Chat Memory**](/components-helpers#chat-memory) component.

Chat memory is stored to an external database or vector store using the [Store Message](/components-helpers#store-message) component.

The [**Chat Memories**](/Components/components-memories) components provide access to their respective external databases **as memory**. This allows AIs to access external memory for persistence and context retention. For example, connect the **Chat Memory** component to an **AstraDBChatMemory*** component to store the message history in an external Astra DB database.

This example stores and retrieves chat history from an [AstraDBChatMemory](/Components/components-memories#astradbchatmemory-component) component with **Store Message** and **Chat Memory** components.

### Prerequisites

* [An OpenAI API key](https://platform.openai.com/)
* [An Astra DB vector database](https://docs.datastax.com/en/astra-db-serverless/get-started/quickstart.html) with:
	* Application Token
	* API Endpoint

### Connect the chat memory component to an external database

1. Load the [Memory Chatbot](/starter-projects-memory-chatbot) starter project.
This starter project extends the basic prompting flow to include a chat memory component.
2. Add the [Store Message](/components-helpers#store-message) component to the flow.
The **Store message** component stores messages in the external database.
3. Add the [AstraDBChatMemory Component](/Components/components-memories#astradbchatmemory-component) to the flow.
The **Astra DB Chat Memory** component stores and retrieves messages from **Astra DB**.
4. Configure the **AstraDBChatMemory** component with your AstraDB instance details.
	1. In the **Astra DB Application Token** field, add your Astra token. (`AstraCS:...`)
	2. In the **API Endpoint** field, add your Astra database's endpoint. (for example, `https://12adb-bc-5378c845f05a6-e0a12-bd889b4-us-east-2.apps.astra.datastax.com`)
5. Connect the **AstraDBChatMemory** component output to the external memory inputs of the [Chat Memory](/components-helpers#chat-memory) and [Store Message](/components-helpers#store-message) components.
6. Link the [Chat Output](/components-io#chat-output) component to the input of the [Store Message](/components-helpers#store-message) component.

Your completed flow should look like this:

![Sample Flow storing Chat Memory in AstraDB](/img/astra_db_chat_memory_rounded.png)

7. In Langflow, create message traffic by running a flow.
8. Inspect your Astra database's tables and activity.
You will see new tables and traffic created.
