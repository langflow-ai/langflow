<!-- markdownlint-disable MD030 -->

# [![Langflow](https://github.com/langflow-ai/langflow/blob/dev/docs/static/img/hero.png)](https://www.langflow.org)

[English](./README.md) | [中文](./README-ZH.md) | 日本語 | [한국어](./README-KR.md) | [Русский](./README-RUS.md)

### [Langflow](https://www.langflow.org) 新しい、視覚的な方法でAIアプリを構築し、繰り返し改良し、展開する方法です。

# ⚡️ ドキュメントとコミュニティ

- [ドキュメンテーション](https://docs.langflow.org)
- [Discord](https://discord.com/invite/EqksyE2EX9)

# 📦 インストール

Langflowはpipでインストールできます。

```shell
# システムにPython 3.10がインストールされていることを確認してください。
# プレリリースバージョンをインストールします。
python -m pip install langflow --pre --force-reinstall

# 安定版をインストールしてください。
python -m pip install langflow -U
```

その後、以下のコマンドでLangflowを実行してください。

```shell
python -m langflow run
```

[HuggingFace Spaces](https://huggingface.co/spaces/Langflow/Langflow-Preview)でLangflowをプレビューすることもできます。[このリンクを使用してスペースを複製](https://huggingface.co/spaces/Langflow/Langflow-Preview?duplicate=true)すると、数分で独自のLangflowワークスペースを作成できます。

# 🎨 フローを作成します。

Langflowを使用してフローを作成するのは簡単です。サイドバーからコンポーネントをキャンバスにドラッグし、それらを接続してアプリケーションを構築するだけです。

プロンプトパラメータを編集したり、コンポーネントを1つの高レベルのコンポーネントにグループ化したり、独自のカスタムコンポーネントを作成することで、探索できます。

作業が完了したら、フローをJSONファイルとしてエクスポートできます。

以下のコマンドでフローを読み込みます。

```python
from langflow.load import run_flow_from_json

results = run_flow_from_json("path/to/flow.json", input_value="Hello, World!")
```

# 🖥️ コマンドラインインターフェース（CLI）

Langflowは、簡単な管理と設定のためのコマンドラインインターフェース（CLI）を提供しています。

## 使用法

Langflowを実行するには、次のコマンドを使用します:

```shell
langflow run [OPTIONS]
```

各オプションについては以下に詳述します:

- `--help`: 利用可能なすべてのオプションを表示します。
- `--host`: サーバーをバインドするホストを定義します。`LANGFLOW_HOST`環境変数を使用して設定できます。デフォルトは`127.0.0.1`です。
- `--workers`: ワーカープロセスの数を設定します。`LANGFLOW_WORKERS`環境変数を使用して設定できます。デフォルトは`1`です。
- `--timeout`: ワーカーのタイムアウトを秒単位で設定します。デフォルトは`60`です。
- `--port`: リッスンするポートを設定します。`LANGFLOW_PORT`環境変数を使用して設定できます。デフォルトは`7860`です。
- `--config`: 構成ファイルへのパスを定義します。デフォルトは`config.yaml`です。
- `--env-file`: 環境変数を含む .env ファイルのパスを指定します。デフォルトは`.env`です。
- `--log-level`: ログレベルを定義します。`LANGFLOW_LOG_LEVEL`環境変数を使用して設定できます。デフォルトは`critical`です。
- `--components-path`: カスタムコンポーネントを含むディレクトリへのパスを指定します。`LANGFLOW_COMPONENTS_PATH`環境変数を使用して設定できます。デフォルトは`langflow/components`です。
- `--log-file`: ログファイルへのパスを指定します。`LANGFLOW_LOG_FILE`環境変数を使用して設定できます。デフォルトは`logs/langflow.log`です。
- `--cache`: 使用するキャッシュのタイプを選択します。オプションは `InMemoryCache` と `SQLiteCache` です。`LANGFLOW_LANGCHAIN_CACHE` 環境変数を使用して設定できます。デフォルトは `SQLiteCache` です。
- `--dev/--no-dev`: 開発モードを切り替えます。デフォルトは `no-dev` です。
- `--path`: ビルドファイルを含むフロントエンドディレクトリへのパスを指定します。このオプションは開発目的のみです。`LANGFLOW_FRONTEND_PATH` 環境変数を使用して設定できます。
- `--open-browser/--no-open-browser`: サーバー起動後にブラウザを開くオプションを切り替えます。`LANGFLOW_OPEN_BROWSER` 環境変数を使用して設定できます。デフォルトは `open-browser` です。
- `--remove-api-keys/--no-remove-api-keys`: データベースに保存されているプロジェクトからAPIキーを削除するオプションを切り替えます。`LANGFLOW_REMOVE_API_KEYS` 環境変数を使用して設定できます。デフォルトは `no-remove-api-keys` です。
- `--install-completion [bash|zsh|fish|powershell|pwsh]`: 指定されたシェルの補完をインストールします。
- `--show-completion [bash|zsh|fish|powershell|pwsh]`: 指定されたシェルの補完を表示し、コピーまたはインストールをカスタマイズできます。
- `--backend-only`: このパラメータは、デフォルト値が `False` の場合、フロントエンドなしでバックエンドサーバーのみを実行することを許可します。`LANGFLOW_BACKEND_ONLY` 環境変数を使用して設定することもできます。
- `--store`: このパラメータは、デフォルト値が `True` の場合、ストア機能を有効にします。 `--no-store` を使用して無効にします。 `LANGFLOW_STORE` 環境変数で構成できます。

これらのパラメータは、Langflowの動作をカスタマイズする必要があるユーザーにとって重要です。特に開発や特定の展開シナリオでの場合です。

### 環境変数

CLIのオプションの多くを環境変数を使用して設定することができます。これらは、オペレーティングシステムにエクスポートするか、`.env`ファイルに追加して、`--env-file`オプションを使用してロードできます。

プロジェクトには`.env.example`という名前のサンプル`.env`ファイルが含まれています。このファイルを新しい`.env`ファイルにコピーし、実際の設定に対応するように例の値を置き換えます。OSと`.env`ファイルの両方で値を設定している場合、`.env`の設定が優先されます。

# 展開

## Google Cloud PlatformでLangflowを展開します。

Google Cloud Shellを使用して、Google Cloud Platform（GCP）にLangflowを展開する手順に従います。ガイドは[**Langflow in Google Cloud Platform**](GCP_DEPLOYMENT.md)文書で利用可能です。

以下は、Langflow リポジトリをクローンし、必要なリソースの設定と Langflow の GCP プロジェクトへのデプロイメントの手順を案内する対話型チュートリアルを開始するための、**"Open in Cloud Shell"** ボタンをクリックしてください。

[![Open in Cloud Shell](https://gstatic.com/cloudssh/images/open-btn.svg)](https://console.cloud.google.com/cloudshell/open?git_repo=https://github.com/langflow-ai/langflow&working_dir=scripts/gcp&shellonly=true&tutorial=walkthroughtutorial_spot.md)

## Railwayでデプロイ

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/JMXEWp?referralCode=MnPSdg)

## Renderでデプロイ

<a href="https://render.com/deploy?repo=https://github.com/langflow-ai/langflow/tree/main">
<img src="https://render.com/images/deploy-to-render-button.svg" alt="Deploy to Render" />
</a>

# 👋 貢献

GitHub 上の当社のオープンソースプロジェクトへのすべてのレベルの開発者からの貢献を歓迎します。貢献を希望される場合は、[貢献ガイドライン](./CONTRIBUTING.md) をご確認いただき、Langflow をよりアクセスしやすくするお手伝いをしてください。

---

[![Star History Chart](https://api.star-history.com/svg?repos=langflow-ai/langflow&type=Timeline)](https://star-history.com/#langflow-ai/langflow&Date)

# 🌟 貢献者

[![langflow contributors](https://contrib.rocks/image?repo=langflow-ai/langflow)](https://github.com/langflow-ai/langflow/graphs/contributors)

# 📄 License

Langflow は MIT ライセンスのもとでリリースされています。詳細については、[LICENSE](LICENSE) ファイルをご覧ください。
