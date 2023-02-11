from langchain.chains import ConversationChain
from langchain.chains.conversation.memory import ConversationBufferMemory
from langchain.agents import Agent, ConversationalAgent, Tool, initialize_agent


class Dictable(object):
    """A mixin that allows an object to be converted to and from a dict"""

    @classmethod
    def from_dict(cls, d):
        """Convert a dict to an object"""
        return cls(**d)

    def to_dict(self):
        return self.__dict__


class DictableChain(Dictable, ConversationChain):
    """A ConversationChain that is also Dictable"""

    pass


class DictableMemory(Dictable, ConversationBufferMemory):
    """A ConversationBufferMemory that is also Dictable"""

    pass


class DictableAgent(Dictable, Agent):
    """An Agent that is also Dictable"""

    pass


class DictableConversationalAgent(Dictable, ConversationalAgent):
    """A ConversationalAgent that is also Dictable"""

    pass


class DictableTool(Dictable, Tool):
    """A Tool that is also Dictable"""

    pass
