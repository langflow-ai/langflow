---
title: Quickstart
slug: /get-started-quickstart
---

import Icon from "@site/src/components/icon";

Get to know Langflow by building an OpenAI-powered chatbot application. After you've constructed a chatbot, add Retrieval Augmented Generation (RAG) to chat with your own data.

## Prerequisites

* [An OpenAI API key](https://platform.openai.com/)
* [An Astra DB vector database](https://docs.datastax.com/en/astra-db-serverless/get-started/quickstart.html) with:
	* An AstraDB application token
	* [A collection in Astra](https://docs.datastax.com/en/astra-db-serverless/databases/manage-collections.html#create-collection)

## Open Langflow and start a new project

1. From the Langflow dashboard, click **New Flow**, and then select **Blank Flow**. A blank workspace opens where you can build your flow.

:::tip
If you don't want to create a blank flow, click **New Flow**, and then select **Basic Prompting** for a pre-built flow.
Continue to [Run the basic prompting flow](#run-basic-prompting-flow).
:::

2. Select **Basic Prompting**.

3. The **Basic Prompting** flow is created.

## Build the basic prompting flow

The Basic Prompting flow will look like this when it's completed:

![](/img/starter-flow-basic-prompting.png)

To build the **Basic Prompting** flow, follow these steps:

1. Click **Inputs**, select the **Chat Input** component, and then drag it to the canvas.
The [Chat Input](/components-io#chat-input) component accepts user input to the chat.
2. Click **Prompt**, select the **Prompt** component, and then drag it to the canvas.
The [Prompt](/components-prompts) component combines the user input with a user-defined prompt.
3. Click **Outputs**, select the **Chat Output** component, and then drag it to the canvas.
The [Chat Output](/components-io#chat-output) component prints the flow's output to the chat.
4. Click **Models**, select the **OpenAI** component, and then drag it to the canvas.
The [OpenAI](components-models#openai) model component sends the user input and prompt to the OpenAI API and receives a response.

You should now have a flow that looks like this:

![](/img/quickstart-basic-prompt-no-connections.png)

With no connections between them, the components won't interact with each other.
You want data to flow from **Chat Input** to **Chat Output** through the connections between the components.
Each component accepts inputs on its left side, and sends outputs on its right side.
Hover over the connection ports to see the data types that the component accepts.
For more on component inputs and outputs, see [Components overview](/concepts-components).

5. To connect the **Chat Input** component to the OpenAI model component, click and drag a line from the blue **Message** port to the OpenAI model component's **Input** port.
6. To connect the **Prompt** component to the OpenAI model component, click and drag a line from the blue **Prompt Message** port to the OpenAI model component's **System Message** port.
7. To connect the **OpenAI** model component to the **Chat Output**, click and drag a line from the blue **Text** port to the **Chat Output** component's **Text** port.

Your finished basic prompting flow should look like this:

![](/img/starter-flow-basic-prompting.png)

### Run the Basic Prompting flow {#run-basic-prompting-flow}

Add your OpenAI API key to the OpenAI model component, and add a prompt to the Prompt component to instruct the model how to respond.

1. Add your credentials to the OpenAI component. The fastest way to complete these fields is with Langflow’s [Global Variables](/configuration-global-variables).

	1. In the OpenAI component’s OpenAI API Key field, click the <Icon name="Globe" aria-label="Globe" /> **Globe** button, and then click **Add New Variable**. 
	Alternatively, click your username in the top right corner, and then click **Settings**, **Global Variables**, and then **Add New**.
	2. Name your variable. Paste your OpenAI API key (sk-…​) in the Value field.
	3. In the **Apply To Fields** field, select the OpenAI API Key field to apply this variable to all OpenAI Embeddings components.

2. To add a prompt to the **Prompt** component, click the **Template** field, and then enter your prompt.
The prompt guides the bot's responses to input.
If you're unsure, use `Answer the user as if you were a GenAI expert, enthusiastic about helping them get started building something fresh.`
3. Click **Playground** to start a chat session.
4. Enter a query, and then make sure the bot responds according to the prompt you set in the **Prompt** component.

You have successfully created a chatbot application using OpenAI in the Langflow Workspace.

## Add vector RAG to your application

You created a chatbot application with Langflow, but let's try an experiment.

1. Ask the bot: `Who won the Oscar in 2024 for best movie?`
2. The bot's response is similar to this:

```plain
I'm sorry, but I don't have information on events or awards that occurred after
October 2023, including the Oscars in 2024.
You may want to check the latest news or the official Oscars website
for the most current information.
```

Well, that's unfortunate, but you can load more up-to-date data with **Retrieval Augmented Generation**, or **RAG**.

Vector RAG allows you to load your own data and chat with it, unlocking a wider range of possibilities for your chatbot application.

## Add vector RAG with the Astra DB component

Build on the basic prompting flow and add vector RAG to your chatbot application with the **Astra DB Vector Store** component.

Add document ingestion to your basic prompting flow, with the **Astra DB** component as the vector store.

:::tip
If you don't want to create a blank flow, click **New Flow**, and then select **Vector RAG** for a pre-built flow.
:::

Adding vector RAG to the basic prompting flow will look like this when completed:

![](/img/quickstart-add-document-ingestion.png)

To build the flow, follow these steps:

1. Disconnect the **Chat Input** component from the **OpenAI** component by double-clicking on the connecting line.
2. Click **Vector Stores**, select the **Astra DB** component, and then drag it to the canvas.
The [Astra DB vector store](/components-vector-stores#astra-db-vector-store) component connects to your **Astra DB** database.
3. Click **Data**, select the **File** component, and then drag it to the canvas.
The [File](/components-data#file) component loads files from your local machine.
3. Click **Processing**, select the **Split Text** component, and then drag it to the canvas.
The [Split Text](/components-processing#split-text) component splits the loaded text into smaller chunks.
4. Click **Processing**, select the **Parse Data** component, and then drag it to the canvas.
The [Data to Message](/components-processing#data-to-message) component converts the data from the **Astra DB** component into plain text.
5. Click **Embeddings**, select the **OpenAI Embeddings** component, and then drag it to the canvas.
The [OpenAI Embeddings](/components-embedding-models#openai-embeddings) component generates embeddings for the user's input, which are compared to the vector data in the database.
6. Connect the new components into the existing flow, so your flow looks like this:

![](/img/quickstart-add-document-ingestion.png)

8. Configure the **Astra DB** component.
	1. In the **Astra DB Application Token** field, add your **Astra DB** application token.
	The component connects to your database and populates the menus with existing databases and collections.
	2. Select your **Database**.
	3. Select your **Collection**. Collections are created in your [Astra DB deployment](https://astra.datastax.com) for storing vector data.
	If you don't have a collection, see the [DataStax Astra DB Serverless documentation](https://docs.datastax.com/en/astra-db-serverless/databases/manage-collections.html#create-collection).
	4. Select **Embedding Model** to bring your own embeddings model, which is the connected **OpenAI Embeddings** component.
	The **Dimensions** value must match the dimensions of your collection. This value can be found in your **Collection** in your [Astra DB deployment](https://astra.datastax.com).

If you used Langflow's **Global Variables** feature, the RAG application flow components are already configured with the necessary credentials.

### Run the chatbot with retrieved context

1. Modify the **Prompt** component to contain variables for both `{user_question}` and `{context}`.
The `{context}` variable gives the bot additional context for answering `{user_question}` beyond what the LLM was trained on.

```plain
Given the context
{context}
Answer the question
{user_question}
```

2. In the **File** component, upload a text file from your local machine with data you want to ingest into the **Astra DB** component database.
This example uploads an up-to-date CSV about Oscar winners.
3. Click **Playground** to start a chat session.
4. Ask the bot: `Who won the Oscar in 2024 for best movie?`
5. The bot's response should be similar to this:

```plain
The Oscar for Best Picture in 2024 was awarded to "Oppenheimer,"
produced by Emma Thomas, Charles Roven, and Christopher Nolan.
```

Adding an **Astra DB** vector store brought your chatbot all the way into 2024.
You have successfully added RAG to your chatbot application using the **Astra DB** component.

## Next steps

This example used movie data, but the RAG pattern can be used with any data you want to load and chat with.

Make the **Astra DB** database the brain that [Agents](/agents-overview) use to make decisions.

Expose this flow as an [API](/concepts-api) and call it from your external applications.

For more on the **Astra DB** component, see [Astra DB vector store](/components-vector-stores#astra-db-vector-store).
