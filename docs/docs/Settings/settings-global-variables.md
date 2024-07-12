---
title: Global Variables
sidebar_position: 0
slug: /settings-global-variables
---

import ReactPlayer from "react-player";

:::info

This page may contain outdated information. It will be updated as soon as possible.

:::




Global Variables are a useful feature of Langflow, allowing you to define reusable variables accessed from any Text field in your project.


**TL;DR**

- Global Variables are reusable variables accessible from any Text field in your project.
- To create one, click the 🌐 button in a Text field and then **+ Add New Variable**.
- Define the **Name**, **Type**, and **Value** of the variable.
- Click **Save Variable** to create it.
- All Credential Global Variables are encrypted and accessible only by you.
- Set _`LANGFLOW_STORE_ENVIRONMENT_VARIABLES`_ to _`true`_ in your `.env` file to add all variables in _`LANGFLOW_VARIABLES_TO_GET_FROM_ENVIRONMENT`_ to your user's Global Variables.

### Create and Add a Global Variable {#3543d5ef00eb453aa459b97ba85501e5}


To create and add a global variable, click the 🌐 button in a Text field, and then click **+ Add New Variable**.


Text fields are where you write text without opening a Text area, and are identified with the 🌐 icon.


For example, to create an environment variable for the **OpenAI** component:

1. In the **OpenAI API Key** text field, click the 🌐 button, then **Add New Variable**.
2. Enter `openai_api_key` in the **Variable Name** field.
3. Paste your OpenAI API Key (`sk-...`) in the **Value** field.
4. Select **Credential** for the **Type**.
5. Choose **OpenAI API Key** in the **Apply to Fields** field to apply this variable to all fields named **OpenAI API Key**.
6. Click **Save Variable**.

You now have a `openai_api_key` global environment variable for your Langflow project.
Subsequently, clicking the 🌐 button in a Text field will display the new variable in the dropdown.


:::tip

You can also create global variables in Settings &gt; Variables and Secrets.

:::




![](./418277339.png)


To view and manage your project's global environment variables, visit **Settings** &gt; **Variables and Secrets**.


### Configure Environment Variables in your .env file {#76844a93dbbc4d1ba551ea1a4a89ccdd}


Setting `LANGFLOW_STORE_ENVIRONMENT_VARIABLES` to `true` in your `.env` file (default) adds all variables in `LANGFLOW_VARIABLES_TO_GET_FROM_ENVIRONMENT` to your user's Global Variables.


These variables are accessible like any other Global Variable.


:::info

To prevent this behavior, set `LANGFLOW_STORE_ENVIRONMENT_VARIABLES` to `false` in your `.env` file.

:::




You can specify variables to get from the environment by listing them in `LANGFLOW_VARIABLES_TO_GET_FROM_ENVIRONMENT`.


Specify variables as a comma-separated list (e.g., _`"VARIABLE1, VARIABLE2"`_) or a JSON-encoded string (e.g., _`'["VARIABLE1", "VARIABLE2"]'`_).


The default list of variables includes the ones below and more:

- ANTHROPIC_API_KEY
- ASTRA_DB_API_ENDPOINT
- ASTRA_DB_APPLICATION_TOKEN
- AZURE_OPENAI_API_KEY
- AZURE_OPENAI_API_DEPLOYMENT_NAME
- AZURE_OPENAI_API_EMBEDDINGS_DEPLOYMENT_NAME
- AZURE_OPENAI_API_INSTANCE_NAME
- AZURE_OPENAI_API_VERSION
- COHERE_API_KEY
- GOOGLE_API_KEY
- GROQ_API_KEY
- HUGGINGFACEHUB_API_TOKEN
- OPENAI_API_KEY
- PINECONE_API_KEY
- SEARCHAPI_API_KEY
- SERPAPI_API_KEY
- UPSTASH_VECTOR_REST_URL
- UPSTASH_VECTOR_REST_TOKEN
- VECTARA_CUSTOMER_ID
- VECTARA_CORPUS_ID
- VECTARA_API_KEY

<ReactPlayer controls url="https://prod-files-secure.s3.us-west-2.amazonaws.com/09f11537-5a5b-4f56-9e8d-de8ebcfae549/7030d3ff-3ecd-44db-8640-9c2295b4e3bc/langflow_global_variables.mp4?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=AKIAT73L2G45HZZMZUHI%2F20240712%2Fus-west-2%2Fs3%2Faws4_request&X-Amz-Date=20240712T232240Z&X-Amz-Expires=3600&X-Amz-Signature=463a0203fa466f5efc5812f6c991821c996ea46f0bcf0ba84177cab56d604621&X-Amz-SignedHeaders=host&x-id=GetObject" />

