from langchain.agents.tools import Tool
from langchain.tools.base import BaseTool
from langchain.llms.base import BaseLLM


def get_csv_loader(llm: BaseLLM, csv_file: str) -> BaseTool:
    """Get the CSV Loader."""
    from langchain.agents import create_csv_agent

    agent = create_csv_agent(llm=llm, path=csv_file)

    return Tool(
        name="CSV Loader",
        description="Useful for interacting with CSV files.",
        func=agent.run,
    )
