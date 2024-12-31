---
title: Global variables
sidebar_position: 5
slug: /configuration-global-variables
---

import ReactPlayer from "react-player";
import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

Global variables let you store and reuse generic input values and credentials across your projects.
You can use a global variable in any text input field that displays the 🌐 icon.

Langflow stores global variables in its internal database, and encrypts the values using a secret key.

## Create a global variable {#3543d5ef00eb453aa459b97ba85501e5}

1. In the Langflow UI, click your profile icon, and then select **Settings**.

2. Click **Global Variables**.

3. Click **Add New**.

4. In the **Create Variable** dialog, enter a name for your variable in the **Variable Name** field.

5. Optional: Select a **Type** for your global variable. The available types are **Generic** (default) and **Credential**.

   No matter which **Type** you select, Langflow still encrypts the **Value** of the global variable.

6. Enter the **Value** for your global variable.

7. Optional: Use the **Apply To Fields** menu to select one or more fields that you want Langflow to automatically apply your global variable to. For example, if you select **OpenAI API Key**, Langflow will automatically apply the variable to any **OpenAI API Key** field.

8. Click **Save Variable**.

You can now select your global variable from any text input field that displays the 🌐 icon.

:::info
Because values are encrypted, you can't view the actual values of your global variables.
In **Settings > Global Variables**, the **Value** column shows the encrypted hash for **Generic** type variables, and shows nothing for **Credential** type variables.
:::

## Edit a global variable

1. In the Langflow UI, click your profile icon, and then select **Settings**.

2. Click **Global Variables**.

3. Click on the global variable you want to edit.

4. In the **Update Variable** dialog, you can edit the following fields: **Variable Name**, **Value**, and **Apply To Fields**.

5. Click **Update Variable**.

## Delete a global variable

:::warning
Deleting a global variable permanently deletes any references to it from your existing projects.
:::

1. In the Langflow UI, click your profile icon, and then select **Settings**.

2. Click **Global Variables**.

3. Click the checkbox next to the global variable that you want to delete.

4. Click the Trash icon.

The global variable, and any existing references to it, are deleted.

## Add global variables from the environment {#76844a93dbbc4d1ba551ea1a4a89ccdd}

### Custom environment variables

You can use the `LANGFLOW_VARIABLES_TO_GET_FROM_ENVIRONMENT` environment variable to source global variables from your runtime environment.

<Tabs>

<TabItem value="local" label="Local" default>

If you installed Langflow locally, you must define the `LANGFLOW_VARIABLES_TO_GET_FROM_ENVIRONMENT` environment variable in a `.env` file.

1. Create a `.env` file and open it in your preferred editor.

2. Add the `LANGFLOW_VARIABLES_TO_GET_FROM_ENVIRONMENT` environment variable as follows:

   ```plaintext title=".env"
   LANGFLOW_VARIABLES_TO_GET_FROM_ENVIRONMENT=VARIABLE1,VARIABLE2
   ```

   Replace `VARIABLE1,VARIABLE2` with a comma-separated list (no spaces) of variables that you want Langflow to source from the environment.
   For example, `my_key,some_string`.

3. Save and close the file.

4. Start Langflow with the `.env` file:

   ```bash
   VARIABLE1="VALUE1" VARIABLE2="VALUE2" python -m langflow run --env-file .env
   ```

   :::note
   In this example, the environment variables (`VARIABLE1="VALUE1"` and `VARIABLE2="VALUE2"`) are prefixed to the startup command.
   This is a rudimentary method for exposing environment variables to Python on the command line, and is meant for illustrative purposes.
   Make sure to expose your environment variables to Langflow in a manner that best suits your own environment.
   :::

5. Confirm that Langflow successfully sourced the global variables from the environment.

   1. In the Langflow UI, click your profile icon, and then select **Settings**.

   2. Click **Global Variables**.

   The environment variables appear in the list of **Global Variables**.

</TabItem>

<TabItem value="docker" label="Docker">

If you're using Docker, you can pass `LANGFLOW_VARIABLES_TO_GET_FROM_ENVIRONMENT` directly from the command line or from a `.env` file.

To pass `LANGFLOW_VARIABLES_TO_GET_FROM_ENVIRONMENT` directly from the command line:

```bash
docker run -it --rm \
    -p 7860:7860 \
    -e LANGFLOW_VARIABLES_TO_GET_FROM_ENVIRONMENT="VARIABLE1,VARIABLE2" \
    -e VARIABLE1="VALUE1" \
    -e VARIABLE2="VALUE2" \
    langflowai/langflow:latest
```

To pass `LANGFLOW_VARIABLES_TO_GET_FROM_ENVIRONMENT` from a `.env` file:

```bash
docker run -it --rm \
    -p 7860:7860 \
    --env-file .env \
    -e VARIABLE1="VALUE1" \
    -e VARIABLE2="VALUE2" \
    langflowai/langflow:latest
```

</TabItem>

</Tabs>

:::info
When adding global variables from the environment, the following limitations apply:

- You can only source the **Name** and **Value** from the environment.
  To add additional parameters, such as the **Apply To Fields** parameter, you must edit the global variables in the Langflow UI.

- Global variables that you add from the environment always have the **Credential** type.
  :::

:::tip
If you want to explicitly prevent Langflow from sourcing global variables from the environment, set `LANGFLOW_STORE_ENVIRONMENT_VARIABLES` to `false` in your `.env` file:

```plaintext title=".env"
LANGFLOW_STORE_ENVIRONMENT_VARIABLES=false
```

:::

### Default environment variables

Langflow automatically detects and converts some environment variables into global variables of the type **Credential**, which are applied to the specific fields in components that require them. Currently, the following variables are supported:

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GOOGLE_API_KEY`
- `COHERE_API_KEY`
- `GROQ_API_KEY`
- `HUGGINGFACEHUB_API_TOKEN`
- `SEARCHAPI_API_KEY`
- `SERPAPI_API_KEY`
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_API_VERSION`
- `AZURE_OPENAI_API_INSTANCE_NAME`
- `AZURE_OPENAI_API_DEPLOYMENT_NAME`
- `AZURE_OPENAI_API_EMBEDDINGS_DEPLOYMENT_NAME`
- `PINECONE_API_KEY`
- `ASTRA_DB_APPLICATION_TOKEN`
- `ASTRA_DB_API_ENDPOINT`
- `UPSTASH_VECTOR_REST_URL`
- `UPSTASH_VECTOR_REST_TOKEN`
- `VECTARA_CUSTOMER_ID`
- `VECTARA_CORPUS_ID`
- `VECTARA_API_KEY`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

For information about other environment variables and their usage, see [Environment Variables](/environment-variables).

## Security best practices

For information about securing your global variables and other sensitive data, see [Security best practices](/configuration-security-best-practices).