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

<p align="center">
  <strong>简体中文</strong> | <a href="README.md">English</a>
</p>

[Langflow](https://langflow.org) 是一个强大的平台，用于构建和部署 AI 驱动的智能体（Agents）和工作流。它为开发者提供了可视化创作体验，并内置了 API 和 MCP 服务器，可将每一个工作流转化为能够集成到任何框架或技术栈应用中的工具。Langflow 开箱即用，支持所有主流的大语言模型（LLMs）、向量数据库以及不断增长的 AI 工具库。

## ✨ 核心特性

- **可视化构建界面**：快速上手并进行迭代。
- **源码访问权限**：允许您使用 Python 自定义任何组件。
- **交互式游乐场**：通过分步控制立即测试并优化您的流程。
- **多智能体编排**：具备对话管理和检索功能。
- **作为 API 部署**：或为 Python 应用导出为 JSON 格式。
- **作为 MCP 服务器部署**：将您的工作流转化为适用于 MCP 客户端的工具。
- **可观测性**：集成了 LangSmith、LangFuse 等工具。
- **企业级支持**：具备安全性与可扩展性。

## 🖥️ Langflow 桌面版 (Langflow Desktop)

Langflow 桌面版是开始使用 Langflow 最简单的方式。它包含了所有依赖项，因此您无需管理 Python 环境或手动安装软件包。支持 Windows 和 macOS。

[📥 下载 Langflow 桌面版](https://www.langflow.org/desktop)

## ⚡️ 快速开始

### 本地安装（推荐）

需要 Python 3.10–3.13 以及 [uv](https://docs.astral.sh/uv/getting-started/installation/)（推荐的包管理器）。

#### 安装

在新的目录中运行：
```shell
uv pip install langflow -U
```

将安装最新的 Langflow 软件包。更多信息请参见[安装并运行 Langflow 开源 Python 包](https://docs.langflow.org/get-started-installation#install-and-run-the-langflow-oss-python-package)。

#### 运行

启动 Langflow：
```shell
uv run langflow run
```

Langflow 将在 http://127.0.0.1:7860 启动。

大功告成！您现在可以使用 Langflow 进行构建了！🎉

## 📦 其他安装选项

### 从源码运行
如果您已克隆此仓库并希望进行贡献，请在仓库根目录下运行以下命令：
```shell
make run_cli
```
更多信息请参见 [DEVELOPMENT.md](./DEVELOPMENT.md)。

### Docker
使用默认设置启动 Langflow 容器：
```shell
docker run -p 7860:7860 langflowai/langflow:latest
```
Langflow 可在 http://localhost:7860/ 访问。有关配置选项，请参见 [Docker 部署指南](https://docs.langflow.org/deployment-docker)。

> [!CAUTION]
> - 用户必须更新到 Langflow >= 1.7.1 以防范 [CVE-2025-68477](https://github.com/langflow-ai/langflow/security/advisories/GHSA-5993-7p27-66g5) 和 [CVE-2025-68478](https://github.com/langflow-ai/langflow/security/advisories/GHSA-f43r-cc68-gpx4)。
> - Langflow 1.7.0 版本存在一个严重 Bug，升级时无法找到持久化状态（流程、项目和全局变量）。1.7.0 版本已被撤回并由包含修复的 1.7.1 版本取代。**请勿**升级到 1.7.0 版本，请直接升级到 1.7.1。
> - Langflow 1.6.0 到 1.6.3 版本存在一个严重 Bug，无法读取 `.env` 文件，可能导致安全漏洞。如果您使用 `.env` 文件进行配置，**请勿**升级到这些版本，请升级到已修复此问题的 1.6.4 版本。
> - 使用 Langflow 桌面版的 Windows 用户**不应**使用应用内更新功能升级到 1.6.0 版本。有关升级说明，请参见 [Windows 桌面版更新问题](https://docs.langflow.org/release-notes#windows-desktop-update-issue)。
> - 用户必须更新到 Langflow >= 1.3 以防范 [CVE-2025-3248](https://nvd.nist.gov/vuln/detail/CVE-2025-3248)
> - 用户必须更新到 Langflow >= 1.5.1 以防范 [CVE-2025-57760](https://github.com/langflow-ai/langflow/security/advisories/GHSA-4gv9-mp8m-592r)
>
> 有关安全信息，请参阅我们的[安全政策](./SECURITY.md)和[安全建议](https://github.com/langflow-ai/langflow/security/advisories)。

## 🚀 部署

Langflow 是完全开源的，您可以将其部署到所有主流的云平台。要了解如何部署 Langflow，请参阅我们的 [Langflow 部署指南](https://docs.langflow.org/deployment-overview)。

## ⭐ 保持更新

在 GitHub 上点亮 Langflow 的 Star，以便第一时间收到新版本的通知。

![Star Langflow](https://github.com/user-attachments/assets/03168b17-a11d-4b2a-b0f7-c1cce69e5a2c)

## 👋 参与贡献

我们欢迎所有水平的开发者进行贡献。如果您想参与，请查阅我们的[贡献指南](./CONTRIBUTING.md)，共同让 Langflow 变得更好。

---

[![Star History Chart](https://api.star-history.com/svg?repos=langflow-ai/langflow&type=Timeline)](https://star-history.com/#langflow-ai/langflow&Date)

## ❤️ 贡献者

[![langflow contributors](https://contrib.rocks/image?repo=langflow-ai/langflow)](https://github.com/langflow-ai/langflow/graphs/contributors)
