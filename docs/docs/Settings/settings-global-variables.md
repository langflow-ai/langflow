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

You can also create global variables in Settings &gt; Global Variables.

:::




![](./418277339.png)


To view and manage your project's global environment variables, visit **Settings** &gt; **Global Variables**.


### Configure Environment Variables in your .env file {#76844a93dbbc4d1ba551ea1a4a89ccdd}


Setting `LANGFLOW_STORE_ENVIRONMENT_VARIABLES` to `true` in your `.env` file (default) adds all variables in `LANGFLOW_VARIABLES_TO_GET_FROM_ENVIRONMENT` to your user's Global Variables.


These variables are accessible like any other Global Variable.


:::info

To prevent this behavior, set `LANGFLOW_STORE_ENVIRONMENT_VARIABLES` to `false` in your `.env` file.

:::




You can specify variables to get from the environment by listing them in `LANGFLOW_VARIABLES_TO_GET_FROM_ENVIRONMENT`, as a comma-separated list (e.g., _`VARIABLE1, VARIABLE2`_).


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

<ReactPlayer controls url="https://youtu.be/RedPOCsYNAM" />


### Precautions

Global variables are stored in the database, and their values are protected by encryption using a secret
key. To preserve access to your global variables and avoid losing them, you should take a few precautions:

1. Keep your secret key safe: Even if your database is secure, it won’t be of much use if you can't decrypt
the values. Ideally, you can set your own secret key using the `LANGFLOW_SECRET_KEY` environment variable. If
you don't provide a custom value for the secret key, one will be generated randomly and saved in the Langflow
installation directory.

2. We use SQLite as the default database, and Langflow saves the database file in the installation directory.
To ensure the security of your data, it’s a good practice to regularly back up this file. If needed, you can
also change the database location by setting the `LANGFLOW_SAVE_DB_IN_CONFIG_DIR` environment variable to true
and configuring `LANGFLOW_CONFIG_DIR` to point to a directory of your choice. Alternatively, you can opt to use
an external database such as PostgreSQL, in which case these configurations are no longer necessary.

For your convenience, if you’re running Langflow directly on your system or in a virtual environment
via a pip installation, you can set these values by providing Langflow with a .env file containing these
environment variables, using the following command:

```bash
langflow run --env-file .env
```

If you’re running Langflow in a Docker container, you can set these values by providing Langflow with:

```bash
docker run \
        --privileged \
        --user 1000:0 \
        -p 7860:7860 \
        -e LANGFLOW_SECRET_KEY=<YOUR_SECRET_KEY_VALUE> \
        -e LANGFLOW_SAVE_DB_IN_CONFIG_DIR=true \
        -e LANGFLOW_CONFIG_DIR=/app/container_path \
        -v $(PWD)/your_path:/app/container_path \
        langflowai/langflow:latest
```

or

```bash
docker run \
	--privileged \
	--user 1000:0 \
	-p 7860:7860 \
	--env-file .env \
	-v $(PWD)/your_path:/app/container_path \
    langflowai/langflow:latest
```
