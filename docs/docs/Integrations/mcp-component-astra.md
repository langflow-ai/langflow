---
title: Connect an Astra DB MCP server to Langflow
slug: /mcp-component-astra
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';
import Icon from "@site/src/components/icon";

Use the [MCP connection component](../Components/mcp-client.md) to connect Langflow to a [Datastax Astra DB MCP server](https://github.com/datastax/astra-db-mcp).

1. Install an LTS release of [Node.js](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm).

2. Create an [OpenAI](https://platform.openai.com/) API key.

3. Create an [Astra DB Serverless (Vector) database](https://docs.datastax.com/en/astra-db-serverless/databases/create-database.html#create-vector-database), if you don't already have one.

4. Get your database's **Astra DB API endpoint** and an **Astra DB application token** with the Database Administrator role. For more information, see [Generate an application token for a database](https://docs.datastax.com/en/astra-db-serverless/administration/manage-application-tokens.html#database-token).

5. Create a [Simple agent starter project](/starter-projects-simple-agent).

6. Remove the **URL** tool and replace it with an [MCP connection component](../Components/mcp-client.md).
The flow should look like this:

    ![MCP connection component connecting to Astra](/img/component-mcp-astra-db.png)

7. In the **MCP connection** component, in the **MCP server** field, add the following code to connect to an Astra DB MCP server:

    ```bash
    npx -y @datastax/astra-db-mcp
    ```

8. In the **MCP connection** component, in the **Env** fields, add variables for `ASTRA_DB_APPLICATION_TOKEN` and `ASTRA_DB_API_ENDPOINT` with the values from your Astra database.

    :::important
    Langflow passes environment variables from the `.env` file to MCP, but not global variables declared in the UI.
    To add the values for `ASTRA_DB_APPLICATION_TOKEN` and `ASTRA_DB_API_ENDPOINT` as global variables, add them to Langflow's `.env` file at startup.
    For more information, see [global variables](/configuration-global-variables).
    :::

    ```bash
    ASTRA_DB_APPLICATION_TOKEN=AstraCS:...
    ```

9. To add another variable, click <Icon name="Plus" aria-hidden="true"/> **Add More**.

    ```bash
    ASTRA_DB_API_ENDPOINT=https://...-us-east-2.apps.astra.datastax.com
    ```

10. In the **Agent** component, add your **OpenAI API key**.

11. Open the **Playground**, and then ask the agent, `What collections are available?`

    Since Langflow is connected to your Astra DB database through the MCP, the agent chooses the correct tool and connects to your database to retrieve the answer.

    ```text
    The available collections in your database are:
    collection_002
    hardware_requirements
    load_collection
    nvidia_collection
    software_requirements
    ```