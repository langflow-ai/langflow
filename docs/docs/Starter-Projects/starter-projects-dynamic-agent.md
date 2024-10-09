# Dynamic Agent

Build a **Dynamic Agent** flow for an agentic application using the CrewAI.

An **agent** uses an LLM as its "brain" to reason through tasks and select among the connected tools to complete them.

This flow uses [CrewAI](https://docs.crewai.com/) to manage a [Hierarchical crew](https://docs.crewai.com/how-to/Hierarchical/) of **Agents** as they perform a sequence of **Tasks**.

CrewAI agents have **Roles**, **Goals**, and **Backstories** that define their behavior and interactions with other agents. Agents in a Hierarchical Crew are managed by a single agent with a **Manager** role, which is connected to an **Open AI** LLM component to reason through the tasks and select the appropriate tools to complete them.

This flow is "dynamic" because it uses the **Chat input** component's text to define a CrewAI agent's Role, Goal, and Backstory. The created agent then uses the connected tools to research and complete the **Task** created from the **Chat input** component.

## Prerequisites

To use this flow, you need an [OpenAI API key](https://platform.openai.com/) and a [Search API key](https://www.searchapi.io/).

## Open Langflow and start a new project

Click **New Project**, and then select the **Dynamic Agent** project.

This opens a starter project with the necessary components to run an agentic application using CrewAI.

The **Dynamic Agent** flow consists of these components:

* The **Chat Input** component accepts user input to the chat.
* The **Prompt** component combines the user input with a user-defined prompt.
* The **OpenAI** model component sends the user input and prompt to the OpenAI API and receives a response.
* The **Chat Output** component prints the flow's output to the chat.
* The **CrewAI Agent** component is an autonomous unit programmed to perform tasks, make decisions, and communicate with other agents.
* The **Crew AI Crew** component represents a collaborative group of agents working together to achieve a set of tasks. This Crew can manage work **sequentially** or **hierarchically**.
* The **Crew AI Task** component is a specific assignment to be completed by agents.
This task can be **sequential** or **hierarchical** depending on the Crew's configuration.
* The **SearchAPI** tool performs web searches using the **SearchAPI.io** API.
* The **Yahoo Finance News Tool** component creates a tool for retrieving news from Yahoo Finance.

## Run the Dynamic Agent flow

1. Add your credentials to the OpenAI and SearchAPI components using Langflow's Global Variables:
   - Click **Settings**, then **Global Variables**.
   - Click **Add New**.
   - Name your variable and paste your API key in the **Value** field.
   - In the **Apply To Fields** field, select the field to apply this variable to.
   - Click **Save Variable**.
2. In the **Chat output** component, click ▶️ Play to start the end-to-end application flow.
   A **Chat output built successfully** message and a ✅ Check on all components indicate that the flow ran successfully.
3. Click **Playground** to start a chat session.
   You should receive a detailed, helpful answer to the question defined in the **Chat input** component.

Now that your query has completed the journey from **Chat input** to **Chat output**, you have completed the **Dynamic Agent** flow.