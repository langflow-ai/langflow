<!-- markdownlint-disable MD030 -->

# [![Langflow](https://github.com/langflow-ai/langflow/blob/dev/docs/static/img/hero.png)](https://www.langflow.org)

[English](./README.md) | [中文](READMEs/README-ZH.md) | [日本語](READMEs/README-JA.md) | 한국어 | [Русский](READMEs/README-RUS.md)

### [Langflow](https://www.langflow.org) 인공지능 앱을 만들고, 반복하고, 배포하는 새로운 시각적인 방법입니다.

# ⚡️ 문서화와 커뮤니티

- [문서화](https://docs.langflow.org)
- [Discord](https://discord.com/invite/EqksyE2EX9)

# 📦 설치

Langflow를 pip로 설치할 수 있습니다.

```shell
# 시스템에 Python 3.10이 설치되어 있는지 확인하십시오.
# 사전 릴리스 버전을 설치하세요.
python -m pip install langflow --pre --force-reinstall

# or stable version
python -m pip install langflow -U
```

그런 다음, 다음 명령으로 Langflow를 실행하세요:

```shell
python -m langflow run
```

[HuggingFace Spaces](https://huggingface.co/spaces/Langflow/Langflow-Preview)에서 Langflow를 미리 볼 수도 있습니다. [이 링크를 사용하여 공간을 복제하면](https://huggingface.co/spaces/Langflow/Langflow-Preview?duplicate=true), 단 몇 분 만에 자신만의 Langflow 작업 공간을 만들 수 있습니다.

# 🎨 플로우 생성

Langflow를 사용하여 플로우를 만드는 것은 간단합니다. 사이드바에서 구성 요소를 캔버스로 끌어다가 연결하여 응용 프로그램을 만들기 시작하세요.

프롬프트 매개변수를 편집하여 탐색하고, 구성 요소를 단일 상위 수준 구성 요소로 그룹화하고, 자신만의 사용자 정의 구성 요소를 만들어보세요.

완료되면 플로우를 JSON 파일로 내보낼 수 있습니다.

다음 명령으로 플로우를 불러옵니다:

```python
from langflow.load import run_flow_from_json

results = run_flow_from_json("path/to/flow.json", input_value="Hello, World!")
```

# 🖥️ 명령 줄 인터페이스(CLI)

Langflow은 쉬운 관리와 구성을 위한 명령 줄 인터페이스(CLI)를 제공합니다.

## 사용법

다음 명령을 사용하여 Langflow를 실행할 수 있습니다:

```shell
langflow run [OPTIONS]
```

아래는 각 옵션에 대한 자세한 설명입니다:

- `--help`: 모든 사용 가능한 옵션을 표시합니다.
- `--host`: 서버를 바인딩할 호스트를 정의합니다. `LANGFLOW_HOST` 환경 변수를 사용하여 설정할 수 있습니다. 기본값은 `127.0.0.1`입니다.
- `--workers`: 워커 프로세스의 수를 설정합니다. `LANGFLOW_WORKERS` 환경 변수를 사용하여 설정할 수 있습니다. 기본값은 `1`입니다.
- `--timeout`: 워커 타임아웃을 초 단위로 설정합니다. 기본값은 `60`입니다.
- `--port`: 수신 대기할 포트를 설정합니다. `LANGFLOW_PORT` 환경 변수를 사용하여 설정할 수 있습니다. 기본값은 `7860`입니다.
- `--config`: 구성 파일의 경로를 정의합니다. 기본값은 `config.yaml`입니다.
- `--env-file`: 환경 변수가 포함된 .env 파일의 경로를 지정합니다. 기본값은 `.env`입니다.
- `--log-level`: 로깅 레벨을 정의합니다. `LANGFLOW_LOG_LEVEL` 환경 변수를 사용하여 설정할 수 있습니다. 기본값은 `critical`입니다.
- `--components-path`: 사용자 정의 구성 요소가 포함된 디렉터리의 경로를 지정합니다. `LANGFLOW_COMPONENTS_PATH` 환경 변수를 사용하여 설정할 수 있습니다. 기본값은 `langflow/components`입니다.
- `--log-file`: 로그 파일의 경로를 지정합니다. `LANGFLOW_LOG_FILE` 환경 변수를 사용하여 설정할 수 있습니다. 기본값은 `logs/langflow.log`입니다.
- `--cache`: 사용할 캐시 유형을 선택합니다. 옵션은 `InMemoryCache`와 `SQLiteCache`입니다. `LANGFLOW_LANGCHAIN_CACHE` 환경 변수를 사용하여 설정할 수 있습니다. 기본값은 `SQLiteCache`입니다.
- `--dev/--no-dev`: 개발 모드를 토글합니다. 기본값은 `no-dev`입니다.
- `--path`: 개발 목적으로만 사용되는 프론트엔드 디렉터리의 경로를 지정합니다. `LANGFLOW_FRONTEND_PATH` 환경 변수를 사용하여 설정할 수 있습니다.
- `--open-browser/--no-open-browser`: 서버 시작 후 브라우저를 열지 여부를 토글합니다. `LANGFLOW_OPEN_BROWSER` 환경 변수를 사용하여 설정할 수 있습니다. 기본값은 `open-browser`입니다.
- `--remove-api-keys/--no-remove-api-keys`: 데이터베이스에 저장된 프로젝트에서 API 키를 제거할지 여부를 토글합니다. `LANGFLOW_REMOVE_API_KEYS` 환경 변수를 사용하여 설정할 수 있습니다. 기본값은 `no-remove-api-keys`입니다.
- `--install-completion [bash|zsh|fish|powershell|pwsh]`: 지정된 쉘에 대한 완성을 설치합니다.
- `--show-completion [bash|zsh|fish|powershell|pwsh]`: 지정된 쉘에 대한 완성을 표시하여 복사하거나 설치를 사용자 정의할 수 있습니다.
- `--backend-only`: 기본값이 `False`인 이 매개변수는 프론트엔드 없이 백엔드 서버만 실행할 수 있습니다. `LANGFLOW_BACKEND_ONLY` 환경 변수를 사용하여 설정할 수도 있습니다.
- `--store`: 기본값이 `True`인 이 매개변수는 스토어 기능을 활성화합니다. 비활성화하려면 `--no-store`를 사용하십시오. `LANGFLOW_STORE` 환경 변수를 사용하여 구성할 수도 있습니다.

이러한 매개변수는 Langflow의 동작을 사용자가 커스터마이즈해야 하는 경우에 특히 중요합니다. 특히 개발 또는 특수 배포 시나리오에서요.

### 환경 변수

많은 CLI 옵션을 환경 변수를 사용하여 구성할 수 있습니다. 이러한 환경 변수는 운영 체제에서 내보낼 수 있거나 `.env` 파일에 추가하여 `--env-file` 옵션을 사용하여 로드할 수 있습니다.

프로젝트에는 `.env.example`이라는 샘플 `.env` 파일이 포함되어 있습니다. 이 파일을 새 파일로 복사하여 `.env`로 이름을 바꾸고 예제 값 대신 실제 설정 값을 넣어주세요. 운영 체제와 `.env` 파일 양쪽에 값이 설정된 경우 `.env` 설정이 우선됩니다.

# 배포

## Google Cloud Platform(GCP)에 Langflow를 배포하세요.

우리의 단계별 가이드를 따라 Google Cloud Shell을 사용하여 Google Cloud Platform (GCP)에 Langflow를 배포하세요. 가이드는 [**Google Cloud Platform에서 Langflow**](GCP_DEPLOYMENT.md) 문서에서 확인할 수 있습니다.

또는 아래의 **"Cloud Shell에서 열기"** 버튼을 클릭하여 Google Cloud Shell을 실행하고, Langflow 리포지토리를 클론한 후 **인터랙티브 튜토리얼**을 시작하세요. 이 튜토리얼은 필요한 리소스를 설정하고 GCP 프로젝트에 Langflow를 배포하는 과정을 안내할 것입니다.

[![Open in Cloud Shell](https://gstatic.com/cloudssh/images/open-btn.svg)](https://console.cloud.google.com/cloudshell/open?git_repo=https://github.com/langflow-ai/langflow&working_dir=scripts/gcp&shellonly=true&tutorial=walkthroughtutorial_spot.md)

## Railway에 배포하기

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/JMXEWp?referralCode=MnPSdg)

## Render에 배포하기

<a href="https://render.com/deploy?repo=https://github.com/langflow-ai/langflow/tree/main">
<img src="https://render.com/images/deploy-to-render-button.svg" alt="Deploy to Render" />
</a>

# 👋 기여하기

모든 수준의 개발자들이 GitHub의 오픈 소스 프로젝트에 기여하는 것을 환영합니다. 기여하고 싶다면 [기여 가이드라인](./CONTRIBUTING.md)을 확인하고 Langflow를 더욱 접근 가능하게 만드는 데 도움을 주시기 바랍니다.

---

[![Star History Chart](https://api.star-history.com/svg?repos=langflow-ai/langflow&type=Timeline)](https://star-history.com/#langflow-ai/langflow&Date)

# 🌟 기여자들

[![langflow contributors](https://contrib.rocks/image?repo=langflow-ai/langflow)](https://github.com/langflow-ai/langflow/graphs/contributors)

# 📄 라이선스

Langflow는 MIT 라이선스로 배포됩니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.
