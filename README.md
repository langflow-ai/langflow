<!-- Title -->

# ⛓️ Langflow

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
<a href="https://discord.gg/EqksyE2EX9"><img alt="Discord Server" src="https://dcbadge.vercel.app/api/server/EqksyE2EX9?compact=true&style=flat"/></a>
<a href="https://huggingface.co/spaces/Logspace/Langflow"><img src="https://huggingface.co/datasets/huggingface/badges/raw/main/open-in-hf-spaces-sm.svg" alt="HuggingFace Spaces"></a>
</p>

<a href="https://github.com/logspace-ai/langflow">
    <img width="100%" src="https://github.com/logspace-ai/langflow/blob/main/img/langflow-demo.gif?raw=true"></a>


<p>
</p>

# Table of Contents
- [⛓️ Langflow](#️-langflow)
- [Table of Contents](#table-of-contents)
- [📦 Installation](#-installation)
    - [Locally](#locally)
    - [HuggingFace Spaces](#huggingface-spaces)
- [🖥️ Command Line Interface (CLI)](#️-command-line-interface-cli)
    - [Usage](#usage)
    - [Environment Variables](#environment-variables)
- [Deployment](#deployment)
  - [Deploy Langflow on Google Cloud Platform](#deploy-langflow-on-google-cloud-platform)
  - [Deploy Langflow on Jina AI Cloud](#deploy-langflow-on-jina-ai-cloud)
      - [API Usage](#api-usage)
- [🎨 Creating Flows](#-creating-flows)
- [👋 Contributing](#-contributing)
- [📄 License](#-license)


# 📦 Installation
### <b>Locally</b>
You can install Langflow from pip:

```shell
pip install langflow
```

Next, run:

```shell
python -m langflow
```
or
```shell
langflow # or langflow --help
```

### HuggingFace Spaces
You can also check it out on [HuggingFace Spaces](https://huggingface.co/spaces/Logspace/Langflow) and run it in your browser! You can even clone it and have your own copy of Langflow to play with.

# 🖥️ Command Line Interface (CLI)

Langflow provides a command-line interface (CLI) for easy management and configuration.

### Usage

You can run the Langflow using the following command:

```shell
langflow [OPTIONS]
```

Each option is detailed below:

- `--help`: Displays all available options.
- `--host`: Defines the host to bind the server to. Can be set using the `LANGFLOW_HOST` environment variable. The default is `127.0.0.1`.
- `--workers`: Sets the number of worker processes. Can be set using the `LANGFLOW_WORKERS` environment variable. The default is `1`.
- `--timeout`: Sets the worker timeout in seconds. The default is `60`.
- `--port`: Sets the port to listen on. Can be set using the `LANGFLOW_PORT` environment variable. The default is `7860`.
- `--config`: Defines the path to the configuration file. The default is `config.yaml`.
- `--env-file`: Specifies the path to the .env file containing environment variables. The default is `.env`.
- `--log-level`: Defines the logging level. Can be set using the `LANGFLOW_LOG_LEVEL` environment variable. The default is `critical`.
- `--log-file`: Specifies the path to the log file. Can be set using the `LANGFLOW_LOG_FILE` environment variable. The default is `logs/langflow.log`.
- `--cache`: Selects the type of cache to use. Options are `InMemoryCache` and `SQLiteCache`. Can be set using the `LANGFLOW_LANGCHAIN_CACHE` environment variable. The default is `SQLiteCache`.
- `--jcloud/--no-jcloud`: Toggles the option to deploy on Jina AI Cloud. The default is `no-jcloud`.
- `--dev/--no-dev`: Toggles the development mode. The default is `no-dev`.
- `--database-url`: Sets the database URL to connect to. If not provided, a local SQLite database will be used. Can be set using the `LANGFLOW_DATABASE_URL` environment variable.
- `--path`: Specifies the path to the frontend directory containing build files. This option is for development purposes only. Can be set using the `LANGFLOW_FRONTEND_PATH` environment variable.
- `--open-browser/--no-open-browser`: Toggles the option to open the browser after starting the server. Can be set using the `LANGFLOW_OPEN_BROWSER` environment variable. The default is `open-browser`.
- `--remove-api-keys/--no-remove-api-keys`: Toggles the option to remove API keys from the projects saved in the database. Can be set using the `LANGFLOW_REMOVE_API_KEYS` environment variable. The default is `no-remove-api-keys`.
- `--install-completion [bash|zsh|fish|powershell|pwsh]`: Installs completion for the specified shell.
- `--show-completion [bash|zsh|fish|powershell|pwsh]`: Shows completion for the specified shell, allowing you to copy it or customize the installation.

### Environment Variables

You can configure many of the CLI options using environment variables. These can be exported in your operating system or added to a `.env` file and loaded using the `--env-file` option.

A sample `.env` file named `.env.example` is included with the project. Copy this file to a new file named `.env` and replace the example values with your actual settings. If you're setting values in both your OS and the `.env` file, the `.env` settings will take precedence.

# Deployment

## Deploy Langflow on Google Cloud Platform

Follow our step-by-step guide to deploy Langflow on Google Cloud Platform (GCP) using Google Cloud Shell. The guide is available in the [**Langflow in Google Cloud Platform**](GCP_DEPLOYMENT.md) document.

Alternatively, click the **"Open in Cloud Shell"** button below to launch Google Cloud Shell, clone the Langflow repository, and start an **interactive tutorial** that will guide you through the process of setting up the necessary resources and deploying Langflow on your GCP project.

[![Open in Cloud Shell](https://gstatic.com/cloudssh/images/open-btn.svg)](https://console.cloud.google.com/cloudshell/open?git_repo=https://github.com/logspace-ai/langflow&working_dir=scripts&shellonly=true&tutorial=walkthroughtutorial_spot.md)


## Deploy Langflow on [Jina AI Cloud](https://github.com/jina-ai/langchain-serve)

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

## Deploy on Railway
[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/Emy2sU?referralCode=MnPSdg)

## Deploy on Render
<a href="https://render.com/deploy?repo=https://github.com/logspace-ai/langflow/tree/main">
<img src="https://render.com/images/deploy-to-render-button.svg" alt="Deploy to Render" />
</a>

# 🎨 Creating Flows

Creating flows with Langflow is easy. Simply drag sidebar components onto the canvas and connect them together to create your pipeline. Langflow provides a range of [LangChain components](https://langchain.readthedocs.io/en/latest/reference.html) to choose from, including LLMs, prompt serializers, agents, and chains.

Explore by editing prompt parameters, link chains and agents, track an agent's thought process, and export your flow.

Once you're done, you can export your flow as a JSON file to use with LangChain.
To do so, click the "Export" button in the top right corner of the canvas, then
in Python, you can load the flow with:

```python
from langflow import load_flow_from_json

flow = load_flow_from_json("path/to/flow.json")
# Now you can use it like any chain
flow("Hey, have you heard of Langflow?")
```


# 👋 Contributing

We welcome contributions from developers of all levels to our open-source project on GitHub. If you'd like to contribute, please check our [contributing guidelines](./CONTRIBUTING.md) and help make Langflow more accessible.


Join our [Discord](https://discord.com/invite/EqksyE2EX9) server to ask questions, make suggestions and showcase your projects! 🦾

<p>
</p>

[![Star History Chart](https://api.star-history.com/svg?repos=logspace-ai/langflow&type=Timeline)](https://star-history.com/#logspace-ai/langflow&Date)


# 📄 License

Langflow is released under the MIT License. See the LICENSE file for details.
