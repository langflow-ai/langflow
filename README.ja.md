<div align="center" style="padding: 10px; border: 1px solid #ccc; background-color: #f9f9f9; border-radius: 10px; margin-bottom: 20px;">
    <h2 style="margin: 0; font-size: 24px; color: #333;">Langflow 1.0 がリリースされました！ 🎉</h2>
    <p style="margin: 5px 0 0 0; font-size: 16px; color: #666;">詳細は <a href="https://medium.com/p/73d3bdce8440" style="text-decoration: underline; color: #1a73e8;">こちら</a> をご覧ください！</p>
</div>

<!-- markdownlint-disable MD030 -->

# [![Langflow](./docs/static/img/hero.png)](https://www.langflow.org)

<p align="center"><strong>
    マルチエージェントおよびRAGアプリケーションを構築するためのビジュアルフレームワーク
</strong></p>
<p align="center" style="font-size: 12px;">
    オープンソース、Python駆動、完全にカスタマイズ可能、LLMおよびベクトルストアに依存しない
</p>

<p align="center" style="font-size: 12px;">
    <a href="https://docs.langflow.org" style="text-decoration: underline;">ドキュメント</a> -
    <a href="https://discord.com/invite/EqksyE2EX9" style="text-decoration: underline;">Discordに参加</a> -
    <a href="https://twitter.com/langflow_ai" style="text-decoration: underline;">Xでフォロー</a> -
    <a href="https://huggingface.co/spaces/Langflow/Langflow-Preview" style="text-decoration: underline;">ライブデモ</a>
</p>

<p align="center">
    <a href="https://github.com/langflow-ai/langflow">
        <img src="https://img.shields.io/github/stars/langflow-ai/langflow">
    </a>
    <a href="https://discord.com/invite/EqksyE2EX9">
        <img src="https://img.shields.io/discord/1116803230643527710?label=Discord">
    </a>
</p>

<div align="center">
  <a href="./README.md"><img alt="README in English" src="https://img.shields.io/badge/English-d9d9d9"></a>
  <a href="./README.PT.md"><img alt="README in Portuguese" src="https://img.shields.io/badge/Portuguese-d9d9d9"></a>
  <a href="./README.ES.md"><img alt="README in Spanish" src="https://img.shields.io/badge/Spanish-d9d9d9"></a>
  <a href="./README.zh_CN.md"><img alt="README in Simplified Chinese" src="https://img.shields.io/badge/简体中文-d9d9d9"></a>
  <a href="./README.ja.md"><img alt="README in Japanese" src="https://img.shields.io/badge/日本語-d9d9d9"></a>
  <a href="./README.KR.md"><img alt="README in KOREAN" src="https://img.shields.io/badge/한국어-d9d9d9"></a>
</div>

<p align="center">
  <img src="./docs/static/img/langflow_basic_howto.gif" alt="Your GIF" style="border: 3px solid #211C43;">
</p>

# 📝 目次

- [📝 目次](#-目次)
- [📦 始めに](#-始めに)
- [🎨 フローの作成](#-フローの作成)
- [デプロイ](#デプロイ)
  - [DataStax Langflow](#datastax-langflow)
  - [Hugging Face Spaces に Langflow をデプロイ](#hugging-face-spacesにlangflowをデプロイ)
  - [Google Cloud Platform に Langflow をデプロイ](#google-cloud-platformにlangflowをデプロイ)
  - [Railway にデプロイ](#railwayにデプロイ)
  - [Render にデプロイ](#renderにデプロイ)
  - [Kubernetes にデプロイ](#kubernetesにデプロイ)
- [🖥️ コマンドラインインターフェース (CLI)](#️-コマンドラインインターフェース-cli)
  - [使用方法](#使用方法)
    - [環境変数](#環境変数)
- [👋 貢献](#-貢献)
- [🌟 貢献者](#-貢献者)
- [📄 ライセンス](#-ライセンス)

# 📦 始めに

Langflow を pip でインストールできます：

```shell
# システムに>=Python 3.10がインストールされていることを確認してください。
python -m pip install langflow -U
```

または

クローンしたリポジトリからインストールしたい場合は、以下のコマンドで Langflow のフロントエンドとバックエンドをビルドしてインストールできます：

```shell
make install_frontend && make build_frontend && make install_backend
```

その後、以下のコマンドで Langflow を実行します：

```shell
python -m langflow run
```

# 🎨 フローの作成

Langflow を使ってフローを作成するのは簡単です。サイドバーからコンポーネントをワークスペースにドラッグして接続するだけで、アプリケーションの構築を開始できます。

プロンプトパラメータを編集したり、コンポーネントを単一の高レベルコンポーネントにグループ化したり、独自のカスタムコンポーネントを作成したりして探索してください。

完了したら、フローを JSON ファイルとしてエクスポートできます。

以下のスクリプトを使用してフローを読み込みます：

```python
from langflow.load import run_flow_from_json

results = run_flow_from_json("path/to/flow.json", input_value="Hello, World!")
```

# デプロイ

## DataStax Langflow

DataStax Langflow は、[AstraDB](https://www.datastax.com/products/datastax-astra)と統合された Langflow のホストバージョンです。インストールや設定なしで数分で稼働できます。[無料でサインアップ](https://astra.datastax.com/signup?type=langflow)してください。

## Hugging Face Spaces に Langflow をデプロイ

[HuggingFace Spaces](https://huggingface.co/spaces/Langflow/Langflow-Preview)で Langflow をプレビューすることもできます。[このリンクを使用してスペースをクローン](https://huggingface.co/spaces/Langflow/Langflow-Preview?duplicate=true)して、数分で独自の Langflow ワークスペースを作成できます。

## Google Cloud Platform に Langflow をデプロイ

Google Cloud Shell を使用して Google Cloud Platform（GCP）に Langflow をデプロイする手順については、[**Langflow in Google Cloud Platform**](./docs/docs/Deployment/deployment-gcp.md)ドキュメントをご覧ください。

または、以下の**「Open in Cloud Shell」**ボタンをクリックして Google Cloud Shell を起動し、Langflow リポジトリをクローンして、GCP プロジェクトに必要なリソースを設定し、Langflow をデプロイするプロセスをガイドする**インタラクティブチュートリアル**を開始します。

[![Open in Cloud Shell](https://gstatic.com/cloudssh/images/open-btn.svg)](https://console.cloud.google.com/cloudshell/open?git_repo=https://github.com/langflow-ai/langflow&working_dir=scripts/gcp&shellonly=true&tutorial=walkthroughtutorial_spot.md)

## Railway にデプロイ

このテンプレートを使用して Langflow 1.0 を Railway にデプロイします：

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/JMXEWp?referralCode=MnPSdg)

## Render にデプロイ

<a href="https://render.com/deploy?repo=https://github.com/langflow-ai/langflow/tree/main">
<img src="https://render.com/images/deploy-to-render-button.svg" alt="Deploy to Render" />
</a>

## Kubernetes にデプロイ

[Kubernetes に Langflow をデプロイ](./docs/docs/Deployment/deployment-kubernetes.md)する手順については、ステップバイステップガイドをご覧ください。

# 🖥️ コマンドラインインターフェース (CLI)

Langflow は、簡単な管理と設定のためのコマンドラインインターフェース（CLI）を提供します。

## 使用方法

以下のコマンドを使用して Langflow を実行できます：

```shell
langflow run [OPTIONS]
```

各オプションの詳細は以下の通りです：

- `--help`: 利用可能なすべてのオプションを表示します。
- `--host`: サーバーをバインドするホストを定義します。`LANGFLOW_HOST`環境変数を使用して設定できます。デフォルトは`127.0.0.1`です。
- `--workers`: ワーカープロセスの数を設定します。`LANGFLOW_WORKERS`環境変数を使用して設定できます。デフォルトは`1`です。
- `--worker-timeout`: ワーカーのタイムアウトを秒単位で設定します。デフォルトは`60`です。
- `--port`: リッスンするポートを設定します。`LANGFLOW_PORT`環境変数を使用して設定できます。デフォルトは`7860`です。
- `--env-file`: 環境変数を含む.env ファイルのパスを指定します。デフォルトは`.env`です。
- `--log-level`: ログレベルを定義します。`LANGFLOW_LOG_LEVEL`環境変数を使用して設定できます。デフォルトは`critical`です。
- `--components-path`: カスタムコンポーネントを含むディレクトリのパスを指定します。`LANGFLOW_COMPONENTS_PATH`環境変数を使用して設定できます。デフォルトは`langflow/components`です。
- `--log-file`: ログファイルのパスを指定します。`LANGFLOW_LOG_FILE`環境変数を使用して設定できます。デフォルトは`logs/langflow.log`です。
- `--cache`: 使用するキャッシュの種類を選択します。オプションは`InMemoryCache`と`SQLiteCache`です。`LANGFLOW_LANGCHAIN_CACHE`環境変数を使用して設定できます。デフォルトは`SQLiteCache`です。
- `--dev/--no-dev`: 開発モードを切り替えます。デフォルトは`no-dev`です。
- `--path`: ビルドファイルを含むフロントエンドディレクトリのパスを指定します。このオプションは開発目的のみに使用されます。`LANGFLOW_FRONTEND_PATH`環境変数を使用して設定できます。
- `--open-browser/--no-open-browser`: サーバー起動後にブラウザを開くオプションを切り替えます。`LANGFLOW_OPEN_BROWSER`環境変数を使用して設定できます。デフォルトは`open-browser`です。
- `--remove-api-keys/--no-remove-api-keys`: データベースに保存されたプロジェクトから API キーを削除するオプションを切り替えます。`LANGFLOW_REMOVE_API_KEYS`環境変数を使用して設定できます。デフォルトは`no-remove-api-keys`です。
- `--install-completion [bash|zsh|fish|powershell|pwsh]`: 指定されたシェルの補完をインストールします。
- `--show-completion [bash|zsh|fish|powershell|pwsh]`: 指定されたシェルの補完を表示し、コピーまたはインストールをカスタマイズできます。
- `--backend-only`: デフォルト値が`False`のこのパラメータは、フロントエンドなしでバックエンドサーバーのみを実行することを許可します。`LANGFLOW_BACKEND_ONLY`環境変数を使用して設定できます。
- `--store`: デフォルト値が`True`のこのパラメータは、ストア機能を有効にします。無効にするには`--no-store`を使用します。`LANGFLOW_STORE`環境変数を使用して設定できます。

これらのパラメータは、特に開発や特殊なデプロイメントシナリオで Langflow の動作をカスタマイズする必要があるユーザーにとって重要です。

### 環境変数

多くの CLI オプションは環境変数を使用して構成できます。これらの変数は、オペレーティングシステムにエクスポートするか、`.env`ファイルに追加して`--env-file`オプションを使用してロードできます。

プロジェクトには、`.env.example`という名前のサンプル`.env`ファイルが含まれています。このファイルを新しいファイル`.env`にコピーし、サンプル値を実際の設定に置き換えます。OS と`.env`ファイルの両方に値を設定している場合、`.env`の設定が優先されます。

# 👋 貢献

私たちは、すべてのレベルの開発者が GitHub のオープンソースプロジェクトに貢献することを歓迎します。貢献したい場合は、[貢献ガイドライン](./CONTRIBUTING.md)を確認し、Langflow をよりアクセスしやすくするのにご協力ください。

---

[![Star History Chart](https://api.star-history.com/svg?repos=langflow-ai/langflow&type=Timeline)](https://star-history.com/#langflow-ai/langflow&Date)

# 🌟 貢献者

[![langflow contributors](https://contrib.rocks/image?repo=langflow-ai/langflow)](https://github.com/langflow-ai/langflow/graphs/contributors)

# 📄 ライセンス

Langflow は MIT ライセンスの下でリリースされています。詳細については、[LICENSE](LICENSE)ファイルを参照してください。
