from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
from slack_bolt.async_app import AsyncApp

from langflow.utils.slack import get_slack_flows_info

app = AsyncApp()
app_handler = AsyncSlackRequestHandler(app)


@app.event("app_mention")
async def handle_app_mentions(body, say, logger):
    text = body.get("event", {}).get("text", "")
    if "list flows" in text:
        flows_info = await get_slack_flows_info()  # Implement this function
        await say(flows_info)
    else:
        await say("Use 'list flows' to see available flows.")


@app.event("message")
async def handle_message(body, say, logger):
    text = body.get("event", {}).get("text", "")
    if "run flow" in text:
        flow_id, inputs = parse_command(text)  # Implement this function
        run_result = await run_flow(flow_id, inputs)  # Implement this function
        await say(run_result)


@app.command("/list_flows")
async def list_flows(ack, say):
    ack()
    flows_info = await get_slack_flows_info()
    # Flows info is a dictionary of flow_id: flow_info
    formatted_flows_message = "\n".join(
        [f"{flow_id}: {flow_info['name']}" for flow_id, flow_info in flows_info.items()]
    )
    await say(formatted_flows_message)
