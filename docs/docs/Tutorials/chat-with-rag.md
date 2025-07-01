---
title: Create a chatbot with your own files
slug: /chat-with-rag
---

import Icon from "@site/src/components/icon";
import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

Create a chatbot application that uses Retrieval Augmented Generation.
This approach embeds your data as vectors in a local vector database.

## Prerequisites

- [A running Langflow instance](/get-started-installation)
- [An OpenAI API key](https://platform.openai.com/api-keys)

## Create a vector RAG flow

1. In Langflow, click **New Flow**, and then select the **Vector Store RAG** template.
2. Add your **OpenAI** API key to the **OpenAI Embeddings** components.
3. You can use the Astra DB vector store components if you want, but this example replaces them with FAISS vector stores.

    Your loading flow should look like this:

    ![File loader chat flow](/img/tutorial-embed-files.png)

    Your chat flow should look like this:

    ![Chat with RAG flow](/img/tutorial-chat-rag-flow.png)

    The flow is complete.
    If you'd like, add files to the File component and chat with it within the Langflow IDE.
    In the next section, you will load files and chat with your flow from a Python application.


## Load and embed a file

You have two options for loading and embedding a file into your vector database: the UI, or the `/v2/files` endpoint.

The UI is the easiest method.

<Tabs>
  <TabItem value="UI" label="UI" default>

    1. In the **File component**, click **File**.
    2. Select the local file you want to upload, and then click **Open**.
        The file is loaded to your Langflow server.
    3. To run the embedding flow, in the vector store component, click <Icon name="Play" aria-hidden="true" /> **Run component**.
        The file is split by chunk overlap and chunk size, and then the chunked files are embedded by the Embeddings component into the vector database.

  </TabItem>
  <TabItem value="API" label="API">



  </TabItem>
</Tabs>

## Chat with your flow from a JavaScript application

## Chat with your embedded documents


## Next steps

* [Model Context Protocol (MCP) servers](/mcp-server)
* [Langflow deployment overview](/deployment-overview)