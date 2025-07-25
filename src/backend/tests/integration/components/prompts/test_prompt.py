from lfx.components.processing import PromptComponent
from lfx.schema.message import Message
from tests.integration.utils import pyleak_marker, run_single_component

pytestmark = pyleak_marker()


async def test():
    outputs = await run_single_component(PromptComponent, inputs={"template": "test {var1}", "var1": "from the var"})
    assert isinstance(outputs["prompt"], Message)
    assert outputs["prompt"].text == "test from the var"
