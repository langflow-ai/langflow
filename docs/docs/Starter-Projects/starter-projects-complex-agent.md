# Complex Agent

Build a Complex Agent flow for a chatbot application using [CrewAI](https://docs.crewai.com/). This flow uses CrewAI to manage a Hierarchical Crew of Agents as they perform a sequence of Tasks.

This flow features a unique method of creating a CrewAI agent out of OpenAI prompt responses. The tool-calling agent's `Role`, `Goal`, and `Backstory` are defined by prompting OpenAI LLM with the user's query. The agent then builds a response by querying the Yahoo Finance News and Search API tools.

The Manager Agent oversees the tool-calling agent, using the OpenAI LLM as a brain to make decisions about how to manage its agents. It can answer general questions from the user, but can also call for help from the tool-calling agent if needed.

## Prerequisites

- [Langflow installed and running](/getting-started-installation)
- [OpenAI API key created](https://platform.openai.com/)
- [SearchAPI API key created](https://www.searchapi.io/)

## Open Langflow and Start a New Project

Click **New Project**, and then select the **Complex Agent** project.

This opens a starter project with the necessary components to run a chatbot application using CrewAI.

## Complex Agent Flow Components

- **Chat Input**: Accepts user input to the chat
- **Prompt**: Combines user input with a user-defined prompt
- **OpenAI model**: Sends user input and prompt to the OpenAI API and receives a response
- **Chat Output**: Prints the flow's output to the chat
- **CrewAI Agent**: An autonomous unit programmed to perform tasks, make decisions, and communicate with other agents
- **Crew AI Crew**: Represents a collaborative group of agents working together to achieve a set of tasks
- **Crew AI Task**: A specific assignment to be completed by agents
- **SearchAPI tool**: Performs web searches using the SearchAPI.io API

## Run the Complex Agent Flow

1. Add your credentials to the OpenAI and SearchAPI components using Langflow's Global Variables:
   - Click **Settings**, then **Global Variables**
   - Click **Add New**
   - Name your variable and paste your API key in the **Value** field
   - In the **Apply To Fields** field, select the field to apply this variable to
   - Click **Save Variable**

2. In the **Chat Output** component, click **Play** to start the end-to-end application flow.

3. Click **Playground** to chat with the flow.

4. Ask the bot a question. The question is passed through the Prompt component to the Hierarchical Task component, then to the Hierarchical Crew component.

Once your query has completed the journey from Chat Input to Chat Output, you have successfully completed the Complex Agent flow.