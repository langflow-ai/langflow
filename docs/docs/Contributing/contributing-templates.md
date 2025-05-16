---
title: Contribute templates
slug: /contributing-templates
---

Follow these best practices when submitting a template to Langflow.

For template formatting examples, see the Langflow repository's [starter_projects](https://github.com/langflow-ai/langflow/tree/main/src/backend/base/langflow/initial_setup/starter_projects) folder.

## Create a PR to submit your template

Follow these steps to submit your template:

1. Fork the Langflow repository on GitHub.
2. Add your `template.json` file to the `src/backend/base/langflow/initial_setup/starter_projects` folder in your fork.
3. Create a Pull Request from your fork to the main Langflow repository.
4. Include a screenshot of your template in the PR.
5. The Langflow team will review your PR, offer feedback, and merge the template.

## Name

The template name must be concise and contain no more than three words.
Capitalize only the first letter of each word.
For example, **Blog Writer** or **Travel Planning Agent**.

## Description

The description is displayed in the UI to guide users to the template. It should be a brief and informative description of what the template does and its intended use cases.

For example:

```json
  "description": "Auto-generate a customized blog post from instructions and referenced articles.",
```

## Icons

Langflow uses the [Lucide](https://lucide.dev/icons/) icon library.

## Flow

Do not use custom components in your template. Only use components that are available in the sidebar.

Include notes in the template to guide users on how the template functions.
Notes accept Markdown syntax.
A single note will usually suffice.

For example:

```text
# Financial Assistant Agents

The Financial Assistant Agent retrieves web content and writes reports about finance.

## Prerequisites

* [OpenAI API Key](https://platform.openai.com/)
* [Tavily AI Search key](https://docs.tavily.com/welcome)
* [Sambanova API key](https://sambanova.ai/)

## Quickstart

1. In both **Agent** components, add your OpenAI API key.
2. In the **Model Provider** field, select **Sambanova**, and select a model.
3. In the **Sambanova** component, add your **Sambanova API key**.
4. In the **Tavily Search** component, add your **Tavily API key**.
5. Click the **Playground** and ask `Why did Nvidia stock drop in January?`
```

## Format

Submit the template in JSON format.

## Tags

Assign the template to one of the existing template categories.

Available categories include:

* Assistants
* Classification
* Coding
* Content Generation
* Q&A
* Prompting
* RAG
* Agents

For more information, see the Langflow repository's [template categories](https://github.com/langflow-ai/langflow/blob/main/src/frontend/src/modals/templatesModal/index.tsx#L27-L57).
