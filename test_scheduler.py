#!/usr/bin/env python
"""Test script to debug scheduler creation."""

import asyncio

from langflow.services.database.models.flow import Flow
from langflow.services.database.models.scheduler import SchedulerCreate
from langflow.services.deps import get_scheduler_service, get_session
from sqlmodel import select


async def main():
    """Test scheduler creation."""
    print("Testing scheduler creation...")

    # Get the scheduler service
    scheduler_service = get_scheduler_service()
    print(f"Scheduler service: {scheduler_service}")

    # Get a valid flow ID from the database
    flow_id = None
    async for session in get_session():
        # Get the first flow from the database
        query = select(Flow).limit(1)
        result = await session.execute(query)
        flow = result.scalar_one_or_none()

        if flow:
            flow_id = flow.id
            print(f"Found flow: {flow.name} (ID: {flow_id})")
            break
        print("No flows found in the database. Please create a flow first.")
        return

    if not flow_id:
        print("Could not get a valid flow ID. Exiting.")
        return

    # Create a scheduler
    scheduler_create = SchedulerCreate(
        name="Test Scheduler",
        description="Test scheduler for debugging",
        flow_id=flow_id,
        cron_expression="*/5 * * * *",  # Run every 5 minutes
        enabled=True,
    )
    print(f"Created scheduler object: {scheduler_create}")

    try:
        # Get a session
        async for session in get_session():
            # Create the scheduler
            print("Creating scheduler...")
            scheduler = await scheduler_service.create_scheduler(
                session=session, scheduler=scheduler_create
            )
            print(f"Created scheduler: {scheduler}")
            break
    except Exception as e:
        print(f"Error creating scheduler: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
