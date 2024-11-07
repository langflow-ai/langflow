<div align="center" style="padding: 10px; border: 1px solid #ccc; background-color: #f9f9f9; border-radius: 10px; margin-bottom: 20px;">
    <h2 style="margin: 0; font-size: 24px; color: #333;">Langflow 1.0 이 출시되었습니다! 🎉</h2>
    <p style="margin: 5px 0 0 0; font-size: 16px; color: #666;"><a href="https://medium.com/p/73d3bdce8440" style="text-decoration: underline; color: #1a73e8;">여기</a>를 눌러 자세히 알아보기!</p>
</div>

<!-- markdownlint-disable MD030 -->

# [![Langflow](./docs/static/img/hero.png)](https://www.langflow.org)

<p align="center"><strong>
    다중 에이전트 및 RAG 애플리케이션 구축을 위한 시각적 프레임워크
</strong></p>
<p align="center" style="font-size: 12px;">
    오픈소스, Python-기반, 전체 커스텀, LLM과 Vector store를 몰라도 사용 가능
</p>

<p align="center" style="font-size: 12px;">
    <a href="https://docs.langflow.org" style="text-decoration: underline;">문서</a> -
    <a href="https://discord.com/invite/EqksyE2EX9" style="text-decoration: underline;">Discord에 참여하기</a> -
    <a href="https://twitter.com/langflow_ai" style="text-decoration: underline;">X에서 팔로우하기</a> -
    <a href="https://huggingface.co/spaces/Langflow/Langflow" style="text-decoration: underline;">실시간 데모</a>
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

# 📝 목차

- [📝 목차](#-content)
- [📦 시작하기](#-get-started)
- [🎨 플로우 만들기](#-create-flows)
- [배포](#deploy)
  - [DataStax Langflow](#datastax-langflow)
  - [Hugging Face Spaces에 Langflow 배포하기](#deploy-langflow-on-hugging-face-spaces)
  - [Google Cloud Platform에 Langflow 배포하기](#deploy-langflow-on-google-cloud-platform)
  - [Railway에 배포하기](#deploy-on-railway)
  - [Render에 배포하기](#deploy-on-render)
  - [Kubernetes에 배포하기](#deploy-on-kubernetes)
- [🖥️ 명령줄 인터페이스 (CLI)](#️-command-line-interface-cli)
  - [사용법](#usage)
    - [환경 변수](#environment-variables)
- [👋 기여](#-contribute)
- [🌟 기여자](#-contributors)
- [📄 라이선스](#-license)

# 📦 시작하기

pip으로 Langflow 다운로드:

```shell
# >=Python 3.10 이 시스템에 미리 설치되어 있어야 합니다.
python -m pip install langflow -U
```

혹은

복제된 Repo에서 설치하려면 다음과 같이 Langflow의 프론트엔드와 백엔드를 구축하고 설치할 수 있습니다:

```shell
make install_frontend && make build_frontend && make install_backend
```

Langflow 실행하기:

```shell
python -m langflow run
```

# 🎨 플로우 만들기

플로우(Flow)는 전체적인 작업의 `흐름`을 표현하는것으로, 별도의 코딩작업을 최소화 하고, 시각적으로 수정/확인이 가능한 일련의 그룹을 말합니다.

Langflow를 사용하여 플로우를 만드는 것은 쉽습니다. 사이드바의 구성 요소를 작업 공간으로 끌어다가 연결하기만 하면 응용 프로그램을 구축할 수 있습니다.

프롬프트 매개 변수를 편집하고 구성 요소를 하나의 상위 수준 구성 요소로 그룹화하고 사용자 정의 구성 요소를 구축하여 탐색합니다.

작업이 완료되면 플로우를 JSON 파일로 내보낼 수 있습니다.

플로우 로드하기:

```python
from langflow.load import run_flow_from_json

results = run_flow_from_json("path/to/flow.json", input_value="Hello, World!")
```

# 배포

## DataStax Langflow

DataStax Langflow는 [AstraDB](https://www.datastax.com/products/datastax-astra) 와 통합된 Langflow의 호스팅된 버전입니다. 별도의 설치나 설정이 필요하지 않고 몇 분 안에 실행됩니다. [무료로 가입하기](https://astra.datastax.com/signup?type=langflow).

## Hugging Face Spaces에 Langflow 배포하기

[Hugging Face Spaces](https://huggingface.co/spaces/Langflow/Langflow) 에서 Langflow를 미리 볼 수 있습니다. [space 복제하기](https://huggingface.co/spaces/Langflow/Langflow?duplicate=true) 에서 몇 분 안에 자신만의 Langflow 작업 공간을 만들 수 있습니다.

## Google Cloud Platform에 Langflow 배포하기

Google Cloud Shell을 사용하여 Google Cloud Platform(GCP)에 Langflow를 배포하려면 단계별 가이드를 따르십시오. 가이드는 [**Langflow in Google Cloud Platform**](/docs/docs/Deployment/deployment-gcp.md) 문서에서 확인할 수 있습니다.

또는 아래의 **"Cloud Shell에서 열기"** 버튼을 클릭하여 Google Cloud Shell을 시작하고 Langflow 저장소를 복제한 후 필요한 리소스를 설정하고 GCP 프로젝트에 Langflow를 배포하는 과정을 안내하는 **대화형 튜토리얼**을 시작합니다.

[![Cloud Shell에서 열기](https://gstatic.com/cloudssh/images/open-btn.svg)](https://console.cloud.google.com/cloudshell/open?git_repo=https://github.com/langflow-ai/langflow&working_dir=scripts/gcp&shellonly=true&tutorial=walkthroughtutorial_spot.md)

## Railway에 배포하기

이 템플릿을 사용하여 Railway에 Langflow 1.0을 배포합니다:

[![Railway에 배포하기](https://railway.app/button.svg)](https://railway.app/template/JMXEWp?referralCode=MnPSdg)

## Render에 배포하기

<a href="https://render.com/deploy?repo=https://github.com/langflow-ai/langflow/tree/main">
<img src="https://render.com/images/deploy-to-render-button.svg" alt="Render에 배포하기" />
</a>

## Kubernetes에 배포하기

[Langflow on Kubernetes](./docs/docs/Deployment/deployment-kubernetes.md)의 가이드를 따르세요.

# 🖥️ 명령줄 인터페이스 (CLI)

Langflow는 쉬운 관리 및 구성을 위한 명령줄 인터페이스(CLI)를 제공합니다.

## 사용법

다음 명령을 사용하여 Langflow를 실행할 수 있습니다:

```shell
langflow run [OPTIONS]
```

각 옵션의 자세한 내용은 아래와 같습니다:

- `--help`: 사용 가능한 모든 옵션을 표시합니다.
- `--host`: 서버를 바인딩할 호스트를 정의합니다. `LANGFLOW_HOST` 환경 변수를 사용하여 설정할 수 있습니다. 기본 값은 `127.0.0.1`입니다.
- `--workers`: 작업자 프로세스 수를 설정합니다. `LANGFLOW_WORKERS` 환경 변수를 사용하여 설정할 수 있습니다. 기본 값은 `1`입니다.
- `--worker-timeout`: 작업자 시간 제한을 초 단위로 설정합니다. 기본 값은 `60`입니다.
- `--port`: 수신할 포트를 설정합니다. `LANGFLOW_PORT` 환경 변수를 사용하여 설정할 수 있습니다. 기본 값은 `7860`입니다.
- `--env-file`: 환경 변수가 포함된 .env 파일의 경로를 지정합니다. 기본 값은 `.env`입니다.
- `--log-level`: 로깅 수준을 정의합니다. `LANGFLOW_LOG_LEVEL` 환경 변수를 사용하여 설정할 수 있습니다. 기본 값은 `critical`입니다.
- `--components-path`: 사용자 지정 구성 요소가 포함된 디렉토리 경로를 지정합니다. `LANGFLOW_COMPONENTS_PATH` 환경 변수를 사용하여 설정할 수 있습니다. 기본 값은 `langflow/components`입니다.
- `--log-file`: 로그 파일 경로를 지정합니다. `LANGFLOW_LOG_FILE` 환경 변수를 사용하여 설정할 수 있습니다. 기본 값은 `logs/langflow.log`입니다.
- `--cache`: 사용할 캐시 유형을 선택합니다. 옵션은 `InMemoryCache` 와 `SQLiteCache`입니다. `LANGFLOW_LANGCHAIN_CACHE` 환경 변수를 사용하여 설정할 수 있습니다. 기본 값은 `SQLiteCache`입니다.
- `--dev/--no-dev`: 개발 모드를 전환합니다. 기본 값은 `no-dev`입니다.
- `--path`: 빌드 파일이 포함된 프런트엔드 디렉토리 경로를 지정합니다. 이 옵션은 개발 목적으로만 사용됩니다. `LANGFLOW_FRONTEND_PATH` 환경 변수를 사용하여 설정할 수 있습니다.
- `--open-browser/--no-open-browser`: 서버를 시작한 후 브라우저를 여는 옵션을 토글합니다. `LANGFLOW_OPEN_BROWSER` 환경 변수를 사용하여 설정할 수 있습니다. 기본 값은 `open-browser`입니다.
- `--remove-api-keys/--no-remove-api-keys`: 데이터베이스에 저장된 프로젝트에서 API 키를 제거하는 옵션을 토글합니다. `LANGFLOW_REMOVE_API_KEYS` 환경 변수를 사용하여 설정할 수 있습니다. 기본 값은 `no-remove-api-keys`입니다.
- `--install-completion [bash|zsh|fish|powershell|pwsh]`: 지정된 셸에 대해 설치합니다.
- `--show-completion [bash|zsh|fish|powershell|pwsh]`: 지정된 셸의 완료를 표시하여 셸을 복사하거나 설치를 사용자 정의할 수 있습니다.
- `--backend-only`: 이 파라미터는 기본 값이 `False`이며, 프론트엔드 없이 백엔드 서버만 실행할 수 있도록 합니다. `LANGFLOW_BACKEND_ONLY` 환경 변수를 사용하여 설정할 수 있습니다.
- `--store`: 이 파라미터는 기본 값이 `True`이며, 스토어 기능을 활성화하고, `--no-store`를 사용하여 비활성화할 수 있습니다. `LANGFLOW_STORE` 환경 변수를 사용하여 설정할 수 있습니다.

These parameters are important for users who need to customize the behavior of Langflow, especially in development or specialized deployment scenarios.

### 환경 변수

환경 변수를 사용하여 많은 CLI 옵션을 구성할 수 있습니다. 이러한 옵션은 운영 체제에서 내보내거나 `.env` 파일에 추가 하고 `--env-file` 옵션을 사용하여 로드할 수 있습니다.

예제 `.env` 파일은 `.env.example` 프로젝트에 포함되어 있습니다. 이 파일을 복사하고 `.env` 파일로 이름을 바꾸어 실제 설정을 바꾸세요. OS와 `.env` 파일 모두에서 값을 설정하는 경우, `.env` 파일 설정이 우선시 됩니다.

# 👋 기여

모든 레벨의 개발자가 GitHub의 오픈소스 프로젝트에 기여하는 것을 환영합니다. 기여하고 싶으시다면 [기여 지침](./CONTRIBUTING.md)을 확인 하고 Langflow를 더 접근하기 쉽게 만드는 데 도움을 주세요.

---

[![Star History Chart](https://api.star-history.com/svg?repos=langflow-ai/langflow&type=Timeline)](https://star-history.com/#langflow-ai/langflow&Date)

# 🌟 기여자

[![langflow contributors](https://contrib.rocks/image?repo=langflow-ai/langflow)](https://github.com/langflow-ai/langflow/graphs/contributors)

# 📄 라이선스

Langflow는 MIT 라이선스에 따라 출시됩니다. 자세한 내용은 [라이선스](LICENSE) 파일을 확인하세요.
