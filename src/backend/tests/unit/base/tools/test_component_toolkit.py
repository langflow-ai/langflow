import sqlite3
from pathlib import Path

import pytest
from lfx.base.tools.component_tool import ComponentToolkit
from lfx.components.data_source.sql_executor import SQLComponent
from lfx.components.input_output.chat_output import ChatOutput
from lfx.components.langchain_utilities import ToolCallingAgentComponent
from lfx.components.openai.openai_chat_model import OpenAIModelComponent
from lfx.components.tools.calculator import CalculatorToolComponent
from lfx.graph.graph.base import Graph
from pydantic import BaseModel

from tests.api_keys import get_openai_api_key


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
    openai_llm.set(api_key=get_openai_api_key())
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
    openai_llm.set(api_key=get_openai_api_key())
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


class TestComponentToolEventEmission:
    """Tests for event emission in component tools (tool mode logs visibility)."""

    def test_emits_build_events_with_correct_structure(self):
        """Verify build_start and build_end events are emitted with the component ID when event_manager is present."""
        import json
        from unittest.mock import MagicMock

        from lfx.events.event_manager import create_default_event_manager

        calculator_component = CalculatorToolComponent(_id="test-component-id")

        # Create a mock queue and event manager
        mock_queue = MagicMock()
        event_manager = create_default_event_manager(queue=mock_queue)
        calculator_component.set_event_manager(event_manager)

        component_toolkit = ComponentToolkit(component=calculator_component)
        component_tool = component_toolkit.get_tools()[0]

        # Invoke the tool
        component_tool.invoke(input={"expression": "2+2"})

        # Verify send_event was called (via queue.put_nowait)
        assert mock_queue.put_nowait.called

        # Find the build_end event
        build_end_calls = [
            call for call in mock_queue.put_nowait.call_args_list if b'"event": "build_end"' in call[0][0][1]
        ]
        assert len(build_end_calls) >= 1, "build_end event should be emitted"

        event_data = json.loads(build_end_calls[0][0][0][1].decode("utf-8").strip())
        assert event_data["data"]["id"] == "test-component-id"

    def test_event_includes_logs_when_component_calls_log(self):
        """Verify log events are emitted in real-time when component calls self.log() during execution."""
        import json
        from unittest.mock import MagicMock

        from lfx.base.tools.constants import TOOL_OUTPUT_NAME
        from lfx.events.event_manager import create_default_event_manager

        class LoggingCalculator(CalculatorToolComponent):
            def run_model(self):
                self.log("computing result", name="Computation Log")
                return super().run_model()

        logging_component = LoggingCalculator(_id="test-component-id")

        mock_queue = MagicMock()
        event_manager = create_default_event_manager(queue=mock_queue)
        logging_component.set_event_manager(event_manager)

        component_toolkit = ComponentToolkit(component=logging_component)
        component_tool = component_toolkit.get_tools()[0]

        component_tool.invoke(input={"expression": "3+3"})

        # Find and parse the log event
        log_calls = [call for call in mock_queue.put_nowait.call_args_list if b'"event": "log"' in call[0][0][1]]
        assert len(log_calls) >= 1, "log event should be emitted when component calls self.log()"

        event_data = json.loads(log_calls[0][0][0][1].decode("utf-8").strip())
        assert event_data["data"]["name"] == "Computation Log"
        assert event_data["data"]["component_id"] == "test-component-id"
        assert event_data["data"]["output"] == TOOL_OUTPUT_NAME

    def test_no_event_emission_without_event_manager(self):
        """Verify tool works correctly when no event_manager is set."""
        calculator_component = CalculatorToolComponent()

        # Ensure no event manager is set
        assert calculator_component.get_event_manager() is None

        component_toolkit = ComponentToolkit(component=calculator_component)
        component_tool = component_toolkit.get_tools()[0]

        # Should execute without errors
        result = component_tool.invoke(input={"expression": "5+5"})
        assert isinstance(result[0], dict)
        assert result[0]["data"]["result"] == "10"

    def test_no_log_events_when_component_does_not_call_log(self):
        """Verify no log events are emitted when component does not call self.log() during execution."""
        from unittest.mock import MagicMock

        from lfx.events.event_manager import create_default_event_manager

        calculator_component = CalculatorToolComponent(_id="test-component-id")

        mock_queue = MagicMock()
        event_manager = create_default_event_manager(queue=mock_queue)
        calculator_component.set_event_manager(event_manager)

        component_toolkit = ComponentToolkit(component=calculator_component)
        component_tool = component_toolkit.get_tools()[0]

        component_tool.invoke(input={"expression": "4*4"})

        log_calls = [call for call in mock_queue.put_nowait.call_args_list if b'"event": "log"' in call[0][0][1]]
        assert len(log_calls) == 0, "no log events should be emitted when component does not call self.log()"

    def test_build_start_and_end_events_are_emitted(self):
        """Verify both build_start and build_end events are emitted."""
        from unittest.mock import MagicMock

        from lfx.events.event_manager import create_default_event_manager

        calculator_component = CalculatorToolComponent(_id="test-component-id")

        mock_queue = MagicMock()
        event_manager = create_default_event_manager(queue=mock_queue)
        calculator_component.set_event_manager(event_manager)

        component_toolkit = ComponentToolkit(component=calculator_component)
        component_tool = component_toolkit.get_tools()[0]

        component_tool.invoke(input={"expression": "10/2"})

        # Check for build_start event
        build_start_calls = [
            call for call in mock_queue.put_nowait.call_args_list if b'"event": "build_start"' in call[0][0][1]
        ]
        assert len(build_start_calls) >= 1, "build_start event should be emitted"

        # Check for build_end event
        build_end_calls = [
            call for call in mock_queue.put_nowait.call_args_list if b'"event": "build_end"' in call[0][0][1]
        ]
        assert len(build_end_calls) >= 1, "build_end event should be emitted"


@pytest.mark.asyncio
class TestComponentToolAsyncEventEmission:
    """Tests for event emission in async component tools."""

    async def test_async_emits_build_end_event(self):
        """Verify build_end event is emitted for async tool execution."""
        import json
        from unittest.mock import MagicMock

        from lfx.base.tools.component_tool import _build_output_async_function
        from lfx.events.event_manager import create_default_event_manager

        calculator_component = CalculatorToolComponent(_id="test-async-component-id")

        mock_queue = MagicMock()
        event_manager = create_default_event_manager(queue=mock_queue)

        # Create an async version of the output method
        async def async_run_model():
            return calculator_component.run_model()

        output_func = _build_output_async_function(calculator_component, async_run_model, event_manager)

        # Set expression before calling
        calculator_component.set(expression="7+7")
        await output_func()

        # Verify build_end event was emitted
        build_end_calls = [
            call for call in mock_queue.put_nowait.call_args_list if b'"event": "build_end"' in call[0][0][1]
        ]
        assert len(build_end_calls) >= 1, "build_end event should be emitted for async execution"

        event_data = json.loads(build_end_calls[0][0][0][1].decode("utf-8").strip())
        assert event_data["data"]["id"] == "test-async-component-id"

    async def test_async_no_event_emission_without_event_manager(self):
        """Verify async tool works correctly when no event_manager is set."""
        from lfx.base.tools.component_tool import _build_output_async_function

        calculator_component = CalculatorToolComponent()

        async def async_run_model():
            return calculator_component.run_model()

        output_func = _build_output_async_function(calculator_component, async_run_model, event_manager=None)

        calculator_component.set(expression="8+8")
        result = await output_func()

        # Should return serialized result without errors
        assert result is not None


class TestComponentToolExceptionHandling:
    """Tests for exception path behaviour in component tools."""

    def test_build_end_emitted_on_exception(self):
        """Verify build_end is still emitted when the component raises, so the frontend does not get stuck."""
        from unittest.mock import MagicMock, patch

        from lfx.events.event_manager import create_default_event_manager

        calculator_component = CalculatorToolComponent(_id="test-exception-component-id")

        mock_queue = MagicMock()
        event_manager = create_default_event_manager(queue=mock_queue)
        calculator_component.set_event_manager(event_manager)

        component_toolkit = ComponentToolkit(component=calculator_component)
        component_tool = component_toolkit.get_tools()[0]

        with patch.object(CalculatorToolComponent, "run_model", side_effect=ValueError("boom")):
            # handle_tool_error=True means ToolException is caught and returned as string
            component_tool.invoke(input={"expression": "1+1"})

        build_end_calls = [
            call for call in mock_queue.put_nowait.call_args_list if b'"event": "build_end"' in call[0][0][1]
        ]
        assert len(build_end_calls) == 1, "build_end must be emitted even when the component raises"

    def test_build_start_emitted_before_exception(self):
        """Verify build_start is emitted before the exception, and both events are present."""
        from unittest.mock import MagicMock, patch

        from lfx.events.event_manager import create_default_event_manager

        calculator_component = CalculatorToolComponent(_id="test-exception-component-id")

        mock_queue = MagicMock()
        event_manager = create_default_event_manager(queue=mock_queue)
        calculator_component.set_event_manager(event_manager)

        component_toolkit = ComponentToolkit(component=calculator_component)
        component_tool = component_toolkit.get_tools()[0]

        with patch.object(CalculatorToolComponent, "run_model", side_effect=ValueError("boom")):
            # handle_tool_error=True means ToolException is caught and returned as string
            component_tool.invoke(input={"expression": "1+1"})

        all_events = [call[0][0][1] for call in mock_queue.put_nowait.call_args_list]
        event_types = [
            next(t for t in (b"build_start", b"build_end") if t in ev)
            for ev in all_events
            if b"build_start" in ev or b"build_end" in ev
        ]
        assert event_types == [b"build_start", b"build_end"], "build_start must precede build_end"


@pytest.mark.asyncio
class TestComponentToolAsyncExceptionHandling:
    """Tests for exception path behaviour in async component tools."""

    async def test_async_build_end_emitted_on_exception(self):
        """Verify build_end is emitted for async tools even when the component raises."""
        from unittest.mock import MagicMock

        from langchain_core.tools.base import ToolException
        from lfx.base.tools.component_tool import _build_output_async_function
        from lfx.events.event_manager import create_default_event_manager

        calculator_component = CalculatorToolComponent(_id="test-async-exception-id")

        mock_queue = MagicMock()
        event_manager = create_default_event_manager(queue=mock_queue)

        async def async_run_model():
            msg = "async boom"
            raise ValueError(msg)

        output_func = _build_output_async_function(calculator_component, async_run_model, event_manager)

        with pytest.raises(ToolException):
            await output_func()

        build_end_calls = [
            call for call in mock_queue.put_nowait.call_args_list if b'"event": "build_end"' in call[0][0][1]
        ]
        assert len(build_end_calls) == 1, "build_end must be emitted for async tool even when the component raises"

    async def test_sync_tool_in_executor_delivers_events(self):
        """Verify events are delivered when a sync tool runs in a thread executor (call_soon_threadsafe path)."""
        import asyncio

        from lfx.events.event_manager import create_default_event_manager

        # Use a real asyncio.Queue so call_soon_threadsafe actually enqueues items
        real_queue: asyncio.Queue = asyncio.Queue()
        # EventManager is created here, inside the running event loop, so self._loop is captured
        event_manager = create_default_event_manager(queue=real_queue)

        calculator_component = CalculatorToolComponent(_id="test-thread-executor-id")
        calculator_component.set_event_manager(event_manager)

        component_toolkit = ComponentToolkit(component=calculator_component)
        component_tool = component_toolkit.get_tools()[0]

        loop = asyncio.get_running_loop()
        # Run the sync tool from a thread — this exercises the call_soon_threadsafe branch
        await loop.run_in_executor(None, component_tool.invoke, {"expression": "3+3"})

        # Allow scheduled callbacks to run
        await asyncio.sleep(0)

        received = []
        while not real_queue.empty():
            received.append(real_queue.get_nowait())

        event_types = {item[1] for item in received}
        assert any(b'"event": "build_start"' in ev for ev in event_types), "build_start must be delivered via executor"
        assert any(b'"event": "build_end"' in ev for ev in event_types), "build_end must be delivered via executor"
