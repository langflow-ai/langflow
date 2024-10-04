# Sequential Tasks Agent

Build a Sequential Tasks Agent flow for a multi-shot application using [CrewAI](https://docs.crewai.com/). This flow uses CrewAI to manage a Crew of Agents as they perform a sequence of Tasks.

## Prerequisites

- [Langflow installed and running](/getting-started-installation)
- [OpenAI API key created](https://platform.openai.com/)
- [SearchAPI API key created](https://www.searchapi.io/)

## Open Langflow and Start a New Project

Click **New Project**, and then select the **Sequential Tasks Agent** project.

This opens a starter project with the necessary components to run a multi-shot application using CrewAI.

## Sequential Tasks Agent Flow Components

- **Text Input**: Accepts text input
- **Prompt**: Combines user input with a user-defined prompt
- **OpenAI model**: Sends user input and prompt to the OpenAI API and receives a response
- **Chat Output**: Prints the flow's output to the chat
- **CrewAI Agent**: An autonomous unit programmed to perform tasks, make decisions, and communicate with other agents
- **Crew AI Crew**: Represents a collaborative group of agents working together to achieve a set of tasks
- **Crew AI Task**: A specific assignment to be completed by agents
- **SearchAPI tool**: Performs web searches using the SearchAPI.io API

## Run the Sequential Tasks Agent Flow

1. Add your credentials to the OpenAI and SearchAPI components using Langflow's Global Variables:
   - Click **Settings**, then **Global Variables**
   - Click **Add New**
   - Name your variable and paste your API key in the **Value** field
   - In the **Apply To Fields** field, select the field to apply this variable to
   - Click **Save Variable**

2. In the **Chat Output** component, click **Play** to start the end-to-end application flow.

3. Click **Playground** to view the flow's output. The default output is a short, comedic blog post about Agile methodology.

Once your query has completed the journey from Text Input to Chat Output, you have successfully completed the Sequential Tasks Agent flow.