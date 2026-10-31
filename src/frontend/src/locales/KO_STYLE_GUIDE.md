# Langflow 한국어 번역 스타일 가이드

한국어 번역 파일 두 개에 적용한다.

- 프론트엔드: `src/frontend/src/locales/ko.json` (버튼, 메뉴, 안내문, 오류)
- 백엔드: `src/backend/base/langflow/locales/ko.json` (컴포넌트 설명, 필드 도움말, 템플릿 설명과 메모)

문구를 추가하거나 고칠 때는 이 문서를 먼저 읽는다.

## 1. 톤

**용어는 영어, 문장은 한국어.** Langflow의 제품 용어는 영어로 두고, 그 밖의 말은 자연스러운 한국어로 쓴다.
영어 문서와 튜토리얼에 나오는 용어가 화면에 그대로 보이므로 찾아보기 쉽고, 문장은 한국어라 개발자가 아니어도 읽힌다.

```
Create first flow            → 첫 Flow 만들기
Configure Model Providers    → Model Provider 설정
Flow not found               → Flow를 찾을 수 없습니다
Let us set things up first   → 먼저 기본 설정부터 할게요
```

**가장 중요한 기준은 번역투를 남기지 않는 것이다.** 영어 문장을 옮기지 않는다.
그 화면에서 그 순간 사용자에게 무엇을 알려야 하는지 파악한 뒤, 처음부터 한국어로 만든 앱이라면 뭐라고 썼을지를 쓴다.
4절에 자주 나오는 번역투와 고친 문장을 실었다.

## 2. 용어집

### 영어로 두는 용어

Langflow 문서에 라벨로 나오는 제품 개념어와, 정착된 한국어가 없는 AI 용어다. 대소문자도 아래 표기를 따른다.

| 분류 | 용어 |
|---|---|
| 제품 | Langflow, Langflow Store, Langflow Assistant, Assistant, Playground, Bundles, Starter Project |
| 핵심 개념 | Flow, Component, Custom Component, Agent, Template, Prompt, Tool, Tool Mode, Freeze, Global Variable, Trace |
| 모델 | Model, Model Provider, Provider, LLM, Embedding, Token, Temperature |
| 지식 | Knowledge, Knowledge Base, Vector Store, Chunk |
| 연동 | MCP, MCP Server, API, API Key, Webhook, A2A, cURL |
| 배포 단계 | Draft, Live |
| 자료형 | Data, DataFrame, Message, JSON, URL, ID, Session ID |
| 그 밖에 | 모든 컴포넌트 이름(Chat Input, Agent, URL 등)과 필드 이름(Language Model, Agent Instructions 등), 회사와 서비스 이름 |

복수형은 단수로 쓴다 (`Flows` → `Flow`, `Components` → `Component`). 단 메뉴 이름으로 굳은 `Bundles`는 그대로 둔다.

### 한국어로 옮기는 말

이미 정착된 일반 소프트웨어 용어다. 같은 영어 낱말은 항상 같은 한국어로 옮긴다.

| 영어 | 한국어 | 영어 | 한국어 |
|---|---|---|---|
| Save | 저장 | Settings, Configure | 설정 |
| Delete | 삭제 | Remove | 제거 |
| Create, New | 만들기, 새 | Add | 추가 |
| Edit | 편집 | Update | 업데이트 |
| Copy / Duplicate / Paste | 복사 / 복제 / 붙여넣기 | Import / Export | 가져오기 / 내보내기 |
| Upload / Download | 업로드 / 다운로드 | Search / Filter / Sort | 검색 / 필터 / 정렬 |
| Share / Shared | 공유 / 공유됨 | Public / Private | 공개 / 비공개 |
| Run | 실행 | Build | 빌드 |
| Deploy, Deployment | 배포 | Publish | 게시 |
| Input / Output | 입력 / 출력 | Field / Value / Type | 필드 / 값 / 유형 |
| Project / Folder / File | 프로젝트 / 폴더 / 파일 | Session / Version / History | 세션 / 버전 / 기록 |
| Node / Canvas | 노드 / 캔버스 | Memory | 메모리 |
| Server / Client | 서버 / 클라이언트 | Environment variable | 환경 변수 |
| Variable | 변수 | Default | 기본값, 기본 |
| Enable / Disable | 켜기 / 끄기 | Enabled / Disabled | 켜짐 / 꺼짐 |
| Expand / Collapse | 펼치기 / 접기 | Lock / Unlock | 잠금 / 잠금 해제 |
| Undo / Redo | 실행 취소 / 다시 실행 | Restore / Revert | 복원 / 되돌리기 |
| Cancel / Confirm / Close | 취소 / 확인 / 닫기 | Back / Next / Continue / Done | 뒤로 / 다음 / 계속 / 완료 |
| Error / Warning | 오류 / 경고 | Status / Details | 상태 / 자세히 |
| Permission / Access | 권한 / 접근 | User / Admin / Owner | 사용자 / 관리자 / 소유자 |
| Sign in, Log in / Sign out | 로그인 / 로그아웃 | Sign up | 가입 |
| Password / Username | 비밀번호 / 사용자 이름 | Authentication / Credentials | 인증 / 인증 정보 |
| Message / Chat | 메시지 / 채팅 | Code / Log | 코드 / 로그 |
| Shortcut | 단축키 | Zoom in / Zoom out | 확대 / 축소 |
| Ingestion, Ingest | 수집 | Inspect | 보기, 확인 |
| Metadata / Index / Collection | 메타데이터 / 인덱스 / 컬렉션 | Database / Table / Column / Row | 데이터베이스 / 테이블 / 열 / 행 |
| Table (글 안의 표) | 표 | Table (Langflow 입력 타입) | Table |
| Endpoint | 엔드포인트 | Query | 검색어 (DB 문맥이면 쿼리) |
| Required / Optional | 필수 / 선택 사항 | String / Number / Boolean | 문자열 / 숫자 / 참거짓 |

### 번역하면서 확정한 말

| 영어 | 한국어 | 영어 | 한국어 |
|---|---|---|---|
| edge | 연결선 | connection | 연결 |
| refresh | 새로 고침, 새로 고치다 | reset | 초기화 |
| generate | 생성 | replace (이미 있는 것을 바꿀 때), override | 덮어쓰기 |
| preview | 미리보기 | details (명사) | 세부 정보 |
| Read-Only | 읽기 전용 | Untitled Flow | 이름 없는 Flow |
| dictionary | 딕셔너리 | parameter | 매개변수 |
| key combination | 키 조합 | local storage | 로컬 저장소 |
| snapshot | 스냅샷 | outdated | 최신 버전이 아닌 |
| file type | 파일 형식 | required fields | 필수 필드 |
| Can view / Can edit / Can run | 보기 가능 / 편집 가능 / 실행 가능 | Viewer / Editor | 보기 권한 / 편집 권한 |
| Human in the Loop | Human in the Loop (제목), 본문에서는 `사람의 확인` | human input | 사람의 입력 |
| traceback, Python, import | 영어 그대로 | Model Component | 영어 그대로 |

사이드바의 분류 이름은 일반 낱말은 한국어로, 제품 용어는 영어로 쓴다.
`Flow Control`의 Flow는 제품 용어가 아니라 실행 흐름(조건, 반복)을 뜻하므로 `흐름 제어`로 옮긴다.

| Input & Output | Data Sources | Models & Agents | LLM Operations | Files & Knowledge | Processing | Flow Control | Utilities |
|---|---|---|---|---|---|---|---|
| 입력과 출력 | 데이터 소스 | Model과 Agent | LLM 작업 | 파일과 Knowledge | 처리 | 흐름 제어 | 유틸리티 |

### 영어 용어 뒤의 조사

발음을 기준으로 붙인다.

| 받침 없음 (를, 가, 는, 와, 로) | 받침 있음 (을, 이, 은, 과, 으로) |
|---|---|
| Flow, Agent, Component, Playground, Provider, Prompt, Trace, Store, MCP, API, API Key, Knowledge Base, Memory Base, Vector Store, Data, Message, Draft, Live, MCP Server, Chunk, Bundles, Assistant, Freeze, Tool Mode | Model, Tool, Template, Embedding, Token, Webhook, Global Variable, JSON, URL, LLM, DataFrame, Span, Action |

`Model`, `Tool`, `URL`, `Global Variable`처럼 ㄹ 받침으로 끝나면 `으로`가 아니라 `로`를 쓴다 (`Model로`, `Tool로`, `URL로`).

## 3. 문체

| 자리 | 어미 | 예 |
|---|---|---|
| 버튼, 메뉴, 탭, 표 머리말 | 명사형 또는 `~하기` | `저장`, `첫 Flow 만들기`, `파일 업로드` |
| 진행 상태 | `~ 중...` | `저장 중...`, `불러오는 중...` |
| 완료 알림 | `~했습니다` | `Flow를 저장했습니다` |
| 실패 알림 | `~하지 못했습니다` | `파일을 업로드하지 못했습니다` |
| 상태 설명 | `~습니다`, `~입니다` | `Flow를 찾을 수 없습니다` |
| 안내, 지시 | `~하세요` | `Model Provider를 추가하세요` |
| 확인 질문 | `~할까요?` | `이 파일을 삭제할까요?` |
| 비어 있는 상태 | `~가 없습니다`, `~ 없음` | `세션이 없습니다`, `데이터 없음` |
| 환영, 안내 제목 | 부드러운 말투 허용 | `먼저 기본 설정부터 할게요` |
| 필드 도움말: 컴포넌트가 하는 일 | `~합니다`, `~입니다` | `켜면 Agent에 계산기 Tool을 추가합니다.` |
| 필드 도움말: 사용자가 할 일 | `~하세요` | `라벨 ID를 쉼표로 구분해 입력하세요.` |

- 원문에 마침표가 있으면 붙이고, 없으면 붙이지 않는다.
- 원문이 Title Case여도 한국어에는 해당 없다. 영어로 두는 용어만 2절 표기를 따른다.
- 한 화면 안에서 `~습니다`와 `~어요`를 섞지 않는다. 기본은 `~습니다`다.

## 4. 번역투 금지

아래는 이 제품의 실제 원문과, 흔히 나오는 번역투, 고친 문장이다. **가운데 열처럼 쓰면 안 된다.**

| 영어 원문 | 번역투 (금지) | 한국어 |
|---|---|---|
| File uploaded successfully | 파일이 성공적으로 업로드되었습니다 | 파일을 업로드했습니다 |
| Changes saved successfully | 변경 사항이 성공적으로 저장되었습니다 | 변경 사항을 저장했습니다 |
| {{type}} duplicated successfully | {{type}}이(가) 성공적으로 복제되었습니다 | {{type}} 복제 완료 |
| {{count}} sessions deleted successfully | {{count}}개의 세션들이 성공적으로 삭제되었습니다 | 세션 {{count}}개를 삭제했습니다 |
| Failed to load knowledge bases | 지식 베이스 로드에 실패했습니다 | Knowledge Base를 불러오지 못했습니다 |
| Failed to add MCP server. | MCP 서버 추가에 실패했습니다. | MCP Server를 추가하지 못했습니다. |
| Error uploading file | 파일 업로드 중 오류 발생 | 파일을 업로드하지 못했습니다 |
| Error on delete user | 사용자 삭제 시 오류 | 사용자를 삭제하지 못했습니다 |
| Something went wrong, please try again | 무언가 잘못되었습니다, 다시 시도해 주십시오 | 문제가 생겼습니다. 다시 시도하세요 |
| There is an error in your function | 당신의 함수에 오류가 있습니다 | 함수에 오류가 있습니다 |
| Oops! Looks like you missed something | 이런! 무언가를 놓치신 것 같습니다 | 빠뜨린 항목이 있습니다 |
| Are you sure you want to delete "{{name}}"? | 정말로 "{{name}}"을(를) 삭제하시겠습니까? | "{{name}}" 파일을 삭제할까요? |
| Are you sure you want to exit without saving your changes? | 변경 사항을 저장하지 않고 종료하시겠습니까? | 변경 사항을 저장하지 않고 나갈까요? |
| This action cannot be undone. The file will be permanently deleted. | 이 작업은 실행 취소할 수 없습니다. 파일이 영구적으로 삭제됩니다. | 삭제한 파일은 되돌릴 수 없습니다. |
| Unsaved changes will be permanently lost. | 저장되지 않은 변경 사항은 영구적으로 손실됩니다. | 저장하지 않은 변경 사항은 사라집니다. |
| No compatible components found. | 호환 가능한 컴포넌트가 발견되지 않았습니다. | 연결할 수 있는 Component가 없습니다. |
| No Data Available | 사용 가능한 데이터 없음 | 데이터 없음 |
| No sessions yet. | 아직 세션이 없습니다. | 세션이 없습니다. |
| No microphone found. Please connect a microphone and try again. | 마이크가 발견되지 않았습니다. 마이크를 연결하고 다시 시도해 주십시오. | 마이크가 없습니다. 마이크를 연결한 뒤 다시 시도하세요. |
| Please upload a JSON file | JSON 파일을 업로드해 주시기 바랍니다 | JSON 파일을 업로드하세요 |
| The file size is too large. Please select a file smaller than {{maxSizeMB}}. | 파일 크기가 너무 큽니다. {{maxSizeMB}}보다 작은 파일을 선택해 주십시오. | 파일이 너무 큽니다. {{maxSizeMB}} 미만인 파일을 선택하세요. |
| Delete {{count}} sessions | {{count}}개의 세션들 삭제 | 세션 {{count}}개 삭제 |
| Create your prompt. Prompts can help guide the behavior of a Language Model. Use curly brackets {} to introduce variables. | 당신의 프롬프트를 생성하십시오. 프롬프트는 언어 모델의 행동을 안내하는 것을 도울 수 있습니다. 변수를 도입하기 위해 중괄호 {}를 사용하십시오. | Prompt를 작성하세요. Prompt는 Language Model이 어떻게 답할지 방향을 잡아 줍니다. 변수는 중괄호 {} 안에 넣으세요. |
| Adjust component's settings and define parameter visibility. Remember to save your changes. | 컴포넌트의 설정을 조정하고 매개변수 가시성을 정의하십시오. 변경 사항을 저장하는 것을 기억하십시오. | Component 설정을 바꾸고 어떤 항목을 노드에 보일지 정합니다. 바꾼 뒤에는 저장하세요. |

### 규칙

1. **사용자를 부르지 않는다.** `당신`, `귀하`, `사용자님`을 쓰지 않고 주어를 생략한다. your는 빼거나 `내`로 옮긴다.
2. **앱이 자기를 부르지 않는다.** `우리`, `저희`를 쓰지 않는다.
3. **successfully, please는 옮기지 않는다.** `성공적으로`는 쓰지 않는다. 성공은 `~했습니다`가, 공손함은 `~하세요`가 이미 담고 있다.
4. **실패는 `~하지 못했습니다`다.** `~에 실패했습니다`, `~하는 중 오류가 발생했습니다`로 쓰지 않는다.
5. **확인 질문은 `~할까요?`다.** `정말로`, `~하시겠습니까`를 쓰지 않는다.
6. **지시는 `~하세요`다.** `~하십시오`, `~해 주시기 바랍니다`를 쓰지 않는다.
7. **개수는 `세션 3개`다.** `3개의 세션`으로 쓰지 않는다. 사물에는 복수 `들`을 붙이지 않는다.
8. **감탄사를 옮기지 않는다.** Oops, Whoops, Yay, Hooray는 지운다. 느낌표도 옮기지 않는다.
9. **피동보다 능동.** `저장되었습니다`보다 `저장했습니다`. 저절로 일어난 일(`연결이 끊겼습니다`)은 피동이 자연스러우니 둔다.
10. **무생물 주어를 풀어 쓴다.** `이 설정은 ~을 허용합니다`가 아니라 `이 설정을 켜면 ~할 수 있습니다`.
11. **조건, 시간, 이유를 앞에 둔다.** `저장하세요, 떠나기 전에`가 아니라 `떠나기 전에 저장하세요`.
12. **쓰지 않는 말.** `하나의`, `각각의`, `~하기 위해`(→ `~하려면`), `A를 위한 B`(→ `A B`), `~에 대한`, `~을 통해`, `~로부터`,
    `~에 의해`, `~함으로써`, `~할 필요가 있다`(→ `~해야 한다`), `만약`, `유효하지 않은`(→ `올바르지 않은`, `형식이 맞지 않습니다`),
    `사용 가능한`(→ 대개 지운다), `로드`, `로딩`(→ `불러오기`, `불러오는 중`), `요구됩니다`(→ `입력하세요`, `필수입니다`).
13. **상투적인 수식어를 쓰지 않는다.** `다양한`, `혁신적인`, `강력한`, `원활한`, `손쉽게`, `효율적으로`. 원문에 있어도 뜻이 비어 있으면 뺀다.
14. **금지 문자.** em대시(`—`)와 en대시(`–`), 가운뎃점(`·`)은 쓰지 않는다. 원문의 em대시는 쉼표, 마침표, 괄호, 콜론으로 바꾼다
    (`Connection successful — {{message}}` → `연결했습니다. {{message}}`, `{{name}} — {{owner}}` → `{{name}} ({{owner}})`).
    말줄임표(`…`, `...`)는 원문과 같은 것을 쓴다.
15. **영어 약어를 옮긴다.** `e.g.` → `예:`, `i.e.` → `즉`, `etc.` → `등`.
16. **영어보다 길어지지 않게 쓴다.** 버튼과 표 머리말의 폭은 영어 길이에 맞춰져 있다.
17. **사용자가 할 일은 `~하세요`로 쓴다.** 도움말이 입력하거나 고르라고 말하는 자리에서 `쉼표로 구분해 입력합니다`처럼 평서문으로 끝내지 않는다.
    컴포넌트가 하는 일(`켜면 출력에 메타데이터를 함께 넣습니다`)만 평서문으로 쓴다.
18. **뜻 없이 덧붙인 말을 뺀다.** `자세히 살펴봅니다`는 `봅니다`, `깔끔한 요약본으로 엮습니다`는 `요약본으로 정리합니다`로 쓴다.
19. **`실수`는 쓰지 않는다.** float는 `소수`로 옮긴다. `실수를 입력하세요`는 잘못을 입력하라는 말로 읽힌다.

## 5. 변수, 복수형, 태그, 문장 조각

### 변수 `{{name}}`

- 변수의 이름과 개수는 원문과 똑같아야 한다. 이름을 번역하거나 빼먹으면 테스트가 실패한다.
- **받침에 따라 바뀌는 조사는 변수 바로 뒤에 붙이지 않는다.** 을/를, 이/가, 은/는, 와/과, 로/으로가 그렇다.
  들어올 값의 받침을 알 수 없다. `{{name}}을(를)` 같은 병기도 쓰지 않는다.
- 피하는 방법은 세 가지다.
  1. 변수 뒤에 그것이 무엇인지 알려 주는 명사를 붙이고 조사는 그 명사에 붙인다: `"{{name}}" 파일을 삭제할까요?`
  2. 명사형으로 끝낸다: `{{type}} 복제 완료`, `{{name}} 삭제`
  3. 콜론 뒤로 보낸다: `캔버스에 추가: {{name}}`
- 받침과 상관없는 조사는 붙여도 된다: 에, 에서, 의, 도, 만, 까지, 부터 (`{{client}}에 설치하지 못했습니다`).
- 숫자 변수는 단위 명사를 붙이면 해결된다: `세션 {{count}}개를`, `{{count}}분 전`.

### 복수형 키 (`_one`, `_other`)

한국어에는 복수 구분이 없지만 두 키를 모두 넣어야 테스트를 통과한다. 두 키에 같은 문장을 넣는다.

### 태그

`playground.noInputHint`의 `<1>Chat Input</1>`처럼 숫자 태그가 있으면 여는 태그와 닫는 태그를 짝 맞춰 그대로 둔다.
태그 안의 컴포넌트 이름은 영어로 둔다.

### 문장 조각

링크나 아이콘을 사이에 두고 문장을 둘로 쪼갠 키가 있다 (`crash.descriptionBefore` = `Please report errors with detailed tracebacks on the`).
전치사나 관사로 끝나거나 소문자로 시작하면 조각이다. 이런 키는 **쓰이는 코드를 찾아 앞뒤 조각과 어떤 순서로 붙는지 확인한 뒤**,
이어 붙였을 때 한국어 어순이 되도록 나눠 쓴다. 빈 문자열은 넣을 수 없다. 빈 값은 영어로 되돌아간다.

낱말 하나짜리 키(`Key`, `Run`, `Set`, `Clear`, `Save`)도 뜻이 여럿이면 쓰이는 자리를 확인한 뒤 옮긴다.

## 6. 백엔드 번역 파일

노드 안에 보이는 글자다. **이름은 영어로 두고 설명만 한국어로 옮긴다.**

| 키 종류 | 처리 |
|---|---|
| `display_name` (컴포넌트, 필드, 출력 이름) | **넣지 않는다.** 키가 없으면 영어 원문이 나온다 |
| `starter_flows.*.name` (템플릿 이름) | **넣지 않는다** |
| `description` (컴포넌트 설명) | 한국어 |
| `info` (필드 도움말) | 한국어 |
| `placeholder` | 안내 문구면 한국어, 예시 입력값이면 그대로 |
| `starter_flows.*.description` | 한국어 |
| `template_notes.*` (템플릿 메모) | 한국어. 마크다운 구조는 그대로 |

- 키에는 영어 원문의 해시가 들어 있다 (`components.agent.description.c4a4ee71`). **키는 복사만 하고 고치지 않는다.**
- 같은 영어 문장은 어느 컴포넌트에서든 같은 한국어로 옮긴다.
- 설명문 안에서 다른 필드나 컴포넌트를 가리키는 이름은 영어로 둔다. 화면에 영어로 보이기 때문이다.
- 템플릿 메모의 `**Model Provider**`, `**Playground**`처럼 굵게 쓴 말은 화면의 라벨이니 영어로 둔다.
  제목(`#`), 목록, 링크, 코드, 이모지는 원문 그대로 둔다.
- `{current_date}`처럼 중괄호가 하나인 말은 Prompt 변수 표기다. 그대로 둔다.

### 자주 나오는 문형

| 영어 | 한국어 |
|---|---|
| If true, adds a calculator tool to the agent. | 켜면 Agent에 계산기 Tool을 추가합니다. |
| If True, disables streaming responses. Useful for batch processing. | 켜면 응답을 스트리밍하지 않습니다. 일괄 처리에 알맞습니다. |
| Whether to clean data before converting to string. | 문자열로 바꾸기 전에 데이터를 정리할지 정합니다. |
| Whether the agent is allowed to execute code. | Agent가 코드를 실행해도 되는지 정합니다. |
| The message to send to the agent. | Agent에 보낼 메시지입니다. |
| Overrides global provider settings. Leave blank to use your pre-configured API Key. | 여기에 입력하면 전체 Provider 설정보다 우선합니다. 비워 두면 미리 설정해 둔 API Key를 씁니다. |
| Endpoint of the Anthropic API. Defaults to 'https://api.anthropic.com' if not specified. | Anthropic API의 엔드포인트입니다. 지정하지 않으면 'https://api.anthropic.com'을 씁니다. |
| Optional dictionary of filters to apply to the search query. | 검색에 적용할 필터입니다. 선택 사항이며 딕셔너리 형식으로 입력하세요. |
| Comma-separated list of label IDs to filter emails. | 이메일을 필터링할 라벨 ID를 쉼표로 구분해 입력하세요. |
| Stream the response from the model. Streaming works only in Chat. | Model의 응답을 스트리밍합니다. Chat에서만 동작합니다. |
| Fetch content from one or more web pages, following links recursively. | 웹 페이지에서 내용을 가져옵니다. 페이지 안의 링크도 따라가며 수집합니다. |
| Define the agent's instructions, then enter a task to complete using tools. | Agent의 지침을 정한 뒤, Tool을 써서 수행할 작업을 입력하세요. |
| Get chat inputs from the Playground. | Playground에서 채팅 입력을 받습니다. |
| Setup Provider | Provider 설정 |
| Enter a URL... | URL 입력... |
| e.g., .properties.id | 예: .properties.id |

도움말에서 되풀이되는 말은 아래로 통일한다.

| 영어 | 한국어 | 영어 | 한국어 |
|---|---|---|---|
| (X only) | (X 전용) | (shown only when X is selected) | X를 선택했을 때만 보입니다. |
| Number of results to return | 가져올 결과 수 | ... to pass to the model | Model에 전달할 ... |
| timeout | 제한 시간(초) | base URL | 기본 URL |
| structured output | 구조화된 출력 | schema | 스키마 |
| instructions | 지침 | mock data, synthetic data | 가상 데이터 |
| auth token | 인증 Token | access key / secret key | 액세스 키 / 비밀 액세스 키 |
| temporary credentials | 임시 인증 정보 | region | 리전 |
| redirect | 리다이렉트 | keyword arguments | 키워드 인자 |
| insert | 삽입 | JSON list | JSON 배열 |
| keyspace | 키스페이스 | similarity search | 유사도 검색 |

- 컴포넌트 설명은 영어가 명령형(`Fetch content...`)이어도 한국어는 `~합니다`로 쓴다.
- `WARNING:`, `Note:`는 `주의:`, `참고:`로 옮긴다.
- `deprecated`는 `더 이상 지원하지 않습니다`로 옮긴다.

## 7. 검사

```bash
# 구조 검사: 키 누락, 변수와 태그 불일치, 용어집 위반
uv run python scripts/i18n/check_ko.py

# 키 일치 테스트 (프론트엔드)
cd src/frontend && npx jest src/locales/__tests__/locale-parity.test.ts
```

스크립트가 통과해도 번역투가 없다는 뜻은 아니다. 무생물 주어, 피동 남발, 영어식 어순은 기계로 잡히지 않는다.
번역한 뒤에는 원문을 보지 않고 한국어만 소리 내어 읽어 보고, 입에서 안 나올 문장을 고친다.
