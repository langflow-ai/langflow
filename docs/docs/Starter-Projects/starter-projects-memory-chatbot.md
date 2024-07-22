---
title: Memory Chatbot
sidebar_position: 3
slug: /starter-projects-memory-chatbot
---



This flow extends the [Basic Prompting](http://localhost:3000/starter-projects/basic-prompting) flow to include a chat memory. This makes the AI remember previous user inputs.


## Prerequisites {#a71d73e99b1543bbba827207503cf31f}


---

- [Langflow installed and running](/getting-started-installation)
- [OpenAI API key created](https://platform.openai.com/)

## Memory Chatbot {#54073bf7eb1b4ff490c313f5612f0842}


---


### Create the memory chatbot project {#70ce99381b7043a1b417a81e9ae74c72}

1. From the Langflow dashboard, click **New Project**.
2. Select **Memory Chatbot**.
3. The **Memory Chatbot** flow is created .

![](./1511598495.png)


This flow uses the same components as the Basic Prompting one, but extends it with a **Chat Memory** component. This component retrieves previous messages and sends them to the **Prompt** component to fill a part of the **Template** with context.


By clicking the template, you'll see the prompt editor like below:


![](./450254819.png)


This gives the **OpenAI** component a memory of previous chat messages.


### Run {#a110cad860584c98af1aead006035378}

1. Open the Playground.
2. Type multiple questions. In the **Memories** tab, your queries are logged in order. Up to 100 queries are stored by default. Try telling the AI your name and asking `What is my name?` on a second message, or `What is the first subject I asked you about?` to validate that previous knowledge is taking effect.

:::tip

Check and adjust advanced parameters by opening the Advanced Settings of the **Chat Memory** component.

:::




![](./1079168789.png)


## Session ID {#4e68c3c0750942f98c45c1c45d7ffbbe}


---


`SessionID` is a unique identifier in Langflow that stores conversation sessions between the AI and a user. A `SessionID` is created when a conversation is initiated, and then associated with all subsequent messages during that session.


In the **Memory Chatbot** flow you created, the **Chat Memory** component references past interactions by **Session ID**. You can demonstrate this by modifying the **Session ID** value to switch between conversation histories.

1. In the **Session ID** field of the **Chat Memory** and **Chat Input** components, add a **Session ID** value like `MySessionID`.
2. Now, once you send a new message the **Playground**, you should have a new memory created on the **Memories** tab.
3. Notice how your conversation is being stored in different memory sessions.

:::tip

Every chat component in Langflow comes with a `SessionID`. It defaults to the flow ID. Explore how changing it affects what the AI remembers.

:::




Learn more about memories in the [Chat Memory](/guides-chat-memory) section.

