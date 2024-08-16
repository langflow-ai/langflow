from langflow.components.agents.CrewAIAgent import CrewAIAgentComponent
from langflow.components.agents.SequentialCrew import SequentialCrewComponent
from langflow.components.helpers.SequentialTask import SequentialTaskComponent
from langflow.components.inputs.TextInput import TextInputComponent
from langflow.components.models.OpenAIModel import OpenAIModelComponent
from langflow.components.outputs.ChatOutput import ChatOutput
from langflow.components.prompts.Prompt import PromptComponent
from langflow.components.tools.SearchAPI import SearchAPIComponent
from langflow.graph.graph.base import Graph


def sequential_tasks_agent_graph():
    llm = OpenAIModelComponent()
    search_api_tool = SearchAPIComponent()
    researcher_agent = CrewAIAgentComponent()
    text_input = TextInputComponent(_display_name="Topic")
    text_input.set(input_value="Agile")
    researcher_agent.set(
        tools=[search_api_tool.build_tool],
        llm=llm.build_model,
        role="Researcher",
        goal="Search Google to find information to complete the task.",
        backstory="Research has always been your thing. You can quickly find things on the web because of your skills.",
    )
    research_task = SequentialTaskComponent()
    document_prompt_component = PromptComponent()
    document_prompt_component.set(
        template="""Topic: {topic}

Build a document about this document.""",
        topic=text_input.text_response,
    )
    research_task.set(
        agent=researcher_agent.build_output,
        task_description=document_prompt_component.build_prompt,
        expected_output="Bullet points and small phrases about the research topic.",
    )
    editor_agent = CrewAIAgentComponent()
    editor_task = SequentialTaskComponent()
    revision_prompt_component = PromptComponent()
    revision_prompt_component.set(
        template="""Topic: {topic}

Revise this document.""",
        topic=text_input.text_response,
    )
    editor_agent.set(
        llm=llm.build_model,
        role="Editor",
        goal="You should edit the Information provided by the Researcher to make it more palatable and to not contain misleading information.",
        backstory="You are the editor of the most reputable journal in the world.",
    )
    editor_task.set(
        agent=editor_agent.build_output,
        task_description=revision_prompt_component.build_prompt,
        expected_output="Small paragraphs and bullet points with the corrected content.",
        task=research_task.build_task,
    )
    blog_prompt_component = PromptComponent()
    blog_prompt_component.set(
        template="""Topic: {topic}

Build a fun blog post about this topic.""",
        topic=text_input.text_response,
    )
    comedian_agent = CrewAIAgentComponent()
    comedian_agent.set(
        llm=llm.build_model,
        role="Comedian",
        goal="You write comedic content based on the information provided by the editor.",
        backstory="Your formal occupation is Comedian-in-Chief. You write jokes, do standup comedy and write funny articles.",
    )
    blog_task = SequentialTaskComponent()
    blog_task.set(
        agent=comedian_agent.build_output,
        task_description=blog_prompt_component.build_prompt,
        expected_output="A small blog about the topic.",
        task=editor_task.build_task,
    )
    sequential_crew_component = SequentialCrewComponent()
    sequential_crew_component.set(tasks=blog_task.build_task)
    chat_output = ChatOutput()
    chat_output.set(input_value=sequential_crew_component.build_output)

    graph = Graph(
        start=text_input,
        end=chat_output,
        flow_name="Sequential Tasks Agent",
        description="This Agent runs tasks in a predefined sequence.",
    )
    return graph
