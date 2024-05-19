<!-- markdownlint-disable MD030 -->

# [![Langflow](https://github.com/langflow-ai/langflow/blob/dev/docs/static/img/hero.png)](https://www.langflow.org)

[English](./README.md) | 中文 | [日本語](./README-JA.md) | [한국어](./README-KR.md) | [Русский](./README-RUS.md)

### [Langflow](https://www.langflow.org) 这是一种全新的、可视化的方法，用于构建、迭代和部署人工智能应用程序。

# ⚡️ 文档和社区

- [文档](https://docs.langflow.org)
- [Discord](https://discord.com/invite/EqksyE2EX9)

# 📦 安装

您可以使用 pip 安装 Langflow：

```shell
# 确保您的系统上已安装 Python 3.10。
# 安装预发布版本
python -m pip install langflow --pre --force-reinstall

# 或稳定版本
python -m pip install langflow -U
```

然后，使用以下命令运行 Langflow：

```shell
python -m langflow run
```

您还可以在 [HuggingFace Spaces](https://huggingface.co/spaces/Langflow/Langflow-Preview). [使用此链接克隆该空间](https://huggingface.co/spaces/Langflow/Langflow-Preview?duplicate=true), 以便在几分钟内创建您自己的 Langflow 工作空间。

# 🎨 创建流程

创建 Langflow 流程非常简单。只需从侧边栏拖动组件到画布上，并连接它们即可开始构建您的应用程序。

通过编辑提示参数来探索，将组件分组到单个高级组件中，并构建您自己的自定义组件。

完成后，您可以将流程导出为 JSON 文件。

加载流程的方式是：

```python
from langflow.load import run_flow_from_json

results = run_flow_from_json("path/to/flow.json", input_value="Hello, World!")
```

# 🖥️ 命令行界面（CLI）

Langflow 提供了命令行界面（CLI），用于方便的管理和配置。

## 用法

您可以使用以下命令运行 Langflow：

```shell
langflow run [OPTIONS]
```

每个选项的详细信息如下：

- `--help`: 显示所有可用选项。
- `--host`: 定义绑定服务器的主机地址。可以使用 `LANGFLOW_HOST` 环境变量进行设置，默认为 `127.0.0.1`。
- `--workers`: 设置工作进程的数量。可以使用 `LANGFLOW_WORKERS` 环境变量进行设置，默认为 `1`。
- `--timeout`: 设置工作进程的超时时间（秒）。默认为 `60`。
- `--port`: 设置服务器监听的端口号。可以使用 `LANGFLOW_PORT` 环境变量进行设置，默认为 `7860`。
- `--config`: 指定配置文件的路径。默认为 `config.yaml`。
- `--env-file`: 指定包含环境变量的 `.env` 文件路径。默认为 `.env`。
- `--log-level`: 定义日志级别。可以使用 `LANGFLOW_LOG_LEVEL` 环境变量进行设置，默认为 `critical`。
- `--components-path`: 指定包含自定义组件的目录路径。可以使用 `LANGFLOW_COMPONENTS_PATH` 环境变量进行设置，默认为 `langflow/components`。
- `--log-file`: 指定日志文件的路径。可以使用 `LANGFLOW_LOG_FILE` 环境变量进行设置，默认为 `logs/langflow.log`。
- `--cache`: 选择要使用的缓存类型。选项有 `InMemoryCache` 和 `SQLiteCache`。可以使用 `LANGFLOW_LANGCHAIN_CACHE` 环境变量进行设置，默认为 `SQLiteCache`。
- `--dev/--no-dev`: 切换开发模式。默认为 `no-dev`。
- `--path`: 指定包含构建文件的前端目录路径。此选项仅用于开发目的。可以使用 `LANGFLOW_FRONTEND_PATH` 环境变量进行设置。
- `--open-browser/--no-open-browser`: 切换是否在启动服务器后打开浏览器的选项。可以使用 `LANGFLOW_OPEN_BROWSER` 环境变量进行设置，默认为 `open-browser`。
- `--remove-api-keys/--no-remove-api-keys`: 切换是否从数据库中保存的项目中移除 API 密钥的选项。可以使用 `LANGFLOW_REMOVE_API_KEYS` 环境变量进行设置，默认为 `no-remove-api-keys`。
- `--install-completion [bash|zsh|fish|powershell|pwsh]`: 安装指定 shell 的自动补全功能。
- `--show-completion [bash|zsh|fish|powershell|pwsh]`: 显示指定 shell 的自动补全功能，允许复制或自定义安装。
- `--backend-only`: 此参数默认为 `False`，允许仅运行后端服务器而不包含前端。可以使用 `LANGFLOW_BACKEND_ONLY` 环境变量进行设置。
- `--store`: 此参数默认为 `True`，启用存储功能。使用 `--no-store` 可以禁用它。可以使用 `LANGFLOW_STORE` 环境变量进行设置。

这些参数对于需要在开发或专业部署场景中定制 Langflow 行为的用户非常重要。

### 环境变量

您可以使用环境变量来配置许多 CLI 选项。这些可以在操作系统中导出，也可以添加到 `.env` 文件中，并使用 `--env-file` 选项加载。

项目中包含一个名为 `.env.example` 的示例 `.env` 文件。将此文件复制到一个名为 `.env` 的新文件中，并用您的实际设置替换示例值。如果您同时在操作系统和 `.env` 文件中设置了值，`.env` 文件中的设置将优先生效。

# 部署

## 部署 Langflow 到 Google Cloud Platform（GCP）

请按照我们的逐步指南，在 Google 云平台（GCP）上使用 Google Cloud Shell 部署 Langflow。该指南可以在以下位置找到：[**在 Google Cloud Platform 上的 Langflow**](GCP_DEPLOYMENT.md) 文档。

或者，点击下方的 **“在 Cloud Shell 中打开”** 按钮，启动 Google Cloud Shell，克隆 Langflow 仓库，并开始一个 **交互式教程**，该教程将引导您完成设置必要资源并在您的 GCP 项目上部署 Langflow 的过程。

[![Open in Cloud Shell](https://gstatic.com/cloudssh/images/open-btn.svg)](https://console.cloud.google.com/cloudshell/open?git_repo=https://github.com/langflow-ai/langflow&working_dir=scripts/gcp&shellonly=true&tutorial=walkthroughtutorial_spot.md)

## 部署在 Railway 平台上

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/JMXEWp?referralCode=MnPSdg)

## 部署在 Render 平台上

<a href="https://render.com/deploy?repo=https://github.com/langflow-ai/langflow/tree/main">
<img src="https://render.com/images/deploy-to-render-button.svg" alt="Deploy to Render" />
</a>

# 👋 贡献

我们欢迎所有级别的开发者为我们在GitHub上的开源项目贡献力量。如果您想要贡献，请检查我们的 [贡献指南。](./CONTRIBUTING.md) 并帮助使Langflow更加易于访问。

---

[![Star History Chart](https://api.star-history.com/svg?repos=langflow-ai/langflow&type=Timeline)](https://star-history.com/#langflow-ai/langflow&Date)

# 🌟 贡献者

[![langflow contributors](https://contrib.rocks/image?repo=langflow-ai/langflow)](https://github.com/langflow-ai/langflow/graphs/contributors)

# 📄 许可证

Langflow是根据MIT许可证发布的. See the [LICENSE](LICENSE) 文件以获取详细信息。
