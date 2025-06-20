import os
import sqlite3
from pathlib import Path

import pytest
from langflow.base.tools.component_tool import ComponentToolkit
from langflow.components.data.sql_executor import SQLComponent
from langflow.components.input_output.chat_output import ChatOutput
from langflow.components.langchain_utilities import ToolCallingAgentComponent
from langflow.components.languagemodels import OpenAIModelComponent
from langflow.components.tools.calculator import CalculatorToolComponent
from langflow.graph.graph.base import Graph
from pydantic import BaseModel


@pytest.fixture
def test_db():
    """Fixture that creates a temporary SQLite database for testing."""
    test_data_dir = Path(__file__).parent.parent.parent.parent / "data"
    db_path = test_data_dir / "test.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # Create students table
    cursor.execute("""
    CREATE TABLE students (
        id INTEGER PRIMARY KEY,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        age INTEGER,
        gpa REAL,
        major TEXT
    )
    """)

    # Create courses table
    cursor.execute("""
    CREATE TABLE courses (
        id INTEGER PRIMARY KEY,
        course_name TEXT NOT NULL,
        instructor TEXT,
        credits INTEGER
    )
    """)

    # Create enrollment junction table
    cursor.execute("""
    CREATE TABLE enrollments (
        student_id INTEGER,
        course_id INTEGER,
        grade TEXT,
        PRIMARY KEY (student_id, course_id),
        FOREIGN KEY (student_id) REFERENCES students (id),
        FOREIGN KEY (course_id) REFERENCES courses (id)
    )
    """)

    # Insert sample student data
    students = [
        (1, "John", "Smith", 20, 3.5, "Computer Science"),
        (2, "Emma", "Johnson", 21, 3.8, "Mathematics"),
        (3, "Michael", "Williams", 19, 3.2, "Physics"),
        (4, "Olivia", "Brown", 22, 3.9, "Biology"),
        (5, "James", "Davis", 20, 3.1, "Chemistry"),
    ]

    cursor.executemany("INSERT INTO students VALUES (?, ?, ?, ?, ?, ?)", students)

    # Insert sample course data
    courses = [
        (101, "Introduction to Programming", "Dr. Jones", 3),
        (102, "Calculus I", "Dr. Smith", 4),
        (103, "Physics 101", "Dr. Brown", 4),
        (104, "Biology Fundamentals", "Dr. Wilson", 3),
        (105, "Chemistry Basics", "Dr. Miller", 3),
    ]

    cursor.executemany("INSERT INTO courses VALUES (?, ?, ?, ?)", courses)

    # Insert sample enrollment data
    enrollments = [
        (1, 101, "A"),
        (1, 102, "B+"),
        (2, 102, "A"),
        (2, 103, "A-"),
        (3, 103, "B"),
        (3, 105, "C+"),
        (4, 104, "A"),
        (5, 105, "B+"),
    ]

    cursor.executemany("INSERT INTO enrollments VALUES (?, ?, ?)", enrollments)

    # Commit changes and close connection
    conn.commit()
    conn.close()
    yield str(db_path)

    Path(db_path).unlink()


def test_component_tool():
    calculator_component = CalculatorToolComponent()
    component_toolkit = ComponentToolkit(component=calculator_component)
    component_tool = component_toolkit.get_tools()[0]
    assert component_tool.name == "run_model"
    assert issubclass(component_tool.args_schema, BaseModel)
    # TODO: fix this
    # assert component_tool.args_schema.model_json_schema()["properties"] == {
    #     "input_value": {
    #         "default": "",
    #         "description": "Message to be passed as input.",
    #         "title": "Input Value",
    #         "type": "string",
    #     },
    # }
    assert component_toolkit.component == calculator_component

    result = component_tool.invoke(input={"expression": "1+1"})
    assert isinstance(result[0], dict)
    assert "result" in result[0]["data"]
    assert result[0]["data"]["result"] == "2"


@pytest.mark.api_key_required
@pytest.mark.usefixtures("client")
async def test_component_tool_with_api_key():
    chat_output = ChatOutput()
    openai_llm = OpenAIModelComponent()
    openai_llm.set(api_key=os.environ["OPENAI_API_KEY"])
    tool_calling_agent = ToolCallingAgentComponent()
    tools = await chat_output.to_toolkit()
    tool_calling_agent.set(
        llm=openai_llm.build_model,
        tools=list(tools),
        input_value="Which tools are available? Please tell its name.",
    )

    g = Graph(start=tool_calling_agent, end=tool_calling_agent)
    g.session_id = "test"
    assert g is not None
    results = [result async for result in g.async_start()]
    assert len(results) == 3
    assert "message_response" in tool_calling_agent._outputs_map["response"].value.get_text()


@pytest.mark.api_key_required
@pytest.mark.usefixtures("client")
async def test_sql_component_to_toolkit(test_db):
    sql_component = SQLComponent()
    sql_component.set(database_url=f"sqlite:///{test_db}")
    tool = await sql_component.to_toolkit()
    openai_llm = OpenAIModelComponent()
    openai_llm.set(api_key=os.environ["OPENAI_API_KEY"])
    tool_calling_agent = ToolCallingAgentComponent()

    tool_calling_agent.set(
        llm=openai_llm.build_model,
        tools=list(tool),
        input_value="run SELECT * FROM courses to get course details.",
    )

    g = Graph(start=tool_calling_agent, end=tool_calling_agent)
    g.session_id = "test"
    assert g is not None
    results = [result async for result in g.async_start()]
    assert len(results) > 0
    assert "Physics 101" in tool_calling_agent._outputs_map["response"].value.get_text()
