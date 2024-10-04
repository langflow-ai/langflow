---
title: LangSmith
sidebar_position: 0
slug: /integrations-langsmith
---



LangSmith is a full-lifecycle DevOps service from LangChain that provides monitoring and observability. To integrate with Langflow, just add your LangChain API key as a Langflow environment variable and you are good to go!


## Step-by-step Configuration {#b912579a43984f9a92921232b67c885d}


---

1. Obtain your LangChain API key from [https://smith.langchain.com](https://smith.langchain.com/)
2. Add the following keys to Langflow .env file:

`LANGCHAIN_API_KEY="your-api-key"LANGCHAIN_PROJECT="your-project-name"`


or export the environment variables in your terminal:


`export LANGCHAIN_API_KEY="your-api-key"export LANGCHAIN_PROJECT="your-project-name"`

1. Restart Langflow using `langflow run --env-file .env`
2. Run any project and check the LangSmith dashboard for monitoring and observability.

![](./965098683.png)


![](./1641825585.png)

