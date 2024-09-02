from temporalio import workflow

from langflow.tasks.activities.flow_activities import run_flow_activity


@workflow.defn
class RunFlowWorkflow:
    @workflow.run
    async def run(
        self, flow: dict, input_request: dict, stream: bool = False, api_key_user: dict | None = None
    ) -> dict:
        return await workflow.execute_activity(
            run_flow_activity,
            flow,
            input_request,
            stream,
            api_key_user,
            retry_policy=workflow.RetryPolicy(maximum_attempts=3),
        )
