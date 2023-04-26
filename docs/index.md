# ⛓️LangFlow
<p>
    ~ A User Interface For
    <a href="https://github.com/hwchase17/langchain" target="_blank">LangChain</a> 🦜🔗 ~
</p>

<p>
<a href="https://huggingface.co/spaces/Logspace/LangFlow" target="_blank"><img src="https://huggingface.co/datasets/huggingface/badges/raw/main/open-in-hf-spaces-sm.svg" alt="HuggingFace Spaces"></a>
<img alt="GitHub Contributors" src="https://img.shields.io/github/contributors/logspace-ai/langflow" />
<img alt="GitHub Last Commit" src="https://img.shields.io/github/last-commit/logspace-ai/langflow" />
<img alt="" src="https://img.shields.io/github/repo-size/logspace-ai/langflow" />
<img alt="GitHub Issues" src="https://img.shields.io/github/issues/logspace-ai/langflow" />
<img alt="GitHub Pull Requests" src="https://img.shields.io/github/issues-pr/logspace-ai/langflow" />
<img alt="Github License" src="https://img.shields.io/github/license/logspace-ai/langflow" />
</p>

<img width="100%" src="img/langflow-demo2.gif">

LangFlow is a GUI for [LangChain](https://github.com/hwchase17/langchain){.internal-link target=_blank}, designed with [react-flow](https://github.com/wbkd/react-flow){.internal-link target=_blank} to provide an effortless way to experiment and prototype flows with drag-and-drop components and a chat box.

---
## 📦 Installation

You can install LangFlow from pip:

``` py
pip install langflow
```

Next, run:
``` py
langflow
```
---
## 🎨 Creating Flows

Creating flows with LangFlow is easy. Simply drag sidebar components onto the canvas and connect them together to create your pipeline. LangFlow provides a range of [LangChain components](https://langchain.readthedocs.io/en/latest/reference.html){.internal-link target=_blank} to choose from, including LLMs, prompt serializers, agents, and chains.

Explore by editing prompt parameters, link chains and agents, track an agent's thought process, and export your flow.

Once you're done, you can export your flow as a JSON file to use with LangChain.
To do so, click the "Export" button in the top right corner of the canvas, then
in Python, you can load the flow with:

``` py
from langflow import load_flow_from_json

flow = load_flow_from_json("path/to/flow.json")
# Now you can use it like any chain
flow("Hey, have you heard of LangFlow?")
```

---
## 🧑‍💻 Deploy Langflow on Google Cloud Platform

Follow our step-by-step guide to deploy Langflow on Google Cloud Platform (GCP) using Google Cloud Shell. The guide is available in the [**Langflow in Google Cloud Platform**](GCP_DEPLOYMENT.md) document.

Alternatively, click the **"Open in Cloud Shell"** button below to launch Google Cloud Shell, clone the Langflow repository, and start an **interactive tutorial** that will guide you through the process of setting up the necessary resources and deploying Langflow on your GCP project.

[![Open in Cloud Shell](https://gstatic.com/cloudssh/images/open-btn.svg)](https://console.cloud.google.com/cloudshell/open?git_repo=https://github.com/genome21/langflow&working_dir=scripts&shellonly=true&tutorial=walkthroughtutorial_spot.md){.internal-link target=_blank}

---
## 👋 Attention

During your process to create flows, you may notice a red asterisk <span style="color:red">*</span>,
which indicates that you must connect a component there to make your flow work.
You will be able to see the component that needs to be connected if you hover over the small circle next to the asterisk.

We welcome contributions from developers of all levels to our open-source project on [GitHub](https://github.com/logspace-ai/langflow){.internal-link target=_blank}. If you'd like to contribute, please check our [contributing](help-langflow.md){.internal-link target=_blank} guidelines and help make LangFlow more accessible.


[![Star History Chart](https://api.star-history.com/svg?repos=logspace-ai/langflow&type=Timeline)](https://star-history.com/#logspace-ai/langflow&Date){.internal-link target=_blank} 
