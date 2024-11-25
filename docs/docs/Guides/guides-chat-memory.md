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


Chat conversations store messages categorized by a `Session ID`. A a single flow can host multiple session IDs, and different flows can also share the same one.


The **Chat Memory** component also retrieves message histories by `Session ID`, which users can change in the component's **Controls** pane.

![](/img/chat-input-controls-pane.png)

By default, if the `Session ID` value is empty, it is set to the same value as `Flow ID`.

You can also display all messages stored across every flow and session by going to **Settings** &gt; **Messages**.

![](/img/settings-messages.png)



## Chat Memory Storing in a Database

Chat memory can be retrieved from an external database or vector store using the [**Chat Memory**](/components-helpers#chat-memory) component, and messages can be stored using the [**Store Message**](/components-helpers#store-message) component. External databases can be accessed as memory through the respective [**Chat Memories components**](/Components/components-memories).

Steps to Store and Retrieve Chat History from a Database:
	1.	Load the [Memory Chatbot](/starter-projects-memory-chatbot) Starter Project.
	2.	Add the [Store Message](/components-helpers#store-message) component to the flow.
	3.	Add the [AstraDBChatMemory Component](/Components/components-memories#astradbchatmemory-component) to the flow.
	4.	Configure the AstraDBChatMemory Component with your AstraDB instance details.
	5.	Connect the AstraDBChatMemory Component output to the external memory inputs of the [Chat Memory](/components-helpers#chat-memory) and [store Message](/components-helpers#store-message) components.
	6.	Link the [Chat Output](/components-io#chat-output) component to the input of the [Store Message](/components-helpers#store-message) component. 

Example Flow

![Sample Flow storing Chat Memory in AstraDB](/img/AstraDBChatMemory.png)


