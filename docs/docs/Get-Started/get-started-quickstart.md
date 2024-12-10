---
title: Quickstart
sidebar_position: 2
slug: /get-started-quickstart
---



## Prerequisites {#b5f154a3a1d242c7bdf57acf0a552732}


* [Python 3.10 to 3.12](https://www.python.org/downloads/release/python-3100/) installed
* [pip](https://pypi.org/project/pip/), [uv](https://docs.astral.sh/uv/getting-started/installation/), or [pipx](https://pipx.pypa.io/stable/installation/) installed
* Before installing Langflow, we recommend creating a virtual environment to isolate your Python dependencies with [venv](https://docs.python.org/3/library/venv.html), [uv](https://docs.astral.sh/uv/pip/environments), or [conda](https://anaconda.org/anaconda/conda)

## Create the basic prompting flow


1. From the Langflow dashboard, click **New Flow**.


2. Select **Basic Prompting**.


3. The **Basic Prompting** flow is created.


![](/img/starter-flow-basic-prompting.png)


This flow allows you to chat with the **OpenAI** component through the **Prompt** component.

4. To examine the flow's **Prompt** component, click on the **Template** field of the **Prompt** component.

```plain
Answer the user as if you were a pirate.

User: {user_input}

Answer:
```

The **Template** instructs the LLM to accept `{user_input}` and `Answer the user as if you were a pirate.`.

5. To create an environment variable for the **OpenAI** component, in the **OpenAI API Key** field, click the **Globe** button, and then click **Add New Variable**.

	1. In the **Variable Name** field, enter `openai_api_key`.
	2. In the **Value** field, paste your OpenAI API Key (`sk-...`).
	3. Click **Save Variable**.


## Run the Basic Prompting flow {#ef0e8283bfb646f99bbb825462d8cbab}

1. To open the **Playground** pane, click **Playground**.
This is where you can interact with your AI.
2. Type a message and press Enter. The bot should respond in a markedly piratical manner!

## Modify the prompt for a different result {#dcea9df0cd51434db76717c78b1e9a94}

1. To modify your prompt results, in the **Prompt** template, click the **Template** field. The **Edit Prompt** window opens.
2. Change `Answer the user as if you were a pirate` to a different character, perhaps `Answer the user as if you were Hermione Granger.`
3. Run the workflow again. The response will be very different.

## Next steps {#63b6db6cb571489c86b3ae89051f1a4f}


---


Well done! You've built your first prompt in Langflow. 🎉


By dragging Langflow components to your workspace, you can create all sorts of interesting behaviors. Here are a couple of examples:

- [Memory Chatbot](/starter-projects-memory-chatbot)
- [Blog Writer](/starter-projects-blog-writer)
- [Document QA](/starter-projects-document-qa)
