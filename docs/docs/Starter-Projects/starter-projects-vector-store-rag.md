---
title: Vector store RAG
slug: /starter-projects-vector-store-rag
---

import Icon from "@site/src/components/icon";

Retrieval Augmented Generation, or RAG, is a pattern for training LLMs on your data and querying it.


RAG is backed by a **vector store**, a vector database which stores embeddings of the ingested data.


This enables **vector search**, a more powerful and context-aware search.


We've chosen [Astra DB](https://astra.datastax.com/signup?utm_source=langflow-pre-release&utm_medium=referral&utm_campaign=langflow-announcement&utm_content=create-a-free-astra-db-account) as the vector database for this starter flow, but you can follow along with any of Langflow's vector database options.


## Prerequisites

* [An OpenAI API key](https://platform.openai.com/)
* [An Astra DB vector database](https://docs.datastax.com/en/astra-db-serverless/get-started/quickstart.html) with:
	* An Astra DB application token
	* [A collection in Astra](https://docs.datastax.com/en/astra-db-serverless/databases/manage-collections.html#create-collection)


## Open Langflow and start a new project

1. From the Langflow dashboard, click **New Flow**.
2. Select **Vector Store RAG**.
3. The **Vector Store RAG** flow is created.

## Build the vector RAG flow

The vector store RAG flow is built of two separate flows for ingestion and query.

![](/img/starter-flow-vector-rag.png)

The **Load Data Flow** (bottom of the screen) creates a searchable index to be queried for contextual similarity.
This flow populates the vector store with data from a local file.
It ingests data from a local file, splits it into chunks, indexes it in Astra DB, and computes embeddings for the chunks using the OpenAI embeddings model.

The **Retriever Flow** (top of the screen) embeds the user's queries into vectors, which are compared to the vector store data from the **Load Data Flow** for contextual similarity.

- **Chat Input** receives user input from the **Playground**.
- **OpenAI Embeddings** converts the user query into vector form.
- **Astra DB** performs similarity search using the query vector.
- **Parse Data** processes the retrieved chunks.
- **Prompt** combines the user query with relevant context.
- **OpenAI** generates the response using the prompt.
- **Chat Output** returns the response to the **Playground**.

1. Configure the **OpenAI** model component.
	1. To create a global variable for the **OpenAI** component, in the **OpenAI API Key** field, click the <Icon name="Globe" aria-label="Globe" /> **Globe** button, and then click **Add New Variable**.
	2. In the **Variable Name** field, enter `openai_api_key`.
	3. In the **Value** field, paste your OpenAI API Key (`sk-...`).
	4. Click **Save Variable**.
2. Configure the **Astra DB** component.
	1. In the **Astra DB Application Token** field, add your **Astra DB** application token.
	The component connects to your database and populates the menus with existing databases and collections.
	2. Select your **Database**.
	3. Select your **Collection**. Collections are created in your [Astra DB deployment](https://astra.datastax.com) for storing vector data.
	If you don't have a collection, see the [DataStax Astra DB Serverless documentation](https://docs.datastax.com/en/astra-db-serverless/databases/manage-collections.html#create-collection).
	4. Select **Embedding Model** to bring your own embeddings model, which is the connected **OpenAI Embeddings** component.
	The **Dimensions** value must match the dimensions of your collection. You can find this value in the **Collection** in your [Astra DB deployment](https://astra.datastax.com).

If you used Langflow's **Global Variables** feature, the RAG application flow components are already configured with the necessary credentials.

## Run the Vector Store RAG flow

1. Click the **Playground** button. Here you can chat with the AI that uses context from the database you created.
2. Type a message and press Enter. (Try something like "What topics do you know about?")
3. The bot will respond with a summary of the data you've embedded.
