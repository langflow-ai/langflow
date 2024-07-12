---
title: ⚡️ Quickstart
sidebar_position: 2
slug: /getting-started-quickstart
---



## Prerequisites {#b5f154a3a1d242c7bdf57acf0a552732}


---

- [Python &gt;=3.10](https://www.python.org/downloads/release/python-3100/) and [pip](https://pypi.org/project/pip/) or [pipx](https://pipx.pypa.io/stable/installation/)
- [OpenAI API key](https://platform.openai.com/)
- [Langflow installed and running](/getting-started-installation)

## Hello World - Basic Prompting {#67e7cd59d0fa43e3926bdc75134f7472}


Let's start with a Prompt component to instruct an OpenAI Model.


Prompts serve as the inputs to a large language model (LLM), acting as the interface between human instructions and computational tasks. By submitting natural language requests in a prompt to an LLM, you can obtain answers, generate text, and solve problems.

1. From the Langflow dashboard, click **New Project**.
2. Select **Basic Prompting**.

![](./131952085.png)


This flow allows you to chat with the **OpenAI** model by using a **Prompt** to send instructions.


Examine the **Prompt** component. The **Template** field instructs the LLM to `Answer the user as if you were a pirate.` This should be interesting...


To use the **OpenAI** component, you have two options for providing your OpenAI API Key: directly passing it to the component or creating an environment variable. For better security and manageability, creating an environment variable is recommended. Here's how to set it up:


In the **OpenAI API Key** field, click the **Globe** button to access environment variables, and then click **Add New Variable**.

1. In the **Variable Name** field, enter `openai_api_key`.
2. In the **Value** field, paste your OpenAI API Key (`sk-...`).
3. Click **Save Variable**.

By creating an environment variable, you keep your API key secure and make it easier to manage across different components or projects.


## Run the basic prompting flow {#27ac88f4721b42c9a9587326905b8df4}

1. Click the **Playground** button. This where you can interact with your bot.
2. Type any message and press Enter. And... Ahoy! 🏴‍☠️ The bot responds in a piratical manner!

## Modify the prompt for a different result {#5208b946024846169fe59ee206021a4f}

1. To modify your prompt results, in the **Prompt** template, click the **Template** field. The **Edit Prompt** window opens.
2. Change `Answer the user as if you were a pirate` to a different character, perhaps `Answer the user as if you were Harold Abelson.`
3. Run the basic prompting flow again. The response will be markedly different.

## Next steps {#63b6db6cb571489c86b3ae89051f1a4f}


Well done! You've built your first prompt in Langflow. 🎉


By dragging Langflow components to your workspace, you can create all sorts of interesting behaviors. Here are a couple of examples:

- [Memory Chatbot](https://docs.langflow.org/starter-projects/memory-chatbot)
- [Blog Writer](https://docs.langflow.org/starter-projects/blog-writer)
- [Document QA](https://docs.langflow.org/starter-projects/document-qa)
