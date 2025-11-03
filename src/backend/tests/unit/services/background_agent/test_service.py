"""Tests for background agent service."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlmodel import select

from langflow.services.background_agent.service import BackgroundAgentService
from langflow.services.database.models.background_agent import (
    AgentStatus,
    BackgroundAgent,
    BackgroundAgentExecution,
    TriggerType,
)
from langflow.services.database.models.flow import Flow
from langflow.services.database.models.user import User
from langflow.services.deps import get_settings_service, session_scope


@pytest.fixture
async def test_user():
    """Create a test user."""
    async with session_scope() as session:
        user = User(
            id=uuid4(),
            username=f"test_user_{uuid4().hex[:8]}",
            password="test_password",
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


@pytest.fixture
async def test_flow(test_user):
    """Create a test flow."""
    async with session_scope() as session:
        flow = Flow(
            id=uuid4(),
            name=f"test_flow_{uuid4().hex[:8]}",
            data={"nodes": [], "edges": []},
            user_id=test_user.id,
        )
        session.add(flow)
        await session.commit()
        await session.refresh(flow)
        return flow


@pytest.fixture
async def background_agent_service():
    """Create a background agent service."""
    settings_service = get_settings_service()
    service = BackgroundAgentService(settings_service)
    service.start()
    yield service
    await service.stop()


@pytest.fixture
async def test_agent(test_user, test_flow):
    """Create a test background agent."""
    async with session_scope() as session:
        agent = BackgroundAgent(
            id=uuid4(),
            name=f"test_agent_{uuid4().hex[:8]}",
            description="Test agent",
            flow_id=test_flow.id,
            user_id=test_user.id,
            trigger_type=TriggerType.INTERVAL,
            trigger_config={"minutes": 5},
            input_config={"input_value": "test"},
            status=AgentStatus.STOPPED,
            enabled=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(agent)
        await session.commit()
        await session.refresh(agent)
        return agent


@pytest.mark.asyncio
async def test_service_initialization(background_agent_service):
    """Test background agent service initialization."""
    assert background_agent_service is not None
    assert background_agent_service.scheduler is not None
    assert background_agent_service._started is True


@pytest.mark.asyncio
async def test_start_agent(background_agent_service, test_agent):
    """Test starting a background agent."""
    result = await background_agent_service.start_agent(test_agent.id)

    assert result["status"] == "started"
    assert result["agent_id"] == str(test_agent.id)

    # Verify agent status in database
    async with session_scope() as session:
        agent = await session.get(BackgroundAgent, test_agent.id)
        assert agent.status == AgentStatus.ACTIVE


@pytest.mark.asyncio
async def test_stop_agent(background_agent_service, test_agent):
    """Test stopping a background agent."""
    # First start the agent
    await background_agent_service.start_agent(test_agent.id)

    # Then stop it
    result = await background_agent_service.stop_agent(test_agent.id)

    assert result["status"] == "stopped"
    assert result["agent_id"] == str(test_agent.id)

    # Verify agent status in database
    async with session_scope() as session:
        agent = await session.get(BackgroundAgent, test_agent.id)
        assert agent.status == AgentStatus.STOPPED


@pytest.mark.asyncio
async def test_pause_resume_agent(background_agent_service, test_agent):
    """Test pausing and resuming a background agent."""
    # Start the agent
    await background_agent_service.start_agent(test_agent.id)

    # Pause it
    result = await background_agent_service.pause_agent(test_agent.id)
    assert result["status"] == "paused"

    async with session_scope() as session:
        agent = await session.get(BackgroundAgent, test_agent.id)
        assert agent.status == AgentStatus.PAUSED

    # Resume it
    result = await background_agent_service.resume_agent(test_agent.id)
    assert result["status"] == "active"

    async with session_scope() as session:
        agent = await session.get(BackgroundAgent, test_agent.id)
        assert agent.status == AgentStatus.ACTIVE


@pytest.mark.asyncio
async def test_trigger_agent(background_agent_service, test_agent):
    """Test manually triggering an agent."""
    result = await background_agent_service.trigger_agent(test_agent.id, trigger_source="manual")

    assert result["status"] == "triggered"
    assert result["agent_id"] == str(test_agent.id)
    assert "execution_id" in result


@pytest.mark.asyncio
async def test_get_agent_status(background_agent_service, test_agent):
    """Test getting agent status."""
    result = await background_agent_service.get_agent_status(test_agent.id)

    assert result["agent_id"] == str(test_agent.id)
    assert result["name"] == test_agent.name
    assert result["status"] == test_agent.status.value
    assert result["enabled"] == test_agent.enabled
    assert result["trigger_type"] == test_agent.trigger_type.value


@pytest.mark.asyncio
async def test_get_agent_executions(background_agent_service, test_agent):
    """Test getting agent execution history."""
    # Create a test execution
    async with session_scope() as session:
        execution = BackgroundAgentExecution(
            agent_id=test_agent.id,
            trigger_source="test",
            status="SUCCESS",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        session.add(execution)
        await session.commit()

    # Get executions
    executions = await background_agent_service.get_agent_executions(test_agent.id, limit=10)

    assert len(executions) > 0
    assert executions[0]["status"] == "SUCCESS"
    assert executions[0]["trigger_source"] == "test"


@pytest.mark.asyncio
async def test_create_cron_trigger(background_agent_service):
    """Test creating a cron trigger."""
    trigger_config = {
        "minute": "0",
        "hour": "*/2",
        "day": "*",
        "month": "*",
        "day_of_week": "*",
    }

    trigger = background_agent_service._create_trigger(TriggerType.CRON, trigger_config)

    assert trigger is not None
    # Verify it's a CronTrigger
    assert trigger.__class__.__name__ == "CronTrigger"


@pytest.mark.asyncio
async def test_create_interval_trigger(background_agent_service):
    """Test creating an interval trigger."""
    trigger_config = {
        "minutes": 5,
        "seconds": 0,
    }

    trigger = background_agent_service._create_trigger(TriggerType.INTERVAL, trigger_config)

    assert trigger is not None
    # Verify it's an IntervalTrigger
    assert trigger.__class__.__name__ == "IntervalTrigger"


@pytest.mark.asyncio
async def test_create_date_trigger(background_agent_service):
    """Test creating a date trigger."""
    run_date = datetime.now(timezone.utc)
    trigger_config = {
        "run_date": run_date,
    }

    trigger = background_agent_service._create_trigger(TriggerType.DATE, trigger_config)

    assert trigger is not None
    # Verify it's a DateTrigger
    assert trigger.__class__.__name__ == "DateTrigger"


@pytest.mark.asyncio
async def test_webhook_trigger_returns_none(background_agent_service):
    """Test that webhook triggers return None (no scheduling needed)."""
    trigger = background_agent_service._create_trigger(TriggerType.WEBHOOK, {})
    assert trigger is None


@pytest.mark.asyncio
async def test_agent_not_found_error(background_agent_service):
    """Test error handling when agent is not found."""
    fake_id = uuid4()

    with pytest.raises(ValueError, match="Agent .* not found"):
        await background_agent_service.start_agent(fake_id)


@pytest.mark.asyncio
async def test_service_stop(background_agent_service):
    """Test stopping the service."""
    await background_agent_service.stop()

    assert background_agent_service._started is False
    assert background_agent_service.scheduler is None
