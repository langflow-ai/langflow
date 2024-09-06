# Hierarchical Tasks Agent

Build a Hierarchical Tasks Agent flow for a multi-shot application using [CrewAI](https://docs.crewai.com/). This flow uses CrewAI to manage a Hierarchical Crew of Agents as they perform disparate tasks under the control of a Manager Agent.

Unlike the agents in the [Sequential Crew starter flow](./starter-projects-sequential-crew.md), the CrewAI agents in this flow don't just perform a task one after the other. One Agent is a Researcher that queries the Search API tool, another is an Editor that evaluates the retrieved information, and the Manager Agent oversees the Researcher and Editor Agents, using the OpenAI LLM as a brain to make decisions about how to manage the Researcher and Editor agents.

## Prerequisites

- [Langflow installed and running](/getting-started-installation)
- [OpenAI API key created](https://platform.openai.com/)
- [SearchAPI API key created](https://www.searchapi.io/)

## Open Langflow and Start a New Project

Click **New Project**, and then select the **Hierarchical Tasks Agent** project.

This opens a starter project with the necessary components to run a multi-shot application using CrewAI.

## Hierarchical Tasks Agent Flow Components

- **Chat Input**: Accepts user input to the chat
- **Prompt**: Combines user input with a user-defined prompt
- **OpenAI model**: Sends user input and prompt to the OpenAI API and receives a response
- **Chat Output**: Prints the flow's output to the chat
- **CrewAI Agent**: An autonomous unit programmed to perform tasks, make decisions, and communicate with other agents
- **Crew AI Crew**: Represents a collaborative group of agents working together to achieve a set of tasks
- **Crew AI Task**: A specific assignment to be completed by agents
- **SearchAPI tool**: Performs web searches using the SearchAPI.io API

## Run the Hierarchical Tasks Agent Flow

1. Add your credentials to the OpenAI and SearchAPI components using Langflow's Global Variables:
   - Click **Settings**, then **Global Variables**
   - Click **Add New**
   - Name your variable and paste your API key in the **Value** field
   - In the **Apply To Fields** field, select the field to apply this variable to
   - Click **Save Variable**

2. In the **Chat Output** component, click **Play** to start the end-to-end application flow.

3. Click **Playground** to view the flow's output. The default output is a concise explanatory text about Langflow.

Once your query has completed the journey from Chat Input to Chat Output, you have successfully completed the Hierarchical Tasks Agent flow.