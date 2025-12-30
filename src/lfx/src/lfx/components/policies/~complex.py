# from lfx.field_typing import Data
import asyncio
from lfx.custom.custom_component.component import Component
from lfx.io import IntInput, Output, HandleInput
from lfx.schema.data import Data


class CustomComponent(Component):
    display_name = "Custom Component"
    description = "Use as a template to create your own component."
    documentation: str = "https://docs.langflow.org/components-custom-components"
    icon = "code"
    name = "CustomComponent"

    inputs = [
        IntInput(
            name="userid"
        ),
        HandleInput(
            name="in_tools",
            display_name="Tools",
            input_types=["Tool"],
            is_list=True,
            required=True,
            info="These are the tools that the agent can use to help with tasks.",
        ),
    ]

    outputs = [
        Output(display_name="Output", name="output", method="build_output"),
    ]

    async def build_output(self) -> Data:
        get_user_tool = [t for t in self.in_tools if t.name == 'get_user'][0]
        get_pays_tool = [t for t in self.in_tools if t.name == 'get_user_payment_methods'][0]
        
        [user, pays] = await asyncio.gather(*[
            get_user_tool.ainvoke(input={"user_id":self.userid}),
            get_pays_tool.ainvoke(input={"user_id":self.userid})
        ])
        
        res = None
        if user and pays:
            res = {
                "user": user.content[0],
                "pays": pays.content[0]
            }
            
        data = Data(value=res)
        self.status = data
        return data
