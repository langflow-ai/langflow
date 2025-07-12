import asyncio
import json

import jinja2

from langflow.base.hil.event_lock import wait_for_hil
from langflow.custom import Component
from langflow.io import MessageTextInput, MultilineInput, Output
from langflow.schema.content_block import ContentBlock
from langflow.schema.content_types import HILContent, JSONContent
from langflow.schema.message import Data, Message


class HILComponent(Component):
    display_name = "HIL"
    description = "User Interaction Component"
    documentation: str = "https://doc.360teams.com/docs/KlkKVZ2dvBCW5lqd"
    icon = "User"
    name = "HILComponent"

    inputs = [
        MultilineInput(
            name="hil_form",
            display_name="HIL Form",
            info="formilyjs schema json",
            value="""
{
  "flow_id": "${ flow_id }",
  "run_id": "${ run_id }",
  "form_schema": {
    "type": "object",
    "properties": {
      "info": {
        "type": "string",
        "title": "Description",
        "default": "The agent wants to execute ${ input_value }, do you allow?",
        "x-read-pretty": true,
        "x-component": "Input",
        "x-decorator": "FormItem"
      },
      "agree": {
        "type": "boolean",
        "title": "Allow",
        "enum": [
            { "label": "Yes", "value": true},
            { "label": "No", "value": false}
        ],
        "default": true,
        "x-component": "Switch",
        "x-decorator": "FormItem",
        "x-validator": [{ "required": true, "message": "Please make a selection" }]
      }
    }
    }
}
            """,
            tool_mode=False,
            required=True,
        ),
        MessageTextInput(
            name="input_value",
            display_name="Input Value",
            info="This is a custom component Input",
            value="Hello, World!",
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Output", name="output", method="build_output"),
    ]

    # Keep original send_message method to prevent it from being removed in tool mode
    async def my_send_message(self, message: Message, id_: str | None = None):
        return await super().send_message(message, id_)

    async def build_output(self) -> Data:
        if hasattr(self, "graph"):
            session_id = self.graph.session_id
        elif hasattr(self, "_session_id"):
            session_id = self._session_id
        else:
            session_id = None

        self.log(self.graph.run_id, "run_id")
        run_id = self.graph.run_id
        flow_id = self.flow_id

        # 1. Variable substitution
        jinja_env = jinja2.Environment(  # noqa: S701
            variable_start_string="${", variable_end_string="}"
        )  # Changed jinja2 template engine variable syntax due to formilyjs schema using {{}} syntax
        jinja_template = jinja_env.from_string(self.hil_form)
        # TODO: dynamic input to render
        data = jinja_template.render(input_value=self.input_value, flow_id=flow_id, run_id=run_id)

        # 2. Save and return schema json to frontend using send_message
        json_content = HILContent(data=json.loads(data))
        message = await Message.create(
            text="",
            sender="hil",
            sender_name="hil",
            properties={
                "icon": "Bot",
                "state": "partial",
                "component_id": self._id,
                "component_name": self.display_name,
            },
            content_blocks=[ContentBlock(title="HIL", contents=[json_content])],
            session_id=session_id,
        )
        message = await self.my_send_message(message=message)

        # 3. Wait for HIL event
        try:
            data = await wait_for_hil(run_id)
            message.content_blocks[0].contents.append(
                JSONContent(data={"status": "success", "msg": "HIL submission successful", "data": data})
            )
            message.properties.state = "complete"
            await self.my_send_message(message=message)
            if not data.get("agree", True):  # Only for demonstrating approval-style HIL interaction
                error_msg = "User rejected"
                raise RuntimeError(error_msg)
            return Data(data=data)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            error_content = JSONContent(data={"status": "fail", "msg": "HIL timeout or cancelled"})
            message.content_blocks[0].contents.append(error_content)
            message.properties.state = "complete"
            await self.my_send_message(message=message)
            raise
