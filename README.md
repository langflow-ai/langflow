<!-- markdownlint-disable MD030 -->

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./docs/static/img/langflow-logo-color-blue-bg.svg">
  <img src="./docs/static/img/langflow-logo-color-black-solid.svg" alt="Langflow logo">
</picture>

[![Release Notes](https://img.shields.io/github/release/langflow-ai/langflow?style=flat-square)](https://github.com/langflow-ai/langflow/releases)
[![PyPI - License](https://img.shields.io/badge/license-MIT-orange)](https://opensource.org/licenses/MIT)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/langflow?style=flat-square)](https://pypistats.org/packages/langflow)
[![Twitter](https://img.shields.io/twitter/url/https/twitter.com/langflow-ai.svg?style=social&label=Follow%20%40Langflow)](https://twitter.com/langflow_ai)
[![YouTube Channel](https://img.shields.io/youtube/channel/subscribers/UCn2bInQrjdDYKEEmbpwblLQ?label=Subscribe)](https://www.youtube.com/@Langflow)
[![Discord Server](https://img.shields.io/discord/1116803230643527710?logo=discord&style=social&label=Join)](https://discord.gg/EqksyE2EX9)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/langflow-ai/langflow)

[Langflow](https://langflow.org) is a powerful platform for building and deploying AI-powered agents and workflows. It provides developers with both a visual authoring experience and built-in API and MCP servers that turn every workflow into a tool that can be integrated into applications built on any framework or stack. Langflow comes with batteries included and supports all major LLMs, vector databases and a growing library of AI tools.

## ✨ Highlight features

- **Visual builder interface** to quickly get started and iterate.
- **Source code access** lets you customize any component using Python.
- **Interactive playground** to immediately test and refine your flows with step-by-step control.
- **Multi-agent orchestration** with conversation management and retrieval.
- **Deploy as an API** or export as JSON for Python apps.
- **Deploy as an MCP server** and turn your flows into tools for MCP clients.
- **Observability** with LangSmith, LangFuse and other integrations.
- **Enterprise-ready** security and scalability.

## 🖥️  Langflow Desktop

Langflow Desktop is the easiest way to get started with Langflow. All dependencies are included, so you don't need to manage Python environments or install packages manually.
Available for Windows and macOS.

[📥 Download Langflow Desktop](https://www.langflow.org/desktop)

## ⚡️ Quickstart

### Install locally (recommended)

Requires Python 3.10–3.13 and [uv](https://docs.astral.sh/uv/getting-started/installation/) (recommended package manager).

#### Install

From a fresh directory, run:
```shell
uv pip install langflow -U
```

The latest Langflow package is installed.
For more information, see [Install and run the Langflow OSS Python package](https://docs.langflow.org/get-started-installation#install-and-run-the-langflow-oss-python-package).

#### Run

To start Langflow, run:
```shell
uv run langflow run
```

Langflow starts at http://127.0.0.1:7860.

That's it! You're ready to build with Langflow! 🎉

## 📦 Other install options

### Run from source
If you've cloned this repository and want to contribute, run this command from the repository root:
```shell
make run_cli
```
For more information, see [DEVELOPMENT.md](./DEVELOPMENT.md).

### Docker
Start a Langflow container with default settings:
```shell
docker run -p 7860:7860 langflowai/langflow:latest
```
Langflow is available at http://localhost:7860/.
For configuration options, see the [Docker deployment guide](https://docs.langflow.org/deployment-docker).

> [!CAUTION]
> - Users must update to Langflow >= 1.7.1 to protect against [CVE-2025-68477](https://github.com/langflow-ai/langflow/security/advisories/GHSA-5993-7p27-66g5) and [CVE-2025-68478](https://github.com/langflow-ai/langflow/security/advisories/GHSA-f43r-cc68-gpx4).
> - Langflow version 1.7.0 has a critical bug where persisted state (flows, projects, and global variables) cannot be found when upgrading. Version 1.7.0 was yanked and replaced with version 1.7.1, which includes a fix for this bug. **DO NOT** upgrade to version 1.7.0. Instead, upgrade directly to version 1.7.1.
> - Langflow versions 1.6.0 through 1.6.3 have a critical bug where `.env` files are not read, potentially causing security vulnerabilities. **DO NOT** upgrade to these versions if you use `.env` files for configuration. Instead, upgrade to 1.6.4, which includes a fix for this bug.
> - Windows users of Langflow Desktop should **not** use the in-app update feature to upgrade to Langflow version 1.6.0. For upgrade instructions, see [Windows Desktop update issue](https://docs.langflow.org/release-notes#windows-desktop-update-issue).
> - Users must update to Langflow >= 1.3 to protect against [CVE-2025-3248](https://nvd.nist.gov/vuln/detail/CVE-2025-3248)
> - Users must update to Langflow >= 1.5.1 to protect against [CVE-2025-57760](https://github.com/langflow-ai/langflow/security/advisories/GHSA-4gv9-mp8m-592r)
>
> For security information, see our [Security Policy](./SECURITY.md) and [Security Advisories](https://github.com/langflow-ai/langflow/security/advisories).

## 🚀 Deployment

Langflow is completely open source and you can deploy it to all major deployment clouds. To learn how to deploy Langflow, see our [Langflow deployment guides](https://docs.langflow.org/deployment-overview).

## ⭐ Stay up-to-date

Star Langflow on GitHub to be instantly notified of new releases.

![Star Langflow](https://github.com/user-attachments/assets/03168b17-a11d-4b2a-b0f7-c1cce69e5a2c)

## 👋 Contribute

We welcome contributions from developers of all levels. If you'd like to contribute, please check our [contributing guidelines](./CONTRIBUTING.md) and help make Langflow more accessible.

---

[![Star History Chart](https://api.star-history.com/svg?repos=langflow-ai/langflow&type=Timeline)](https://star-history.com/#langflow-ai/langflow&Date)

## ❤️ Contributors

[![langflow contributors](https://contrib.rocks/image?repo=langflow-ai/langflow)](https://github.com/langflow-ai/langflow/graphs/contributors)
