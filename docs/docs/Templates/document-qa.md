---
title: Document QA
slug: /document-qa
---

Build a question-and-answer chatbot with a document loaded from local memory.

## Prerequisites

- [A running Langflow instance](/docs/get-started-installation)
- [An OpenAI API key](https://platform.openai.com/)

## Create the document QA flow

1. From the Langflow dashboard, click **New Flow**.
2. Select **Document QA**.
3. The **Document QA** flow is created.

![](/img/starter-flow-document-qa.png)

This flow is composed of a chatbot with the **Chat Input**, **Prompt**, **OpenAI**, and **Chat Output** components, but also incorporates a **File** component, which loads a file from your local machine. The **Parser** component converts the data from the **File** component into the **Prompt** component as `{Document}`.

The **Prompt** component is instructed to answer questions based on the contents of `{Document}`. This gives the **OpenAI** component context it would not otherwise have access to.

### Run the document QA flow

1. Add your **OpenAI API key** to the **Open AI** model component.

2. To select a document to load, in the **File** component, click the **Select files** button. Select a local file or a file loaded with [File management](/docs/concepts-file-management), and then click **Select file**. The file name appears in the component.

3. Click the **Playground** button. Enter a question about the loaded document's content. You should receive a contextual response indicating that the AI has read your document.

