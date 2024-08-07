<!-- markdownlint-disable MD030 -->

# [![Langflow](./docs/static/img/hero.png)](https://www.langflow.org)

<p align="center" style="font-size: 12px;">
    Langflow is a low-code app builder for RAG (retrieval augmented generation) and multi-agent AI applications. It’s Python-based and agnostic to any model, API, data source or database.
</p>

<p align="center" style="font-size: 12px;">
    <a href="https://docs.langflow.org" style="text-decoration: underline;">Docs</a> -
    <a href="http://langflow.datastax.com" style="text-decoration: underline;">Free Cloud Service</a> -
    <a href="https://discord.com/invite/EqksyE2EX9" style="text-decoration: underline;">Join our Discord</a> -
    <a href="https://twitter.com/langflow_ai" style="text-decoration: underline;">Follow us on X</a>
</p>

<div align="center">
  <a href="./README.md"><img alt="README in English" src="https://img.shields.io/badge/English-d9d9d9"></a>
  <a href="./README.PT.md"><img alt="README in Portuguese" src="https://img.shields.io/badge/Portuguese-d9d9d9"></a>
  <a href="./README.zh_CN.md"><img alt="README in Simplified Chinese" src="https://img.shields.io/badge/简体中文-d9d9d9"></a>
  <a href="./README.ja.md"><img alt="README in Japanese" src="https://img.shields.io/badge/日本語-d9d9d9"></a>
  <a href="./README.KR.md"><img alt="README in KOREAN" src="https://img.shields.io/badge/한국어-d9d9d9"></a>
</div>

<p align="center">

https://github.com/user-attachments/assets/a1a36011-6169-4804-87ad-cfd4c5a79872

</p>

# Core features 
1. **Open-source framework:** Python-based and agnostic to any model, API, data source, or database.
2. **Visual canvas IDE:** Intuitive drag-and-drop interface for building and running workflows.
3. **Playground:** Immediately test and iterate workflows with step-by-step control.
4. **Conditional workflows:** Build complex, Turing-complete workflows for powerful AI and RAG applications
5. **Multi-Agent capabilities:** Create AIs with multiple agents using different models working together on tasks.
6. **Cloud service:** Build, test, deploy and monitor AI applications in the cloud.
7. **Customizable Components:**  Control component execution with custom Python code.
8. **Export JSON or API Deployment:** Export as JSON or as a JavaScript or Python API  back-end service.
9. **Observability:** Real time traceability with LangSmith integration by adding LangChain API key.
10. **Enterprise-ready:** Deploy on DataStax cloud service to support enterprise security and scale
11. **Ecosystem Integrations:** Prebuilt, reusable components to connect to any model, API, data source or database.

![Integrations](https://github.com/user-attachments/assets/df4a6714-60de-4a8b-aff0-982c5aa467e3)

# Stay up-to-date

Star Langflow on GitHub to be instantly notified of new releases.

![Star Langflow](https://github.com/user-attachments/assets/03168b17-a11d-4b2a-b0f7-c1cce69e5a2c)

# 📦 Quick Start

- **Install Langflow with pip** (Python version 3.10 or greater):

// python -m pip install langflow -U

- **Cloud:** DataStax Langflow is a complete, hosted Langflow environment with zero setup. [Sign up for a free account.](http://langflow.datastax.com) 
- **Self-managed:** Run Langflow in your environment. [Install Langflow](https://docs.langflow.org/getting-started-installation) to run a local Langflow server, and then use the [Quickstart](https://docs.langflow.org/getting-started-quickstart) guide to create and execute a flow.
- **Hugging Face:** [Clone the space using this link](https://huggingface.co/spaces/Langflow/Langflow?duplicate=true) to create your own Langflow workspace in minutes.

# 🎨 Create Flows

Creating flows with Langflow is easy. Simply drag components from the sidebar onto the workspace and connect them to start building your application.

Explore by editing prompt parameters, grouping components into a single high-level component, and building your own Custom Components.

Once you’re done, you can export your flow as a JSON file.

Load the flow with:

```python
from langflow.load import run_flow_from_json

results = run_flow_from_json("path/to/flow.json", input_value="Hello, World!")
```

# Deploy

## Deploy on Google Cloud Platform

Follow our step-by-step guide to deploy Langflow on Google Cloud Platform (GCP) using Google Cloud Shell. The guide is available in the [**Langflow in Google Cloud Platform**](./docs/docs/Deployment/deployment-gcp.md) document.

Alternatively, click the **"Open in Cloud Shell"** button below to launch Google Cloud Shell, clone the Langflow repository, and start an **interactive tutorial** that will guide you through the process of setting up the necessary resources and deploying Langflow on your GCP project.

[![Open in Cloud Shell](https://gstatic.com/cloudssh/images/open-btn.svg)](https://console.cloud.google.com/cloudshell/open?git_repo=https://github.com/langflow-ai/langflow&working_dir=scripts/gcp&shellonly=true&tutorial=walkthroughtutorial_spot.md)

## Deploy on Railway

Use this template to deploy Langflow 1.0 on Railway:

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/JMXEWp?referralCode=MnPSdg)

## Deploy on Render

<a href="https://render.com/deploy?repo=https://github.com/langflow-ai/langflow/tree/main">
<img src="https://render.com/images/deploy-to-render-button.svg" alt="Deploy to Render" />
</a>

## Deploy on Kubernetes

Follow our step-by-step guide to deploy [Langflow on Kubernetes](./docs/docs/Deployment/deployment-kubernetes.md).

# 🖥️ Command Line Interface (CLI)

Langflow provides a command-line interface (CLI) for easy management and configuration.

## Usage

You can run the Langflow using the following command:

```shell
langflow run [OPTIONS]
```

For more details on the CLI options, [follow our documentation.](https://docs.langflow.org/configuration-cli)

# 👋 Contribute

We welcome contributions from developers of all levels to our open-source project on GitHub. If you'd like to contribute, please check our [contributing guidelines](./CONTRIBUTING.md) and help make Langflow more accessible.

---

[![Star History Chart](https://api.star-history.com/svg?repos=langflow-ai/langflow&type=Timeline)](https://star-history.com/#langflow-ai/langflow&Date)

# 🌟 Contributors

[![langflow contributors](https://contrib.rocks/image?repo=langflow-ai/langflow)](https://github.com/langflow-ai/langflow/graphs/contributors)

# 📄 License

Langflow is released under the MIT License. See the [LICENSE](LICENSE) file for details.
