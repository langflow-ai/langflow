---
title: Quickstart
slug: /get-started-quickstart
---

import Icon from "@site/src/components/icon";
import DownloadableJsonFile from "@theme/DownloadableJsonFile";

Get started quickly with Langflow by loading a template, modifying it, and running it.

## Prerequisites

- [A running Langflow instance](/get-started-installation)
- [An OpenAI API key](https://platform.openai.com/)

## Run the agent template flow

Langflow includes template flows to demonstrate different use cases.

1. To open the **Simple Agent** template flow, click **New Flow**, and then select **Simple Agent**.

![Simple agent starter flow](/img/starter-flow-simple-agent.png)

This flow connects [Chat I/O](/components-chat-io) components with an [Agent](/components-agent) component.
As you ask the agent questions, it may call the connected [Calculator](/components-helpers#calculator) and [URL](/components-data#url) tools to answer.

2. In the agent component, in the **OpenAI API Key** field, add your OpenAI API key.

3. To run the flow, click <Icon name="Play" aria-hidden="true"/> **Playground**.

4. Ask the agent a simple math question, such as `I want to add 4 and 4.`
The Playground displays the agent's reasoning process as it correctly selects the Calculator component's `evaluate_expression` action.

![Playground with Agent calculator tool](/img/quickstart-simple-agent-playground.png)

5. Ask the agent about current events.
For this request, the agent selects the URL component's `fetch_content` action, and returns a summary of current headlines.

You have successfully run your first flow.

## Add tools




