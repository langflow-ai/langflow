---
title: Document QA
slug: /document-qa
description: Build a question-and-answer chatbot with document analysis capabilities using a document loaded from local memory.
---

import Icon from "@site/src/components/icon";

This flow demonstrates adding a file to the [File](/components-data#file) component to load a document from your local machine.

## Prerequisites

- [A running Langflow instance](/get-started-installation)
- [An OpenAI API key](https://platform.openai.com/)

## Create the document QA flow

1. From the Langflow dashboard, click **New Flow**.
2. Select **Document QA**.
3. The **Document QA** flow is created.

![Document QA starter flow](/img/starter-flow-document-qa.png)

This flow is composed of a chatbot with the **Chat Input**, **Prompt**, **Language model**, and **Chat Output** components, but also incorporates a **File** component, which loads a file from your local machine. The **Parser** component converts the data from the **File** component into the **Prompt** component as `{Document}`.

The **Prompt** component is instructed to answer questions based on the contents of `{Document}`. This gives the **OpenAI** component context it would not otherwise have access to.

### Run the document QA flow

1. Add your **OpenAI API key** to the **Language model** model component.
	Optionally, create a [global variable](/configuration-global-variables) for the **OpenAI API key**.

	1. In the **OpenAI API Key** field, click <Icon name="Globe" aria-hidden="True" /> **Globe**, and then click **Add New Variable**.
	2. In the **Variable Name** field, enter `openai_api_key`.
	3. In the **Value** field, paste your OpenAI API Key (`sk-...`).
	4. Click **Save Variable**.

2. To select a document to load, in the **File** component, click the **Select files** button. Select a local file or a file loaded with [File management](/concepts-file-management), and then click **Select file**. The file name appears in the component.

3. To run the flow, click <Icon name="Play" aria-hidden="true"/> **Playground**. Enter a question about the loaded document's content. You should receive a contextual response indicating that the LLM has read your document.

