---
title: Connect an Astra DB MCP server to Langflow
slug: /mcp-component-astra
---

Use the [MCP server component](/components-tools#mcp-server) to connect Langflow to a [Datastax Astra DB MCP server](https://github.com/datastax/astra-db-mcp).

1. Install an LTS release of [Node.js](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm).
2. Create an [OpenAI](https://platform.openai.com/) API key.
3. Create an [Astra DB Serverless (Vector) database](https://docs.datastax.com/en/astra-db-serverless/databases/create-database.html#create-vector-database), if you don't already have one.
4. Get your database's **Astra DB API endpoint** and an **Astra DB application token** with the Database Administrator role. For more information, see [Generate an application token for a database](https://docs.datastax.com/en/astra-db-serverless/administration/manage-application-tokens.html#database-token).
5. Create a [Simple agent starter project](/starter-projects-simple-agent).
6. Remove the **URL** tool and replace it with an [MCP server](/components-tools#mcp-server) component.
The flow should look like this:
![MCP stdio component](/img/mcp-server-component.png)
7. In the **MCP server** component, in the **MCP command** field, add the following code.
Replace the values for `ASTRA_TOKEN` and `ASTRA_ENDPOINT` with the values from your Astra database.

```text
env ASTRA_DB_APPLICATION_TOKEN=ASTRA_TOKEN ASTRA_DB_API_ENDPOINT=ASTRA_ENDPOINT npx -y @datastax/astra-db-mcpnpx -y @datastax/astra-db-mcp
```

:::important
Langflow passes environment variables from the `.env` file to MCP, but not global variables declared in the UI.
To add the values for `ASTRA_DB_APPLICATION_TOKEN` and `ASTRA_DB_API_ENDPOINT` as global variables, add them to Langflow's `.env` file at startup.
For more information, see [global variables](/configuration-global-variables).
:::

8. In the **Agent** component, add your **OpenAI API key**.
9. Open the **Playground**, and then ask the agent, `What collections are available?`

Since Langflow is connected to your Astra DB database through the MCP, the agent chooses the correct tool and connects to your database to retrieve the answer.
```text
The available collections in your database are:
collection_002
hardware_requirements
load_collection
nvidia_collection
software_requirements
```