---
title: Blog writer
slug: /blog-writer
---

Build a Blog Writer flow for a one-shot application using OpenAI.

This flow extends the Basic Prompting flow with the **URL** and **Parser** components that fetch content from multiple URLs and convert the loaded data into plain text.

OpenAI uses this loaded data to generate a blog post, as instructed by the **Text Input** and **Prompt** components.

## Prerequisites

- [A running Langflow instance](/get-started-installation)
- [An OpenAI API key](https://platform.openai.com/)

## Create the blog writer flow

1. From the Langflow dashboard, click **New Flow**.
2. Select **Blog Writer**.
3. The **Blog Writer** flow is created.

![](/img/starter-flow-blog-writer.png)


This flow creates a blog article generator with **Prompt**, **OpenAI**, and **Chat Output** components, augmented with reference content and instructions from the **URL** and **Text Input** components.

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

1. Click the **Playground** button, and then click **Run Flow**.
A blog post about Langflow is generated, with content sourced from `langflow.org` and `docs.langflow.org`.
2. To write about something different, change the values in the **URL** component and adjust the instructions on the left side bar of the **Playground**. Try again and see what the LLM constructs.

