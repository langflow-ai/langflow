---
title: Connect an agent
slug: /chat-with-sqlite
---

import Icon from "@site/src/components/icon";
import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

This tutorial shows you how to build a recommendation engine by connecting an [agent](/agents) to a local SQLite database with customer data.

Then, you present the data in a JavaScript chat application to recommend newer versions of the product.

The main focus of this tutorial is to show you how to connect a local database to an agent, and use the data to take action with another connected tool.

## Prerequisites

- [A running Langflow instance](/get-started-installation)
- [A Langflow API key](/configuration-api-keys)
- [SQLite3](https://www.sqlite.org/docs.html)
- [An OpenAI API key](https://platform.openai.com/api-keys)

This tutorial uses an OpenAI LLM. If you want to use a different provider, you need a valid credential for that provider.

## Optional: Create a local SQLite database

This flow uses data from a local customer database to make a recommendation.

If you don't have a database, you can download and run this SQL command to create one.
This demonstration database contains two customers with three orders for illustrative purposes.
If you have your own SQLite-compatible database, connect it to the Agent component in the same way.

This tutorial assumes you're running this command at the Langflow repository root.

To create the database from the included SQL command, run the following command:
```sql
sqlite3 recommendation_demo.db < docs/static/files/recommendation_demo.sql
```

## Create an agentic flow that connects to a local database

The following steps modify the [**Simple agent**](/simple-agent) template to connect your SQLite database and a [**Web search**](/components-data#web-search) components as tools for the agent.

1. In Langflow, click **New Flow**, and then select the **Simple agent** template.
2. Remove the **URL** and **Calculator** tools, and instead connect the [**SQL query**](/components-data#sql-query) and [**Web search**](/components-data#web-search) tools to your agent.
The flow appears like this:

![](/img/tutorial-agent-with-sql.png)

3. In the **Agent** component, enter your OpenAI API key.

    If you want to use a different provider or model, edit the **Model Provider**, **Model Name**, and **API Key** fields accordingly.

4. In your SQL Query component, add the address for your database.
If you used the default example, the address is `sqlite:////langflow/recommendation_demo.db`.
5. To verify that your flows is operational, click <Icon name="Play" aria-hidden="true" /> **Playground**, and then ask the LLM a question, such as `Recommend three items based on Alex Smith's previous purchases, and provide web links where they can be purchased.`
The LLM should respond with recommendations and web links for electronics items based on Alex's previous purchases.
The Playground displays the agent's chain of thought as it uses the SQL query component's `run_sql_query` tool to access your database, and the Web search component's `perform_search` tool to find links to related items.

## Send requests to your flow from a JavaScript application

With your flow operational, connect it to a JavaScript application to use the agent's responses.

In this case, we want the application to consume the URLs the agent returns, and not return any chat messages.






## Next steps