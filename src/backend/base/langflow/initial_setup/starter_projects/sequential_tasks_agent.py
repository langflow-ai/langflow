from lfx.components.crewai.sequential_crew import SequentialCrewComponent
from lfx.components.crewai.sequential_task_agent import SequentialTaskAgentComponent
from lfx.components.input_output import ChatOutput, TextInputComponent
from lfx.components.openai.openai_chat_model import OpenAIModelComponent
from lfx.components.processing import PromptComponent
from lfx.components.tools import SearchAPIComponent
from lfx.graph import Graph


def sequential_tasks_agent_graph():
    llm = OpenAIModelComponent()
    search_api_tool = SearchAPIComponent()

    text_input = TextInputComponent(_display_name="Topic")
    text_input.set(input_value="Agile")

    # Document Prompt for Researcher
    document_prompt_component = PromptComponent()
    document_prompt_component.set(
        template="""Topic: {topic}

Build a document about this topic.""",
        topic=text_input.text_response,
    )

    # Researcher Task Agent
    researcher_task_agent = SequentialTaskAgentComponent()
    researcher_task_agent.set(
        role="Researcher",
        goal="Search Google to find information to complete the task.",
        backstory="Research has always been your thing. You can quickly find things on the web because of your skills.",
        tools=[search_api_tool.build_tool],
        llm=llm.build_model,
        task_description=document_prompt_component.build_prompt,
        expected_output="Bullet points and small phrases about the research topic.",
    )

    # Revision Prompt for Editor
    revision_prompt_component = PromptComponent()
    revision_prompt_component.set(
        template="""Topic: {topic}

Revise this document.""",
        topic=text_input.text_response,
    )

    # Editor Task Agent
    editor_task_agent = SequentialTaskAgentComponent()
    editor_task_agent.set(
        role="Editor",
        goal="You should edit the information provided by the Researcher to make it more palatable and to not contain "
        "misleading information.",
        backstory="You are the editor of the most reputable journal in the world.",
        llm=llm.build_model,
        task_description=revision_prompt_component.build_prompt,
        expected_output="Small paragraphs and bullet points with the corrected content.",
        previous_task=researcher_task_agent.build_agent_and_task,
    )

    # Blog Prompt for Comedian
    blog_prompt_component = PromptComponent()
    blog_prompt_component.set(
        template="""Topic: {topic}

Build a fun blog post about this topic.""",
        topic=text_input.text_response,
    )

    # Comedian Task Agent
    comedian_task_agent = SequentialTaskAgentComponent()
    comedian_task_agent.set(
        role="Comedian",
        goal="You write comedic content based on the information provided by the editor.",
        backstory="Your formal occupation is Comedian-in-Chief. "
        "You write jokes, do standup comedy, and write funny articles.",
        llm=llm.build_model,
        task_description=blog_prompt_component.build_prompt,
        expected_output="A small blog about the topic.",
        previous_task=editor_task_agent.build_agent_and_task,
    )

    crew_component = SequentialCrewComponent()
    crew_component.set(
        tasks=comedian_task_agent.build_agent_and_task,
    )

    # Set up the output component
    chat_output = ChatOutput()
    chat_output.set(input_value=crew_component.build_output)

    # Create the graph
    return Graph(
        start=text_input,
        end=chat_output,
        flow_name="Sequential Tasks Agent",
        description="This Agent runs tasks in a predefined sequence.",
    )
