Agents use an LLM (Language Model) to decide which actions to take and in what order. These actions can either involve using a tool and observing its output or returning information to the user.

When used correctly, agents can be incredibly powerful. This notebook aims to demonstrate how to easily use agents through a straightforward, high-level API.

To load agents, you'll need to understand the following concepts:

* Tool: A function that performs a specific task, such as a Google search, a database lookup, a Python REPL, or other chains. Currently, the interface for a tool is expected to have a string as input and a string as output.
* LLM: The language model that powers the agent.
* Agent: The specific agent to use, identified by a string that references a supported agent class. This notebook focuses on using the standard, supported agents via the simplest, highest-level API.