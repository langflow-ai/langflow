<!-- Title -->

# ⛓️ LangFlow

~ A User Interface For [LangChain](https://github.com/hwchase17/langchain) ~

<p>
<img alt="GitHub Contributors" src="https://img.shields.io/github/contributors/logspace-ai/langflow" />
<img alt="GitHub Last Commit" src="https://img.shields.io/github/last-commit/logspace-ai/langflow" />
<img alt="" src="https://img.shields.io/github/repo-size/logspace-ai/langflow" />
<img alt="GitHub Issues" src="https://img.shields.io/github/issues/logspace-ai/langflow" />
<img alt="GitHub Pull Requests" src="https://img.shields.io/github/issues-pr/logspace-ai/langflow" />
<img alt="Github License" src="https://img.shields.io/github/license/logspace-ai/langflow" />
</p>

<a href="https://github.com/logspace-ai/langflow">
    <img width="100%" src="https://github.com/logspace-ai/langflow/blob/main/img/langflow-demo.gif?raw=true"></a>

LangFlow is a GUI for [LangChain](https://github.com/hwchase17/langchain), designed with [react-flow](https://github.com/wbkd/react-flow) to provide an effortless way to experiment and prototype flows with drag-and-drop components and a chat box.

## 📦 Installation

You can install LangFlow from pip:

`pip install langflow`

Next, run:

`langflow`

## 🎨 Creating Flows

Creating flows with LangFlow is easy. Simply drag sidebar components onto the canvas and connect them together to create your pipeline. LangFlow provides a range of [LangChain components](https://langchain.readthedocs.io/en/latest/reference.html) to choose from, including LLMs, prompt serializers, agents, and chains.

Explore by editing prompt parameters, link chains and agents, track an agent's thought process, and export your flow.

Once you're done, you can export your flow as a JSON file to use with LangChain.
To do so, click the "Export" button in the top right corner of the canvas, then
in Python, you can load the flow with:

```python
from langflow import load_flow_from_json

flow = load_flow_from_json("path/to/flow.json")
# Now you can use it like any chain
flow("Hey, have you heard of LangFlow?")
```


## 👋 Contributing

We welcome contributions from developers of all levels to our open-source project on GitHub. If you'd like to contribute, please check our contributing guidelines and help make LangFlow more accessible.


[![Star History Chart](https://api.star-history.com/svg?repos=logspace-ai/langflow&type=Timeline)](https://star-history.com/#logspace-ai/langflow&Date)


## 📄 License

LangFlow is released under the MIT License. See the LICENSE file for details.
