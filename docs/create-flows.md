# Creating Flows

Creating flows with LangFlow is easy. Simply drag sidebar components onto the canvas and connect them together to create your pipeline. LangFlow provides a range of [LangChain components](https://langchain.readthedocs.io/en/latest/reference.html){.internal-link target=\_blank} to choose from, including LLMs, prompt serializers, agents, and chains.

<br>

Explore by editing prompt parameters, link chains and agents, track an agent's thought process, and export your flow.

<br>

Once you're done, you can export your flow as a JSON file to use with LangChain.
To do so, click the "Export" button in the top right corner of the canvas, then
in Python, you can load the flow with:

```py
from langflow import load_flow_from_json

flow = load_flow_from_json("path/to/flow.json")
# Now you can use it like any chain
flow("Hey, have you heard of LangFlow?")
```
