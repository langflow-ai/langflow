---
title: What is Langflow?
slug: /about-langflow
---

Langflow is an open-source, Python-based, customizable framework for building AI applications.
It supports important AI functionality, like agents and Model Context Protocol (MCP), and it doesn't require you to use specific large language models (LLMs) or vector stores.

The visual editor simplifies prototyping of application workflows, enabling developers to quickly turn their ideas into powerful, real-world solutions.

:::tip Try it
Build and run your first flow in minutes: [Install Langflow](/get-started-installation), and then try the [Quickstart](/get-started-quickstart).
:::

## Application development and prototyping

Langflow can help you develop a wide variety of AI applications, such as [chatbots](/memory-chatbot), [document analysis systems](/document-qa), [content generators](/blog-writer), and [agentic applications](/simple-agent).

### Create flows in minutes

The primary purpose of Langflow is to create and serve flows, which are functional representations of application workflows.

To [build a flow](/concepts-flows), you connect and configure component nodes. Each component is a single step in the workflow.

With Langflow's [visual editor](/concepts-overview), you can drag and drop components to quickly build and test a functional AI application workflow.
For example, you could build a chatbot flow for an e-commerce store that uses an LLM and a product data store to allow customers to ask questions about the store's products.

![Basic prompting flow within in the workspace](/img/workspace-basic-prompting.png)

### Test flows in real-time

You can use the [Playground](/concepts-playground) to test flows without having to build your entire application stack.
You can interact with your flows and get real-time feedback about flow logic and response generation.

You can also run individual components to test dependencies in isolation.

### Run and serve flows

You can use your flows as prototypes for more formal application development, or you can use the Langflow API to embed your flows into your application code.

For more extensive projects, you can build Langflow as a dependency or deploy a Langflow server to serve flows over the public internet.

For more information, see the following:

* [Share and embed flows](/concepts-publish)
* [Get started with the Langflow API](/api-reference-api-examples)
* [Develop an application with Langflow](/develop-application)
* [Langflow deployment overview](/deployment-overview)

## Endless modifications and integrations

Langflow provides [components](/concepts-components) that support many services, tools, and functionality that are required for AI applications.

Some components are generalized, such as inputs, outputs, and data stores.
Others are specialized, such as agents, language models, and embedding providers.

All components offer parameters that you can set to fixed or variable values. You can also use tweaks to temporarily override flow settings at run-time.

### Agent and MCP support

In addition to building agentic flows with Langflow, you can leverage Langflow's built-in agent and MCP features:

* [Use Langflow Agents](/agents)
* [Use components and flows as Agent tools](/agents-tools)
* [Use Langflow as an MCP server](/mcp-server)
* [Use Langflow as an MCP client](/mcp-client)

### Extensibility

In addition to the core components, Langflow supports custom components.

You can use custom components developed by others, and you can develop your own custom components for personal use or to share with other Langflow users.

For more information, see the following:

* [Contribute to Langflow](/contributing-how-to-contribute)
* [Create custom Python components](/components-custom-components)

## Next steps

* [Install Langflow](/get-started-installation)
* [Quickstart](/get-started-quickstart)