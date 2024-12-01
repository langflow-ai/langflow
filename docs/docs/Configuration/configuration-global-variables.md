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

7. Optional: Use the **Apply To Fields** menu to select one or more fields that you want Langflow to automatically apply your global variable to.
For example, if you select **OpenAI API Key**, Langflow will automatically apply the variable to any **OpenAI API Key** field.

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

- Global variables that you add from the the environment always have the **Credential** type.
:::

:::tip
If you want to explicitly prevent Langflow from sourcing global variables from the environment, set `LANGFLOW_STORE_ENVIRONMENT_VARIABLES` to `false` in your `.env` file:

```plaintext title=".env"
LANGFLOW_STORE_ENVIRONMENT_VARIABLES=false
```

:::

<!-- TODO: Most of the information in this section should be documented on other pages dedicated to environment variables and best practices. However, until those pages exist, we'll just have to keep this information here. Once those pages are added, we can reduce this section to a bulleted list with cross references. -->
## Precautions

Even though Langflow stores global variables in its internal database, and encrypts the values using a secret key, you should consider taking extra precautions to ensure the database and secret key are protected.

### Use a custom secret key

By default, Langflow generates a random secret key.
However, you should provide your own secret key, as it's more secure to use a key that is already known to you.

Use the `LANGFLOW_SECRET_KEY` environment variable to provide a custom value for the secret key when you start Langflow.

### Protect the secret key

Make sure to store the secret key in a secure location.

By default, Langflow stores the secret key in its configuration directory.
The location of the configuration directory depends on your operating system:

- macOS: `~/Library/Caches/langflow/secret_key`
- Linux: `~/.cache/langflow/secret_key`
- Windows: `%USERPROFILE%\AppData\Local\langflow\secret_key`

To change the location of the the configuration directory, and thus the location of the secret key, set the `LANGFLOW_CONFIG_DIR` environment variable to your preferred storage directory.

### Protect the database

Make sure to store Langflow's internal database file in a secure location, and take regular backups to prevent accidental data loss.

By default, Langflow stores the database file in its installation directory.
The location of the file depends on your operating system and installation method:

- macOS: `PYTHON_LOCATION/site-packages/langflow/langflow.db`
- Linux: `PYTHON_LOCATION/site-packages/langflow/langflow.db`
- Windows: `PYTHON_LOCATION\Lib\site-packages\langflow\langflow.db`

To change the location of the database file, follow these steps:

1. Set the `LANGFLOW_SAVE_DB_IN_CONFIG_DIR` environment variable to `true`.
2. Set the `LANGFLOW_CONFIG_DIR` environment variable to your preferred storage directory.

<!-- TODO: Add documentation for external database support. -->
<!-- Alternatively, you can configure Langflow to store data in an *external* database, such as PostgreSQL, instead of its own internal database. -->