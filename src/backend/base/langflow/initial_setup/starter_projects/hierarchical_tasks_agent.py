from langflow.components.crewai.crewai import CrewAIAgentComponent
from langflow.components.crewai.hierarchical_crew import HierarchicalCrewComponent
from langflow.components.crewai.hierarchical_task import HierarchicalTaskComponent
from langflow.components.input_output import ChatInput, ChatOutput
from langflow.components.languagemodels import OpenAIModelComponent
from langflow.components.prompts import PromptComponent
from langflow.components.tools import SearchAPIComponent
from langflow.graph import Graph


def hierarchical_tasks_agent_graph():
    llm = OpenAIModelComponent(model_name="gpt-4o-mini")
    manager_llm = OpenAIModelComponent(model_name="gpt-4o")
    search_api_tool = SearchAPIComponent()
    researcher_agent = CrewAIAgentComponent()
    chat_input = ChatInput()
    researcher_agent.set(
        tools=[search_api_tool.build_tool],
        llm=llm.build_model,
        role="Researcher",
        goal="Search for information about the User's query and answer as best as you can",
        backstory="You are a reliable researcher and journalist ",
    )

    editor_agent = CrewAIAgentComponent()

    editor_agent.set(
        llm=llm.build_model,
        role="Editor",
        goal="Evaluate the information for misleading or biased data.",
        backstory="You are a reliable researcher and journalist ",
    )

    response_prompt = PromptComponent()
    response_prompt.set(
        template="""User's query:
{query}

Respond to the user with as much as information as you can about the topic. Delete if needed.
If it is just a general query (e.g a greeting) you can respond them directly.""",
        query=chat_input.message_response,
    )
    manager_agent = CrewAIAgentComponent()
    manager_agent.set(
        llm=manager_llm.build_model,
        role="Manager",
        goal="You can answer general questions from the User and may call others for help if needed.",
        backstory="You are polite and helpful. You've always been a beacon of politeness.",
    )
    task = HierarchicalTaskComponent()
    task.set(
        task_description=response_prompt.build_prompt,
        expected_output="Succinct response that answers the User's query.",
    )
    crew_component = HierarchicalCrewComponent()
    crew_component.set(
        tasks=task.build_task,
        agents=[researcher_agent.build_output, editor_agent.build_output],
        manager_agent=manager_agent.build_output,
    )
    chat_output = ChatOutput()
    chat_output.set(input_value=crew_component.build_output)

    return Graph(
        start=chat_input,
        end=chat_output,
        flow_name="Sequential Tasks Agent",
        description="This Agent runs tasks in a predefined sequence.",
    )
