from uuid import uuid4

import pytest
from langflow.services.flow.flow_runner import LangflowRunnerExperimental


@pytest.fixture
def sample_flow_dict():
    return {
        "id": str(uuid4()),  # Add required ID field
        "name": "test_flow",  # Add name field
        "data": {
            "nodes": [],
            "edges": [],
        },
    }


@pytest.fixture
def flow_runner():
    return LangflowRunnerExperimental()


@pytest.mark.asyncio
async def test_database_exists_check(flow_runner):
    """Test database exists check functionality."""
    result = await flow_runner.database_exists_check()
    assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_get_flow_dict_from_dict(flow_runner, sample_flow_dict):
    """Test loading flow from a dictionary."""
    result = await flow_runner.get_flow_dict(sample_flow_dict)
    assert result == sample_flow_dict


@pytest.mark.asyncio
async def test_get_flow_dict_invalid_input(flow_runner):
    """Test loading flow with invalid input type."""
    pattern = r"Input must be a file path .* or a JSON object .*"
    with pytest.raises(TypeError, match=pattern):
        await flow_runner.get_flow_dict(123)


@pytest.mark.asyncio
async def test_run_with_dict_input(flow_runner, sample_flow_dict):
    """Test running flow with dictionary input."""
    session_id = str(uuid4())
    input_value = "test input"

    result = await flow_runner.run(
        session_id=session_id,
        flow=sample_flow_dict,
        input_value=input_value,
    )
    assert result is not None


@pytest.mark.asyncio
async def test_run_with_different_input_types(flow_runner, sample_flow_dict):
    """Test running flow with different input and output types."""
    session_id = str(uuid4())
    test_cases = [
        ("text input", "text", "text"),
        ("chat input", "chat", "chat"),
        ("test input", "chat", "all"),  # Updated to use "all" as default output_type
    ]

    for input_value, input_type, output_type in test_cases:
        result = await flow_runner.run(
            session_id=session_id,
            flow=sample_flow_dict,
            input_value=input_value,
            input_type=input_type,
            output_type=output_type,
        )
        assert result is not None


@pytest.mark.asyncio
async def test_initialize_database(flow_runner):
    """Test database initialization."""
    flow_runner.should_initialize_db = True
    await flow_runner.init_db_if_needed()
    assert not flow_runner.should_initialize_db
