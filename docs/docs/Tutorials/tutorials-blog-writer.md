---
title: Blog writer
slug: /tutorials-blog-writer
---

Build a Blog Writer flow for a one-shot application using OpenAI.

This flow extends the Basic Prompting flow with the **URL** and **Parse data** components that fetch content from multiple URLs and convert the loaded data into plain text.

OpenAI uses this loaded data to generate a blog post, as instructed by the **Text input** component.


## Prerequisites {#899268e6c12c49b59215373a38287507}


---

- [Langflow installed and running](/get-started-installation)
- [OpenAI API key created](https://platform.openai.com/)


## Create the blog writer flow {#0c1a9c65b7d640f693ec3aad963416ff}

1. From the Langflow dashboard, click **New Flow**.
2. Select **Blog Writer**.
3. The **Blog Writer** flow is created.

![](/img/starter-flow-blog-writer.png)


This flow creates a one-shot article generator with **Prompt**, **OpenAI**, and **Chat Output** components, augmented with reference content and instructions from the **URL** and **Text Input** components.

The **URL** component extracts raw text and metadata from one or more web links.
The **Parse Data** component converts the data coming from the **URL** component into plain text to feed the prompt.

To examine the flow's prompt, click the **Template** field of the **Prompt** component.

```plain
Reference 1:

{references}

---

{instructions}

Blog:
```

The `{instructions}` value is received from the **Text input** component, and one or more `{references}` are received from a list of URLs parsed from the **URL** component.


### Run the blog writer flow {#b93be7a567f5400293693b31b8d0f81a}

1. Click the **Playground** button. Here you can chat with the AI that has access to the **URL** content.
2. Click the **Lighting Bolt** icon to run it.
3. To write about something different, change the values in the **URL** component and adjust the instructions on the left side bar of the **Playground**. Try again and see what the LLM constructs.

