<!-- Title -->

# ⛓️ LangFlow

~ An effortless way to experiment and prototype [LangChain](https://github.com/hwchase17/langchain) pipelines ~

<p>
<img alt="GitHub Contributors" src="https://img.shields.io/github/contributors/logspace-ai/langflow" />
<img alt="GitHub Last Commit" src="https://img.shields.io/github/last-commit/logspace-ai/langflow" />
<img alt="" src="https://img.shields.io/github/repo-size/logspace-ai/langflow" />
<img alt="GitHub Issues" src="https://img.shields.io/github/issues/logspace-ai/langflow" />
<img alt="GitHub Pull Requests" src="https://img.shields.io/github/issues-pr/logspace-ai/langflow" />
<img alt="Github License" src="https://img.shields.io/github/license/logspace-ai/langflow" />
</p>

<p>
<a href="https://discord.gg/FUhJnnJ9"><img alt="Discord Server" src="https://dcbadge.vercel.app/api/server/FUhJnnJ9?compact=true&style=flat"/></a>
<a href="https://huggingface.co/spaces/Logspace/LangFlow"><img src="https://huggingface.co/datasets/huggingface/badges/raw/main/open-in-hf-spaces-sm.svg" alt="HuggingFace Spaces"></a>
</p>

<a href="https://github.com/logspace-ai/langflow">
    <img width="100%" src="https://github.com/logspace-ai/langflow/blob/main/img/langflow-demo.gif?raw=true"></a>


<p>
</p>

## 📦 Installation
### <b>Locally</b>
You can install LangFlow from pip:

```shell
pip install langflow
```

Next, run:

```shell
python -m langflow
```
or
```shell
langflow
```

### Deploy Langflow on Google Cloud Platform

Follow our step-by-step guide to deploy Langflow on Google Cloud Platform (GCP) using Google Cloud Shell. The guide is available in the [**Langflow in Google Cloud Platform**](GCP_DEPLOYMENT.md) document.

Alternatively, click the **"Open in Cloud Shell"** button below to launch Google Cloud Shell, clone the Langflow repository, and start an **interactive tutorial** that will guide you through the process of setting up the necessary resources and deploying Langflow on your GCP project.

[![Open in Cloud Shell](https://gstatic.com/cloudssh/images/open-btn.svg)](https://console.cloud.google.com/cloudshell/open?git_repo=https://github.com/logspace-ai/langflow&working_dir=scripts&shellonly=true&tutorial=walkthroughtutorial_spot.md)


### Deploy Langflow on [Jina AI Cloud](https://github.com/jina-ai/langchain-serve)

Langflow integrates with langchain-serve to provide a one-command deployment to Jina AI Cloud.

Start by installing `langchain-serve` with

```bash
pip install -U langchain-serve
```

Then, run:

```bash
langflow --jcloud
```

```text
🎉 Langflow server successfully deployed on Jina AI Cloud 🎉
🔗 Click on the link to open the server (please allow ~1-2 minutes for the server to startup): https://<your-app>.wolf.jina.ai/
📖 Read more about managing the server: https://github.com/jina-ai/langchain-serve
```

  <details>
  <summary>Show complete (example) output</summary>

  ```text
    🚀 Deploying Langflow server on Jina AI Cloud
    ╭───────────────────────── 🎉 Flow is available! ──────────────────────────╮
    │                                                                          │
    │   ID                    langflow-e3dd8820ec                              │
    │   Gateway (Websocket)   wss://langflow-e3dd8820ec.wolf.jina.ai           │
    │   Dashboard             https://dashboard.wolf.jina.ai/flow/e3dd8820ec   │
    │                                                                          │
    ╰──────────────────────────────────────────────────────────────────────────╯
    ╭──────────────┬──────────────────────────────────────────────────────────────────────────────╮
    │ App ID       │                     langflow-e3dd8820ec                                      │
    ├──────────────┼──────────────────────────────────────────────────────────────────────────────┤
    │ Phase        │                            Serving                                           │
    ├──────────────┼──────────────────────────────────────────────────────────────────────────────┤
    │ Endpoint     │          wss://langflow-e3dd8820ec.wolf.jina.ai                              │
    ├──────────────┼──────────────────────────────────────────────────────────────────────────────┤
    │ App logs     │                  dashboards.wolf.jina.ai                                     │
    ├──────────────┼──────────────────────────────────────────────────────────────────────────────┤
    │ Swagger UI   │          https://langflow-e3dd8820ec.wolf.jina.ai/docs                       │
    ├──────────────┼──────────────────────────────────────────────────────────────────────────────┤
    │ OpenAPI JSON │        https://langflow-e3dd8820ec.wolf.jina.ai/openapi.json                 │
    ╰──────────────┴──────────────────────────────────────────────────────────────────────────────╯

    🎉 Langflow server successfully deployed on Jina AI Cloud 🎉
    🔗 Click on the link to open the server (please allow ~1-2 minutes for the server to startup): https://langflow-e3dd8820ec.wolf.jina.ai/
    📖 Read more about managing the server: https://github.com/jina-ai/langchain-serve
  ```

  </details>

#### API Usage

You can use Langflow directly on your browser, or use the API endpoints on Jina AI Cloud to interact with the server.

  <details>
  <summary>Show API usage (with python)</summary>

  ```python
import requests

BASE_API_URL = "https://langflow-e3dd8820ec.wolf.jina.ai/api/v1/predict"
FLOW_ID = "864c4f98-2e59-468b-8e13-79cd8da07468"
# You can tweak the flow by adding a tweaks dictionary
# e.g {"OpenAI-XXXXX": {"model_name": "gpt-4"}}
TWEAKS = {
  "ChatOpenAI-g4jEr": {},
  "ConversationChain-UidfJ": {}
}

def run_flow(message: str, flow_id: str, tweaks: dict = None) -> dict:
    """
    Run a flow with a given message and optional tweaks.

    :param message: The message to send to the flow
    :param flow_id: The ID of the flow to run
    :param tweaks: Optional tweaks to customize the flow
    :return: The JSON response from the flow
    """
    api_url = f"{BASE_API_URL}/{flow_id}"

    payload = {"message": message}

    if tweaks:
        payload["tweaks"] = tweaks

    response = requests.post(api_url, json=payload)
    return response.json()

# Setup any tweaks you want to apply to the flow
print(run_flow("Your message", flow_id=FLOW_ID, tweaks=TWEAKS))
  ```

  ```json
  {
    "result": "Great choice! Bangalore in the 1920s was a vibrant city with a rich cultural and political scene. Here are some suggestions for things to see and do:\n\n1. Visit the Bangalore Palace - built in 1887, this stunning palace is a perfect example of Tudor-style architecture. It was home to the Maharaja of Mysore and is now open to the public.\n\n2. Attend a performance at the Ravindra Kalakshetra - this cultural center was built in the 1920s and is still a popular venue for music and dance performances.\n\n3. Explore the neighborhoods of Basavanagudi and Malleswaram - both of these areas have retained much of their old-world charm and are great places to walk around and soak up the atmosphere.\n\n4. Check out the Bangalore Club - founded in 1868, this exclusive social club was a favorite haunt of the British expat community in the 1920s.\n\n5. Attend a meeting of the Indian National Congress - founded in 1885, the INC was a major force in the Indian independence movement and held many meetings and rallies in Bangalore in the 1920s.\n\nHope you enjoy your trip to 1920s Bangalore!"
  }
  ```

  </details>

> Read more about resource customization, cost, and management of Langflow apps on Jina AI Cloud in the **[langchain-serve](https://github.com/jina-ai/langchain-serve)** repository.


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

We welcome contributions from developers of all levels to our open-source project on GitHub. If you'd like to contribute, please check our [contributing guidelines](./CONTRIBUTING.md) and help make LangFlow more accessible.


Join our [Discord](https://discord.com/invite/EqksyE2EX9) server to ask questions, make suggestions and showcase your projects! 🦾

<p>
</p>

[![Star History Chart](https://api.star-history.com/svg?repos=logspace-ai/langflow&type=Timeline)](https://star-history.com/#logspace-ai/langflow&Date)


## 📄 License

LangFlow is released under the MIT License. See the LICENSE file for details.
