from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp

def create_slack_app():
    app = AsyncApp()
    socket_handler = AsyncSocketModeHandler(app)

    @app.event("app_mention")
    async def handle_app_mentions(body, say, logger):
        text = body.get("event", {}).get("text", "")
        if "list flows" in text:
            flows_info = await get_slack_flows_info()  # Implement this function
            await say(flows_info)
        else:
            await say("Use 'list flows' to see available flows.")

    @app.message()
    async def handle_message(body, say, logger):
        text = body.get("event", {}).get("text", "")
        if "run flow" in text:
            flow_id, inputs = parse_command(text)  # Implement this function
            run_result = await run_flow(flow_id, inputs)  # Implement this function
            await say(run_result)

    @app.command("/run_flow")
    async def run_flow(ack, say, command, logger):
        await ack()
        await say(f"Running flow with inputs: {command}")

        try:
            flow_id, inputs = parse_command(command)
            run_result = await run_flow(flow_id, inputs)
        except Exception as e:
            await say(f"Failed to run flow: {e}")
            logger.exception(e)
            return
        await say(run_result)

    @app.command("/list_flows")
    async def list_flows(ack, say, logger):
        await ack()
        try:
            flows_info = get_slack_flows_info()
        except Exception as e:
            await say(f"Failed to get flows: {e}")
            logger.exception(e)
            return
        # Flows info is a dictionary of flow_id: flow_info
        formatted_flows_message = "\n".join(
            [
                f"{flow_id}: {flow_info['name']}"
                for flow_id, flow_info in flows_info.items()
            ]
        )
        await say(formatted_flows_message)

    return app, socket_handler
