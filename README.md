<!-- markdownlint-disable MD030 -->

# ⛓️ Langflow

<h3>Discover a simpler & smarter way to build around Foundation Models</h3>

[![Release Notes](https://img.shields.io/github/release/logspace-ai/langflow)](https://github.com/logspace-ai/langflow/releases)
[![Contributors](https://img.shields.io/github/contributors/logspace-ai/langflow)](https://github.com/logspace-ai/langflow/contributors)
[![Last Commit](https://img.shields.io/github/last-commit/logspace-ai/langflow)](https://github.com/logspace-ai/langflow/last-commit)
[![Open Issues](https://img.shields.io/github/issues-raw/logspace-ai/langflow)](https://github.com/logspace-ai/langflow/issues)
[![LRepo-size](https://img.shields.io/github/repo-size/logspace-ai/langflow)](https://github.com/logspace-ai/langflow/repo-size)
[![Open in Dev Containers](https://img.shields.io/static/v1?label=Dev%20Containers&message=Open&color=blue&logo=visualstudiocode)](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/logspace-ai/langflow)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![GitHub star chart](https://img.shields.io/github/stars/logspace-ai/langflow?style=social)](https://star-history.com/#logspace-ai/langflow)
[![GitHub fork](https://img.shields.io/github/forks/logspace-ai/langflow?style=social)](https://github.com/logspace-ai/langflow/fork)
[![Twitter](https://img.shields.io/twitter/url/https/twitter.com/langflow_ai.svg?style=social&label=Follow%20%40langflow_ai)](https://twitter.com/langflow_ai)
[![](https://dcbadge.vercel.app/api/server/EqksyE2EX9?compact=true&style=flat)](https://discord.com/invite/EqksyE2EX9)
[![HuggingFace Spaces](https://huggingface.co/datasets/huggingface/badges/raw/main/open-in-hf-spaces-sm.svg)](https://huggingface.co/spaces/Logspace/Langflow)
[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/logspace-ai/langflow)

The easiest way to create and customize your flow

<a href="https://github.com/logspace-ai/langflow">
<img width="100%" src="https://github.com/logspace-ai/langflow/blob/dev/docs/static/img/new_langflow_demo.gif"></a>

# 📦 Installation

### <b>Locally</b>

You can install Langflow from pip:

```shell
# This installs the package without dependencies for local models
pip install langflow
```

To use local models (e.g llama-cpp-python) run:

```shell
pip install langflow[local]
```

This will install the following dependencies:

- [CTransformers](https://github.com/marella/ctransformers)
- [llama-cpp-python](https://github.com/abetlen/llama-cpp-python)
- [sentence-transformers](https://github.com/UKPLab/sentence-transformers)

You can still use models from projects like LocalAI, Ollama, LM Studio, Jan and others.

Next, run:

```shell
python -m langflow
```

or

```shell
langflow run # or langflow --help
```

### HuggingFace Spaces

You can also check it out on [HuggingFace Spaces](https://huggingface.co/spaces/Logspace/Langflow) and run it in your browser! You can even clone it and have your own copy of Langflow to play with.

# 🖥️ Command Line Interface (CLI)

Langflow provides a command-line interface (CLI) for easy management and configuration.

## Usage

You can run the Langflow using the following command:

```shell
langflow run [OPTIONS]
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
- `--components-path`: Specifies the path to the directory containing custom components. Can be set using the `LANGFLOW_COMPONENTS_PATH` environment variable. The default is `langflow/components`.
- `--log-file`: Specifies the path to the log file. Can be set using the `LANGFLOW_LOG_FILE` environment variable. The default is `logs/langflow.log`.
- `--cache`: Selects the type of cache to use. Options are `InMemoryCache` and `SQLiteCache`. Can be set using the `LANGFLOW_LANGCHAIN_CACHE` environment variable. The default is `SQLiteCache`.
- `--dev/--no-dev`: Toggles the development mode. The default is `no-dev`.
- `--path`: Specifies the path to the frontend directory containing build files. This option is for development purposes only. Can be set using the `LANGFLOW_FRONTEND_PATH` environment variable.
- `--open-browser/--no-open-browser`: Toggles the option to open the browser after starting the server. Can be set using the `LANGFLOW_OPEN_BROWSER` environment variable. The default is `open-browser`.
- `--remove-api-keys/--no-remove-api-keys`: Toggles the option to remove API keys from the projects saved in the database. Can be set using the `LANGFLOW_REMOVE_API_KEYS` environment variable. The default is `no-remove-api-keys`.
- `--install-completion [bash|zsh|fish|powershell|pwsh]`: Installs completion for the specified shell.
- `--show-completion [bash|zsh|fish|powershell|pwsh]`: Shows completion for the specified shell, allowing you to copy it or customize the installation.
- `--backend-only`: This parameter, with a default value of `False`, allows running only the backend server without the frontend. It can also be set using the `LANGFLOW_BACKEND_ONLY` environment variable.
- `--store`: This parameter, with a default value of `True`, enables the store features, use `--no-store` to deactivate it. It can be configured using the `LANGFLOW_STORE` environment variable.

These parameters are important for users who need to customize the behavior of Langflow, especially in development or specialized deployment scenarios.

### Environment Variables

You can configure many of the CLI options using environment variables. These can be exported in your operating system or added to a `.env` file and loaded using the `--env-file` option.

A sample `.env` file named `.env.example` is included with the project. Copy this file to a new file named `.env` and replace the example values with your actual settings. If you're setting values in both your OS and the `.env` file, the `.env` settings will take precedence.

# Deployment

## Deploy Langflow on Google Cloud Platform

Follow our step-by-step guide to deploy Langflow on Google Cloud Platform (GCP) using Google Cloud Shell. The guide is available in the [**Langflow in Google Cloud Platform**](GCP_DEPLOYMENT.md) document.

Alternatively, click the **"Open in Cloud Shell"** button below to launch Google Cloud Shell, clone the Langflow repository, and start an **interactive tutorial** that will guide you through the process of setting up the necessary resources and deploying Langflow on your GCP project.

[![Open in Cloud Shell](https://gstatic.com/cloudssh/images/open-btn.svg)](https://console.cloud.google.com/cloudshell/open?git_repo=https://github.com/logspace-ai/langflow&working_dir=scripts/gcp&shellonly=true&tutorial=walkthroughtutorial_spot.md)

## Deploy on Railway

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/JMXEWp?referralCode=MnPSdg)

## Deploy on Render

<a href="https://render.com/deploy?repo=https://github.com/logspace-ai/langflow/tree/main">
<img src="https://render.com/images/deploy-to-render-button.svg" alt="Deploy to Render" />
</a>

# 🎨 Creating Flows

Creating flows with Langflow is easy. Simply drag components from the sidebar onto the canvas and connect them to start building your application.

Explore by editing prompt parameters, grouping components into a single high-level component, and building your own Custom Components.

Once you’re done, you can export your flow as a JSON file.

Load the flow with:

```python
from langflow import load_flow_from_json

flow = load_flow_from_json("path/to/flow.json")
# Now you can use it
flow("Hey, have you heard of Langflow?")
```

# 👋 Contributing

We welcome contributions from developers of all levels to our open-source project on GitHub. If you'd like to contribute, please check our [contributing guidelines](./CONTRIBUTING.md) and help make Langflow more accessible.

Join our [Discord](https://discord.com/invite/EqksyE2EX9) server to ask questions, make suggestions, and showcase your projects! 🦾

---

[![Star History Chart](https://api.star-history.com/svg?repos=logspace-ai/langflow&type=Timeline)](https://star-history.com/#logspace-ai/langflow&Date)

# 🌟 Contributors

[![langflow contributors](https://contrib.rocks/image?repo=logspace-ai/langflow)](https://github.com/logspace-ai/langflow/graphs/contributors)

# 📄 License

Langflow is released under the MIT License. See the LICENSE file for details.
