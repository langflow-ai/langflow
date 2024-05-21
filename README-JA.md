<!-- markdownlint-disable MD030 -->

# [![Langflow](https://github.com/langflow-ai/langflow/blob/dev/docs/static/img/hero.png)](https://www.langflow.org)

[English](./README.md) | [中文](./README-ZH.md) | 日本語 | [한국어](./README-KR.md) | [Русский](./README-RUS.md)

### [Langflow](https://www.langflow.org) は、AIアプリを構築、反復、および展開するための新しいビジュアルな方法です。

# ⚡️ ドキュメントとコミュニティ

- [ドキュメント](https://docs.langflow.org)
- [Discord](https://discord.com/invite/EqksyE2EX9)

# 📦 インストール

Langflowはpipでインストールできます:

```shell
# システムにPython 3.10がインストールされていることを確認してください。
# プレリリース版をインストールする
python -m pip install langflow --pre --force-reinstall

# または安定版
python -m pip install langflow -U
```

次に、Langflowを以下のように実行してください:

```shell
python -m langflow run
```

Langflowを[HuggingFace Spaces](https://huggingface.co/spaces/Langflow/Langflow-Preview)でプレビューすることもできます。数分で独自のLangflowワークスペースを作成するために、このリンクを使用してスペースを複製してください: [リンク](https://huggingface.co/spaces/Langflow/Langflow-Preview?duplicate=true)

# 🎨 フローの作成

Langflowでフローを作成するのは簡単です。サイドバーからコンポーネントをキャンバスにドラッグし、それらを接続するだけで、アプリケーションの構築を始めることができます。

プロンプトのパラメータを編集したり、コンポーネントを1つの高レベルコンポーネントにグループ化したり、独自のカスタムコンポーネントを作成したりすることで、さまざまな探求ができます。

作業が完了したら、フローをJSONファイルとしてエクスポートすることができます。

フローを読み込むには、

```python
from langflow.load import run_flow_from_json

results = run_flow_from_json("path/to/flow.json", input_value="Hello, World!")
```

# 🖥️ コマンドラインインターフェース（CLI）

Langflowは、簡単な管理と設定のためにコマンドラインインターフェース（CLI）を提供しています。

## 使用法

以下のコマンドを使用してLangflowを実行できます:

```shell
langflow run [OPTIONS]
```

各オプションの詳細は以下の通りです:

- `--help`: 全ての利用可能なオプションを表示します。
- `--host`: サーバーをバインドするホストを定義します。`LANGFLOW_HOST` 環境変数を使用して設定できます。デフォルトは `127.0.0.1` です。
- `--workers`: ワーカープロセスの数を設定します。`LANGFLOW_WORKERS` 環境変数を使用して設定できます。デフォルトは `1` です。
- `--timeout`: ワーカーのタイムアウト時間（秒単位）を設定します。デフォルトは `60` です。
- `--port`: リッスンするポートを設定します。`LANGFLOW_PORT` 環境変数を使用して設定できます。デフォルトは `7860` です。
- `--config`: 設定ファイルへのパスを定義します。デフォルトは `config.yaml` です。
- `--env-file`: 環境変数を含む `.env` ファイルへのパスを指定します。デフォルトは `.env` です。
- `--log-level`: ログレベルを定義します。`LANGFLOW_LOG_LEVEL` 環境変数を使用して設定できます。デフォルトは `critical` です。
- `--components-path`: カスタムコンポーネントが含まれるディレクトリへのパスを指定します。`LANGFLOW_COMPONENTS_PATH` 環境変数を使用して設定できます。デフォルトは `langflow/components` です。
- `--log-file`: ログファイルへのパスを指定します。`LANGFLOW_LOG_FILE` 環境変数を使用して設定できます。デフォルトは `logs/langflow.log` です。
- `--cache`: 使用するキャッシュのタイプを選択します。オプションは `InMemoryCache` と `SQLiteCache` です。`LANGFLOW_LANGCHAIN_CACHE` 環境変数を使用して設定できます。デフォルトは `SQLiteCache` です。
- `--dev/--no-dev`: 開発モードを切り替えます。デフォルトは `no-dev` です。
- `--path`: ビルドファイルが含まれるフロントエンドディレクトリへのパスを指定します。このオプションは開発目的のみです。`LANGFLOW_FRONTEND_PATH` 環境変数を使用して設定できます。
- `--open-browser/--no-open-browser`: サーバー起動後にブラウザを開くオプションを切り替えます。`LANGFLOW_OPEN_BROWSER` 環境変数を使用して設定できます。デフォルトは `open-browser` です。
- `--remove-api-keys/--no-remove-api-keys`: データベースに保存されたプロジェクトから API キーを削除するオプションを切り替えます。`LANGFLOW_REMOVE_API_KEYS` 環境変数を使用して設定できます。デフォルトは `no-remove-api-keys` です。
- `--install-completion [bash|zsh|fish|powershell|pwsh]`: 指定したシェル用の補完をインストールします。
- `--show-completion [bash|zsh|fish|powershell|pwsh]`: 指定したシェル用の補完を表示し、コピーまたはインストールをカスタマイズできます。
- `--backend-only`: バックエンドサーバーのみを起動するためのパラメーターです。デフォルト値は `False` です。`LANGFLOW_BACKEND_ONLY` 環境変数を使用して設定できます。
- `--store`: ストア機能を有効にするためのパラメーターです。無効にするには `--no-store` を使用します。`LANGFLOW_STORE` 環境変数を使用して設定できます。デフォルトは `True` です。

これらのパラメーターは、特に開発や特定の展開シナリオで Langflow の挙動をカスタマイズする必要があるユーザーにとって重要です。

### 環境変数

環境変数を使用して、多くの CLI オプションを設定できます。これらの環境変数は、オペレーティングシステムにエクスポートまたは `.env` ファイルに追加し、`--env-file` オプションを使用して読み込むことができます。

`.env` ファイルとして、`.env.example` ファイルがプロジェクトに含まれています。このファイルをコピーし、`.env` ファイルとして新しいファイルを作成し、例値を実際の設定に置き換えます。OSで`.env` ファイルを設定している場合も、`.env` ファイルの設定は優先されます。

# 展開

## Google Cloud Platform で Langflow を展開する

Google Cloud Shell を使用して Google Cloud Platform (GCP) に Langflow を展開する手順に従ってください。ガイドは [**Langflow in Google Cloud Platform**](GCP_DEPLOYMENT.md) ドキュメントでご確認いただけます。

代替手段として、以下の **"Open in Cloud Shell"** ボタンをクリックして、Google Cloud Shell を起動し、Langflow リポジトリをクローンし、インタラクティブなチュートリアルを開始してください。このチュートリアルでは、必要なリソースの設定とLangflowのGCPプロジェクトへの展開手順を案内します。

[![Open in Cloud Shell](https://gstatic.com/cloudssh/images/open-btn.svg)](https://console.cloud.google.com/cloudshell/open?git_repo=https://github.com/langflow-ai/langflow&working_dir=scripts/gcp&shellonly=true&tutorial=walkthroughtutorial_spot.md)

## Railway に展開する

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/JMXEWp?referralCode=MnPSdg)

## Render に展開する

<a href="https://render.com/deploy?repo=https://github.com/langflow-ai/langflow/tree/main">
<img src="https://render.com/images/deploy-to-render-button.svg" alt="Deploy to Render" />
</a>

# 👋 貢献する

私たちは、GitHub 上のオープンソースプロジェクトに対して、すべてのレベルの開発者からの貢献を歓迎しています。もし貢献したい場合は、[貢献ガイドライン](./CONTRIBUTING.md) をご確認いただき、Langflow をより使いやすくするお手伝いをしてください。

---

[![Star History Chart](https://api.star-history.com/svg?repos=langflow-ai/langflow&type=Timeline)](https://star-history.com/#langflow-ai/langflow&Date)

# 🌟 貢献者

[![langflow contributors](https://contrib.rocks/image?repo=langflow-ai/langflow)](https://github.com/langflow-ai/langflow/graphs/contributors)

# 📄 ライセンス

LangflowはMITライセンスの下でリリースされています。詳細については、[LICENSE](LICENSE)ファイルをご覧ください。
