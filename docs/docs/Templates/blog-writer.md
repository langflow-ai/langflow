---
title: Blog writer
slug: /blog-writer
---

import Icon from "@site/src/components/icon";

Build a Blog Writer flow for a one-shot application using OpenAI.

This flow extends the Basic Prompting flow with the [URL](/components-data#url) and [Parser](/components-processing#parser) components that fetch content from multiple URLs and convert the loaded data into plain text.

The [Language model](/components-models) component uses this loaded data to generate a blog post, as instructed by the [Text input](/components-io#text-input) and [Prompt](components-prompts) components.

## Prerequisites

- [A running Langflow instance](/get-started-installation)
- [An OpenAI API key](https://platform.openai.com/)

## Create the blog writer flow

1. From the Langflow dashboard, click **New Flow**.
2. Select **Blog Writer**.
3. The **Blog Writer** flow is created.

![Blog writer starter flow](/img/starter-flow-blog-writer.png)

This flow creates a blog article generator with **Prompt**, **Language Model**, and **Chat Output** components, augmented with reference content and instructions from the **URL** and **Text Input** components.

The **URL** component extracts raw text and metadata from one or more web links.
The **Parser** component converts the data coming from the **URL** component into plain text to feed the prompt.

To examine the flow's prompt, click the **Template** field of the **Prompt** component.

```text
Reference 1:

{references}

---

{instructions}

Blog:
```

The `{instructions}` value is received from the **Text Input** component, and one or more `{references}` are received from a list of URLs parsed from the **URL** component.


### Run the blog writer flow

1. Add your **OpenAI API key** to the **Language model** model component.
	Optionally, create a [global variable](/configuration-global-variables) for the **OpenAI API key**.

	1. In the **OpenAI API Key** field, click <Icon name="Globe" aria-hidden="True" /> **Globe**, and then click **Add New Variable**.
	2. In the **Variable Name** field, enter `openai_api_key`.
	3. In the **Value** field, paste your OpenAI API Key (`sk-...`).
	4. Click **Save Variable**.

2. To run the flow, click <Icon name="Play" aria-hidden="true"/> **Playground**, and then click **Run Flow**.
A blog post about Langflow is generated, with content sourced from `langflow.org` and `docs.langflow.org`.
3. To write about something different, change the values in the **URL** component and adjust the instructions in the **Text input** component. Try again and see what the LLM constructs.