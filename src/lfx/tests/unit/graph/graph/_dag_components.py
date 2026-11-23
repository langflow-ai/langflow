"""Real materialized component fixtures, isolated from the regression files."""

from lfx.custom.custom_component.component import Component
from lfx.graph import Graph
from lfx.io import HandleInput, Output
from lfx.schema.message import Message


class StaticNode(Component):
    supports_dependency_ready_scheduling = True
    inputs = [HandleInput(name="messages", input_types=["Message"], is_list=True)]
    outputs = [Output(name="message", method="message_response")]

    async def message_response(self) -> Message:
        return Message(text="".join(message.text for message in (self.messages or [])))


class InheritedNode(StaticNode):
    pass


def connected(node_class=StaticNode):
    source, target = node_class(_id="source"), node_class(_id="target")
    target.set(messages=[source.message_response])
    return Graph(source, target)


def branched():
    source, slow, fast, child, merge = [StaticNode(_id=key) for key in ("source", "slow", "fast", "child", "merge")]
    slow.set(messages=[source.message_response])
    fast.set(messages=[source.message_response])
    child.set(messages=[fast.message_response])
    merge.set(messages=[slow.message_response, child.message_response])
    return Graph(source, merge)


class ThreadNode(Component):
    supports_dependency_ready_scheduling = True
    inputs = []
    outputs = [Output(name="message", method="message_response")]

    def message_response(self) -> Message:
        self._entered.set()
        self._release.wait()
        self._finished.set()
        return Message(text="thread-value")


class IteratorNode(Component):
    supports_dependency_ready_scheduling = True
    inputs = []
    outputs = [Output(name="message", method="message_response", types=["Message"])]

    async def message_response(self) -> Message:
        async def tokens():
            yield "unsupported"

        return Message(text=tokens())
