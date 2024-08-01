---
title: Document QA
sidebar_position: 2
slug: /starter-projects-document-qa
---



Build a question-and-answer chatbot with a document loaded from local memory.


## Prerequisites {#6555c100a30e4a21954af25e2e05403a}


---

- [Langflow installed and running](/getting-started-installation)
- [OpenAI API key created](https://platform.openai.com/)

## Document QA {#acc90b19d4634c279b3e4e19e4e7ab1d}


---


### Create the Document QA project {#204500104f024553aab2b633bb99f603}

1. From the Langflow dashboard, click **New Project**.
2. Select **Document QA**.
3. The **Document QA** project is created.

![](./626991262.png)


This flow is composed of a standard chatbot with the **Chat Input**, **Prompt**, **OpenAI**, and **Chat Output** components, but it also incorporates a **File** component, which loads a file from your local machine. **Parse Data** is used to convert the data from **File** into the **Prompt** component as `{Document}`. The **Prompt** component is instructed to answer questions based on the contents of `{Document}`. This gives the **OpenAI** component context it would not otherwise have access to.


![](./1140665127.png)


### Run the Document QA {#f58fcc2b9e594156a829b1772b6a7191}


1. To select a document to load, in the **File** component, click the **Path** field. Select a local file, and then click **Open**. The file name appears in the field.


![](./1073956357.png)


2. Click the **Playground** button. Here you can chat with the AI that has access to your document's content.


3. Type in a question about the document content and press Enter. You should see a contextual response.

