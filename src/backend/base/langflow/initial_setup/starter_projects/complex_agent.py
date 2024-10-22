from langflow.components.agents import CrewAIAgentComponent, HierarchicalCrewComponent
from langflow.components.helpers import HierarchicalTaskComponent
from langflow.components.inputs import ChatInput
from langflow.components.models import OpenAIModelComponent
from langflow.components.outputs import ChatOutput
from langflow.components.prompts import PromptComponent
from langflow.components.tools import SearchAPIComponent, YfinanceToolComponent
from langflow.graph import Graph


def complex_agent_graph():
    llm = OpenAIModelComponent(model_name="gpt-4o-mini")
    manager_llm = OpenAIModelComponent(model_name="gpt-4o")
    search_api_tool = SearchAPIComponent()
    yahoo_search_tool = YfinanceToolComponent()
    dynamic_agent = CrewAIAgentComponent()
    chat_input = ChatInput()
    role_prompt = PromptComponent(_display_name="Role Prompt")
    role_prompt.set(
        template="""Define a Role that could execute or answer well the user's query.

User's query: {query}

Role should be two words max. Something like "Researcher" or "Software Developer".
"""
    )

    goal_prompt = PromptComponent(_display_name="Goal Prompt")
    goal_prompt.set(
        template="""Define the Goal of this Role, given the User's Query.
User's query: {query}

Role: {role}

The goal should be concise and specific.
Goal:
""",
        query=chat_input.message_response,
        role=role_prompt.build_prompt,
    )
    backstory_prompt = PromptComponent(_display_name="Backstory Prompt")
    backstory_prompt.set(
        template="""Define a Backstory of this Role and Goal, given the User's Query.
User's query: {query}

Role: {role}
Goal: {goal}

The backstory should be specific and well aligned with the rest of the information.
Backstory:""",
        query=chat_input.message_response,
        role=role_prompt.build_prompt,
        goal=goal_prompt.build_prompt,
    )
    dynamic_agent.set(
        tools=[search_api_tool.build_tool, yahoo_search_tool.build_tool],
        llm=llm.build_model,
        role=role_prompt.build_prompt,
        goal=goal_prompt.build_prompt,
        backstory=backstory_prompt.build_prompt,
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
        tasks=task.build_task, agents=[dynamic_agent.build_output], manager_agent=manager_agent.build_output
    )
    chat_output = ChatOutput()
    chat_output.set(input_value=crew_component.build_output)

    return Graph(
        start=chat_input,
        end=chat_output,
        flow_name="Sequential Tasks Agent",
        description="This Agent runs tasks in a predefined sequence.",
    )
