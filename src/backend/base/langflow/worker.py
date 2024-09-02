import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from langflow.services.deps import get_settings_service
from langflow.tasks.activities.flow_activities import run_flow_activity
from langflow.tasks.workflows.flow_workflows import RunFlowWorkflow


async def run_worker():
    settings_service = get_settings_service()
    TEMPORAL_SERVER_URL = settings_service.settings.temporal_server_url
    TASK_QUEUE_NAME = settings_service.settings.temporal_task_queue_name
    client = await Client.connect(TEMPORAL_SERVER_URL)

    async with Worker(
        client,
        task_queue=TASK_QUEUE_NAME,
        workflows=[RunFlowWorkflow],
        activities=[run_flow_activity],
    ):
        print("Worker started, ctrl+c to exit")
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(run_worker())
