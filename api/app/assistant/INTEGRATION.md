# 개인화 AI 챗봇 연동

> **서비스 연결 현황(2026-11-23)** — 아래 계약은 `service_data.py`(실제 프로필·공고 DB·스킬트리·Postgres 저장소)와 `wiring.py`(main.py 연결, 시연 계정, 웹 규칙 엔진 추천 공고 전달)로 구현했다. 패키지 버전은 `api/requirements.txt` 한 곳에서 관리하고 Dockerfile은 고치지 않는다. 웹 화면은 `web/src/components/Assistant.tsx`. 아래의 설치·Dockerfile 단계 설명은 연결 전 기록이다.

개인화 상담과 지원서 기능은 `api/app/assistant/`에서 제공한다. 기존 세션 쿠키를 사용하는 전용 `/api/assistant` 라우터를 FastAPI에 등록하면 된다. 공고 상세의 `/api/chat`은 기존 `oppId`·`question` 입력과 `text`·`citations`·`held` 출력을 유지한다.

## 백엔드 설치와 라우터 등록

저장소 루트에서 `python -m pip install -r api/requirements.txt -r api/app/assistant/requirements.txt`로 설치한다.

1. 컨테이너의 [api/Dockerfile 3~5행](../../Dockerfile#L3-L5)에서 설치 전에 어시스턴트 requirements도 복사한다. 기존 `COPY requirements.txt .` 다음에 `COPY app/assistant/requirements.txt ./assistant-requirements.txt`를 추가하고, pip 설치 인수에 `-r assistant-requirements.txt`를 추가한다.
2. `CareerData`, `AssistantStore` 계약을 구현한 어댑터와 서버 모델 설정을 구성한다. 코드 예시의 `career_data`, `assistant_store`, `settings`는 이 단계에서 생성한다. 현재 `main.py`에 이 객체들은 정의되어 있지 않다.
3. [api/app/main.py 262~268행](../main.py#L262-L268)의 기존 공고·프로세스 라우터 등록 바로 아래, `purge_expired` 미들웨어 위에 다음 코드를 넣는다. `make_assistant_router` 별칭을 사용하면 기존 공고 라우터의 `make_router` 이름과 구분된다. [117행의 `current_user`](../main.py#L117)와 같은 앱을 사용한다.

```python
from .assistant.model import GeminiModel
from .assistant.router import make_router as make_assistant_router
from .assistant.service import AssistantService

assistant = AssistantService(
    data=career_data,
    store=assistant_store,
    model=GeminiModel(settings.gemini_api_key, settings.gemini_model, timeout=8),
)
app.include_router(make_assistant_router(current_user, assistant))
```

4. 로컬 서버를 확인할 때 `api`에서 `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`으로 시작한다. `/openapi.json`에서 `/api/chat`과 `/api/assistant/chat`이 모두 있는지 확인한다. 기존 로그인 후 `/api/me`와 어시스턴트 라우트를 같은 브라우저 세션으로 호출한다.

### 계정과 세션

기존 `POST /api/auth/signup`과 `POST /api/auth/login`은 `cuk_session` 쿠키를 발급한다. 회원가입은 비밀번호를 Argon2 해시로 저장하고, 로그인은 입력값을 그 해시와 검증한다. 세션 토큰은 `HttpOnly`, `SameSite=Lax`, `Path=/` 쿠키로 전달하고, `COOKIE_SECURE=1`이면 `Secure`를 추가한다. 세션은 14일 뒤 만료되며, 서버는 토큰의 SHA-256 해시를 `sessions` 테이블에서 조회한다. 어시스턴트는 `Depends(current_user)`가 검증한 `User.id`로 기억·대화·문서에 접근한다. `POST /api/auth/logout`은 서버 세션 행을 삭제하고 브라우저 쿠키를 지운다. [세션 발급](../main.py#L108-L124) · [로그인과 로그아웃](../main.py#L147-L190)

로컬 가상 시연은 `MockCareerData({"logged-in-demo-user": "demo001"})`와 `JsonAssistantStore(Path("<전용 로컬 데이터 디렉터리>"))`를 사용한다. 로그인 ID와 가상 학생 ID의 대응을 명시해야 하며, 등록하지 않은 계정에 가상 학생 프로필을 배정하지 않는다. CLI는 `api`에서 `python -m app.assistant.service --user demo001 --store <전용_로컬_디렉터리>`로 실행한다. 접속에 필요한 설정은 실행 환경에서 공급한다. 실행할 때마다 새 대화 ID를 만들며, 동일한 저장소와 사용자에서 장기 기억을 불러온다. `--conversation-id <대화ID>`로 이전 대화를 이어갈 수 있다. 업데이트 전 CLI 대화는 `--conversation-id default`로 열 수 있다. 저장소를 지정하지 않으면 시스템 임시 디렉터리 아래의 `cuk-career-ai-assistant-dev`를 사용한다. 기존 개발용 JSON을 옮길 때는 `--import-legacy app/assistant`를 사용한다. 가져오기는 지정한 한 사용자의 기록을 새 저장소에 복사한다.

### 실제 데이터 담당자에게 필요한 계약

| 제공 함수 | 받을 값 |
|---|---|
| `CareerData.get_profile(user_id)` | `Profile` 및 `Fact[]`. 학과, 학년, 학적, 학력, 교육, 기술, 프로젝트, 근무·인턴, 활동·수상, 관심사, 목표 및 자격증. 안정적인 기록 ID, 유형, 표기값, 등록 또는 공식 검증 출처가 필요하다. 확인된 취득일과 기록 참조는 `date`, `reference`로 준다. |
| `get_opportunity(id)`, `list_opportunities()` | `Opportunity`. 공고 ID, 채용·창업 구분, 제목·기관·원문 설명, 시간대가 있는 마감 시각, 구조화 조건, 필요 서류, 최신 원문 링크와 버전. 동일한 ID를 기존 `Posting`과 이어준다. 가상 여부를 `mock`으로 규정한다. |
| `get_skill_node(job_id, skill_id)` | `SkillNode`. 웹 카탈로그와 같은 직무·스킬 ID, 표시명, 설명, 선수학습, 학습 항목. 관리자가 카탈로그를 수정한 경우 화면과 동일한 버전을 조회한다. |
| `get_skill_tree(job_id)`, `list_career_roles()` | 선택 구현인 `CatalogCareerData` 계약. 직무별 `SkillTree`와 직무명·업무 설명·관심사 태그가 담긴 `CareerRole`을 제공한다. 기존 노드 단건 어댑터도 사용할 수 있다. |
| `AssistantStore.get_state`, `save_state` | 사용자 ID로 범위를 제한하고 같은 `revision`에서만 기억과 대화, 대화 중 갱신한 초안을 한 트랜잭션으로 저장한다. `PostgreSQL`에서는 버전 비교 또는 행 잠금과 사용자 ID를 포함한 키를 사용한다. |
| `create_document`, `get_document`, `get_original`, `save_draft` | 소유자 ID와 문서 ID로 범위를 제한한다. 원본 바이트는 불변이며, `save_draft`는 초안 리비전을 비교한다. 객체 저장소를 쓸 경우 원본 쓰기가 확인된 후 메타데이터를 공개한다. |

서버의 `source`는 `system`(시스템 등록), `official`(기관 검증), `conversation`(대화 중 사용자 진술), `user_claim`(기억 편집에서 입력한 진술)이다. `Profile.mock=true`인 프로필의 등록·공식 기록은 가상 시연용이다. 모델에는 이를 일반 등록, 기관 검증, 사용자 진술과 구별해 전달한다. 가상 프로필은 가상 공고에서만 판정 근거가 된다. 브라우저의 `User.state`는 자체 입력 자료다. 실제 `official`은 발급 기관이나 학교가 검증한 내역에만 부여한다. 자격증은 공식 확인 기록만 자동 입력하며 미취득·준비 중인 자격증은 취득 필드에서 제외한다. 이름·연락처는 Gemini에 전달하지 않는다.

프로필은 원본 등록 정보이며, 장기 기억은 사용자가 수정·삭제할 수 있는 진술이다. 전공·학년·진로 목표가 다르면 정정을 요청하고, 명시적 변경을 저장하면 상담에 반영한다. 기존 프로필은 변경 권한을 가진 원본 시스템에서 관리한다. `Fact.progress`는 `preparing`(준비/학습 중), `completed`(취득/완료 진술), `not_held`(미취득 진술), `beginner`(초급 진술), `intermediate`(중급 진술)이다. 값이 없는 기존 기록도 읽는다. 자격증은 처음 준비 중이라고 기록하거나 기존 취득 진술을 같은 기억 ID에서 정정할 수 있다. 학습 가능 시간은 `study_time` 기억으로 저장하며 학습 일정은 상담 답변으로 제안한다.

프로젝트나 근무 경험이 없다는 명시적인 본인 진술도 `not_held`로 저장한다. 이후 문서의 수행 경험에는 사용하지 않는다. 기억을 요청하면 새로 저장된 내용만 응답에 적고, 실제 저장이 끝난 요청에서 응답을 반환한다. 사용자가 직접 말한 역량이나 경험을 다시 묻는 경우에는 저장소에서 답변을 구성한다. 필요하면 직접 진술, 공식 확인 기록, 프로필 등록 정보, 가상 자료의 출처를 표시한다.

대화 이력은 참조와 화면 이동에 사용한다. 답변 생성 시 최근 6턴과 1,800자 이내 요약이 기준이며, 기억 후보가 있었던 턴은 과거 진술이 최신 기록처럼 재사용되는 것을 줄이기 위해 모델용 이력에서 제외한다. 사용자가 정한 예시 이름은 대화별로 최대 8개를 유지한다. 서버의 조회 이력은 대화당 최근 50턴을 제공하고, 동일 `requestId`의 재시도는 보관 중인 턴에 대해 같은 결과를 반환한다. 사용자별 장기 기억과 대화·문서 변경은 답변 생성 후 한 번에 저장한다.

조건은 `kind`와 허용 `values` 또는 `grade`의 `minimum`으로 표현한다. 값이 없거나 별도 판정이 필요한 조건은 `check`로 응답한다. 마감과 자격을 판단한 Python 결과가 답변과 API의 기준이다. 기존 웹 판정과 같은 조건의 결과가 일치하는지 확인한다.

### 스킬트리 카탈로그 어댑터

`skill_context.CatalogSkillData`는 팀 카탈로그의 `skills[]`와 `jobs[]`를 받아 스킬 조회용 구성 요소로 사용할 수 있다. `jobs[].nodes[]`의 `skill`, `prereq[]`, `required`를 읽고 기존 ID를 유지한다. 직무 설명은 `summary` 또는 `description`을 사용한다. `description`, `difficulty`, `importance`, `learningTopics`, `interests`는 제공되는 경우 상담에 반영한다. 실제 데이터 어댑터는 기존 프로필·공고 저장소와 이 구성 요소를 조합해 `get_skill_node`, `get_skill_tree`, `list_career_roles`로 노출할 수 있다.

간선은 선수 노드에서 그 기술을 사용하는 후속 노드를 향한다. 현재 선택, 직접 연결, 질문에 언급된 스킬을 우선해 최대 14개 노드와 32개 간선을 전달하고, 탐색 깊이를 방향별 4단계로 제한한다. 없는 ID와 자기 참조를 건너뛰고, 전체 그래프에서 순환을 먼저 찾은 뒤 순환에 속한 간선을 선수·후속 순서에서 제외한다. 결과가 부분 데이터인지 표시한다. 이전 이름 기반 선수학습 목록은 정확히 일치하는 이름이 하나일 때 연결할 수 있다.

현재 노드와 이전 노드가 모두 필요한 질문에는 상담에서 두 노드의 직무와 기술 ID를 조회한다. 직무 트리를 비교할 때 같은 기술 ID를 공통 기술로 사용하고, 간선은 각각의 직무 안에서 확인한다. 서버가 카탈로그 관계를 표시하고 Gemini가 필요한 경우 일반 학습 조언을 덧붙인다. 현재 사용자가 말한 학습 수준과 가능 시간은 상담에 사용하며, 가상 프로필과 사용자 진술의 출처는 유지한다.

### 로컬 스킬트리 실험실

`api` 디렉터리에서 다음 명령을 실행한다. 기본 카탈로그 `skill_lab_catalog.json`에는 AI 엔지니어 7개 노드와 데이터 엔지니어 8개 노드가 들어 있다. 실험실 사용자는 `mock_data.json`의 가상 프로필을 사용한다. 기존 챗봇은 같은 파일의 기본 상담용 카탈로그를 계속 읽는다.

```powershell
.\.venv\Scripts\python.exe -B -m app.assistant.skill_lab --plan
.\.venv\Scripts\python.exe -B -m app.assistant.skill_lab --catalog .\app\recommender\career_catalog.json --plan
.\.venv\Scripts\python.exe -B -m app.assistant.skill_lab --live --max-requests 12
```

`--plan`은 카탈로그를 읽어서 직무와 노드 수, 명령, 요청 상한을 표시한다. 첫 두 명령의 Gemini 요청은 0회다. `--live`는 환경에 설정된 `GEMINI_API_KEY`를 사용한다. 모델은 `--model` 또는 `GEMINI_MODEL`로 지정할 수 있다. `--catalog`를 `--live`에 함께 사용하면 다른 개발자의 export로 상담한다. 세션 상한의 기본값은 20회이며 기본 실험실에서는 자동 재시도를 수행하지 않는다. 선택 명령에는 모델 호출이 없고, 상담 턴은 경로에 따라 0~2회다. 세션에는 가상 입력만 사용한다.

```text
:users
:user demo001
:jobs
:job mock-ai-engineer
:nodes
:node mock-data-analysis
이 노드는 어떤 일을 배우는 거야?
선수학습과 후속 노드는 뭐야?
:node mock-pandas
아까 선택한 노드와 지금 노드는 어떻게 달라?
그럼 어떤 걸 먼저 배우는 게 좋아?
:job mock-data-engineer
:node mock-pipeline
다음 노드 중 어디부터 실습할까?
AI 엔지니어와 데이터 엔지니어의 스킬트리는 어떻게 달라?
:status
:quit
```

직무를 바꾸면 현재 노드가 해제된다. `:status`에서 다음 상담에 전달될 `jobId`와 `skillId`를 확인할 수 있다. 한 실행 안에서 같은 사용자의 대화가 이어지고, `:user`로 사용자별 선택과 기억을 전환한다. 이력과 기억은 실행별 임시 디렉터리에 저장하고 종료 시 정리한다.

기억을 확인하려면 “나는 Python 기초 문법은 어느 정도 알고 있지만, 실제 데이터 분석 프로젝트를 해본 적은 없어. 이 내용을 기억해줘.”를 한 줄로 입력한다. 저장 안내에 두 진술이 있는지 확인한 뒤 다른 직무와 노드를 선택한다. “내가 직접 말했던 Python 실력과 데이터 분석 프로젝트 경험을 각각 알려줘. 가상 사용자 데이터와 구분해줘.”에 저장된 진술과 상담용 가상 프로젝트 예시가 별도로 표시되는지 확인한다.

### 서비스에서 실제 카탈로그를 연결할 때 필요한 값

| 위치 | 필드와 의미 |
|---|---|
| `jobs[]` | 안정적인 직무 `id`, 표시 `name`, `summary` 또는 `description`, `nodes[]`, 선택 `interests[]` |
| `skills[]` | 안정적인 기술 `id`, 표시 `name`, `description`, `learningTopics[]`, `importance`, 선택 `difficulty` |
| `jobs[].nodes[]` | 기술 ID 참조 `skill`, 같은 직무 안의 선수 기술 ID 목록 `prereq[]`, 선택 `required`. 선수 기술이 없는 노드는 빈 배열을 제공한다. |
| 상담 요청 | `context.page=tree`와 화면의 `jobId`, 선택했다면 `skillId`. 화면을 옮길 때 같은 `conversationId`를 전달한다. |

어댑터는 직무와 기술 레코드에서 상담용 `jobId`, `skillId`, `skillName`을 구성한다. 실제 서비스 연결 시 사용할 카탈로그 버전과 검증 출처는 담당 시스템에서 관리한다. 실험실은 외부 JSON도 로컬 검증 자료로 취급한다.

## 프론트엔드 API

기본 경로는 `/api/assistant`다. 웹에서는 상대 URL과 기존 세션 쿠키를 사용한다. Next.js는 `/api/*`를 API 서버로 전달하므로 브라우저는 `credentials: "same-origin"`으로 요청하면 된다. 쿠키는 브라우저가 처리한다. 챗봇 API는 쿠키로 사용자를 결정하며 본문의 `userId`는 `422`로 거부한다. JSON 키는 camelCase다. 화면을 이동해도 `conversationId`를 유지하고 새 대화에는 새 ID를 사용한다. 생략하면 `default`다. `conversationId`, `requestId`, `context`의 화면·선택 ID는 영문·숫자로 시작하는 최대 80자의 식별자이며 이후 `.`, `_`, `-`도 허용한다.

| 메서드 및 경로 | 요청 | 성공 응답 |
|---|---|---|
| `POST /chat` | 앞뒤 공백을 제거한 `message` 1~2,000자, `conversationId`, `requestId`, `context`는 선택 | 200 `ChatResult` |
| `GET /conversations/{id}` | 이전 대화 ID | 200 `{conversationId, summary, messages}`. 각 메시지는 `{timestamp, message, result, context}` |
| `GET /memory` | 없음 | 200 `Fact[]` |
| `POST /memory` | `{kind, value, detail?, date?, progress?}` | 201 `Fact` |
| `PATCH /memory/{id}` | `{kind, value, detail?, date?, progress?}`로 해당 기억 교체 | 200 `Fact` |
| `DELETE /memory/{id}` | 없음 | 204 |
| `POST /documents?filename={name}` | 파일 바이트를 요청 본문으로 전송. PDF는 `application/pdf`, DOCX는 `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, JSON은 `application/json` | 201 `{id, filename, format, fields, warnings, draft}` |
| `GET /documents/{id}` | 없음 | 200 문서 정보와 최신 `draft` |
| `POST /documents/{id}/draft` | `{fieldIds?, narrativePrompt?, targetRole?, minCharacters?, maxCharacters?}`. 전체 자동 입력은 `{}` | 200 `Draft` |
| `PATCH /documents/{id}/draft` | `{revision, values: {"field-id": "새 초안 값"}}`. 빈 문자열은 필드를 비운다. | 200 `Draft` |
| `GET /documents/{id}/draft/download` | 없음 | 200 별도 초안 파일의 바이너리와 `Content-Disposition: attachment` |
| `POST /narrative` | `{topic, targetRole?, minCharacters?, maxCharacters?}` | 200 `{draft: DraftField, mockData}`로 독립적인 자기소개서 초안과 근거 반환 |

### 채팅 요청 및 응답

```json
{
  "conversationId": "career-demo-1",
  "requestId": "turn-1",
  "message": "이 노드의 선수학습은 뭔가요?",
  "context": {"page": "tree", "jobId": "mock-ai-engineer", "skillId": "mock-data-analysis"}
}
```

`context.page`는 `tree`, `home`, `opportunities`, `documents` 등 화면 식별자다. 실제 공고 화면은 `opportunityId`, 업로드 직후의 작성 요청은 `documentId`를 추가한다. 선택을 해제하면 `skillId`를 생략하고, 직무만 표시하는 화면이면 `jobId`를 보낸다. 현재 트리의 선택을 우선하며, 다른 화면에서 이전 스킬을 명시적으로 참조하면 같은 대화의 이전 선택을 보조 문맥으로 사용한다. 후속 공고·문서 질문도 같은 `conversationId`에서 문맥을 찾는다. `answer`는 일반 텍스트로 렌더링한다.

```json
{
  "answer": "선택한 데이터 분석 노드의 선수학습은 Python 기초예요.",
  "conversationId": "career-demo-1",
  "mockData": true,
  "memoryUpdated": false,
  "needsConfirmation": [],
  "contextIssues": [],
  "opportunities": [],
  "document": null
}
```

`contextIssues`에는 `unknown_skill`, `missing_skill_context`, `unknown_opportunity`, `no_matching_opportunity`를 보낼 수 있다. 유효한 공고 응답에는 공고별 `id`, `type`, `title`, `organization`, `description`, `deadline`, `open`, `conditions[{label, verdict, reason}]`, `documents`, `mock`, `sourceUrl`, `version`이 포함된다. `mock`으로 표시된 공고에는 가상 표시를 붙인다. 문서 답변의 `document`에는 `{id, revision, filled, needsConfirmation, missing, unsupported}`가 들어 있다. `needsConfirmation`의 문자열은 사용자에게 확인할 질문 또는 해당 필드 라벨이다.

현재 요청을 먼저 판단한 뒤 이전 대화나 화면 선택을 문맥으로 사용한다. 작성·수정·축약 요청 뒤에 덧붙인 반영 조건도 같은 문서 요청으로 처리한다. 문서 수정 중에는 기존 기억을 사용하고, 새로운 사용자 진술이 함께 들어올 때 기억 후보를 추출한다. 자격증 정정과 조회가 한 메시지에 있으면 정정을 검증한 상태로 조회에 답하고 해당 턴과 기억을 함께 저장한다. 문서 작성 중에도 일반 질문으로 전환할 수 있다. 이전 초안은 문서를 이어서 수정하거나 방금 요청한 경험을 보강할 때 참조한다.

### 페이지 이동과 이력 응답

`profile`로 이동한 뒤 같은 대화를 이어가는 `POST /api/assistant/chat` 요청 예시다.

```json
{
  "conversationId": "career-demo-1",
  "requestId": "turn-2",
  "message": "그 기술을 어떻게 연습할까요?",
  "context": {"page": "profile"}
}
```

첫 턴 저장 후 `GET /api/assistant/conversations/career-demo-1` 응답 예시다. `messages[].result`는 채팅 응답과 같은 스키마이고 `messages[].context`는 당시 화면 정보다.

```json
{
  "conversationId": "career-demo-1",
  "summary": "",
  "messages": [
    {
      "timestamp": "2026-11-22T01:00:00Z",
      "message": "이 노드의 선수학습은 뭔가요?",
      "context": {
        "page": "tree",
        "jobId": "mock-ai-engineer",
        "skillId": "mock-data-analysis",
        "opportunityId": null,
        "documentId": null
      },
      "result": {
        "answer": "선택한 데이터 분석 노드의 선수학습은 Python 기초예요.",
        "conversationId": "career-demo-1",
        "mockData": true,
        "memoryUpdated": false,
        "needsConfirmation": [],
        "contextIssues": [],
        "opportunities": [],
        "document": null
      }
    }
  ]
}
```

사용자별로 대화를 구분하므로 다른 사용자가 같은 `conversationId`로 조회하면 자신의 저장 기록만 받는다. 그 사용자에게 해당 대화가 없으면 `404`다. 네트워크 재시도로 동일 요청을 다시 보낼 때는 `requestId`와 본문을 그대로 재사용한다.

### 양식과 초안

가상 JSON 양식의 최소 예시는 `{"fields":[{"id":"project","label":"프로젝트","kind":"project"},{"id":"intro","label":"지원동기","kind":"narrative"}]}`다. DOCX는 본문의 `{{project}}` 같은 자리표시자와 두 열의 명확한 빈 값 셀을 분석한다. 지원하는 PDF는 암호나 스크립트가 없고 실제 AcroForm 텍스트 위젯이 있는 양식이다. 기본 라틴 문자 밖의 입력은 PDF에서 `unsupported`로 남긴다. 한글 값은 DOCX·JSON 양식에서 작성할 수 있다. 평면 PDF, 스캔 PDF, XFA, 서명 PDF, 일반 DOCX의 자유 배치 빈 줄과 이미지에는 자동 입력하지 않는다.

`Draft`는 `{revision, mockData, fields}`다. 각 `DraftField`는 `{field: {id,label,kind}, status, value, sources, suggestions, note}`다. `filled`는 등록값으로 자동 입력, `confirmation`은 확인 대기, `missing`은 정보 없음, `draft`는 AI 초안, `edited`는 사용자 편집, `unsupported`는 양식 제한을 뜻한다. `filled`에도 확인 대기 중인 추가 기록이 `suggestions`에 있을 수 있다. 초안 내보내기는 자동으로 확인 대기값을 채우지 않는다. 사용자가 직접 편집한 값 역시 제출용으로 검증된 값으로 승격되지 않는다. 서로 다른 항목을 다시 쓰려면 `fieldIds`와 필요한 경우 `narrativePrompt`를 함께 보낸다.

자기소개서는 지원 직무와 문항, 글자 수를 받아 현재 프로필과 본인 진술 중 관련 근거를 고른다. 모델은 허용된 근거 ID를 선택하고 서버가 문장을 작성한다. 경험 근거가 부족한 지원동기는 확인된 관심사와 관련 자격 준비 상태를 지원 이유와 연결하고, 남은 분량에 직무에서의 계획을 담는다. 자기소개도 확인된 배경으로 작성 가능한 초안을 먼저 제공한다. 두 경우 모두 실제 근거를 보강할 질문 하나를 덧붙인다. 경험을 중심으로 작성하는 문항에 해당 근거가 없으면 경험과 역할을 한 가지 묻는다. 글자 수는 본문의 공백과 문장부호를 포함하며 `[AI 초안]` 표시와 작성 안내는 제외한다. API의 범위는 1~3,900자이며 최소가 최대보다 크면 `422`다. 채팅에서는 ‘300자 이내’, ‘250~300자’, ‘500자 내외’를 해석한다.

‘없는 경력은 만들지 마’와 같은 표현은 초안에 사용할 근거를 제한한다. 특정 경력이나 실제 사례를 바탕으로 작성해 달라고 요청하면 해당 근거가 있어야 초안을 작성한다. 가상 경력은 테스트 문서에 `[가상 예시]`로 표시하며, `targetRole`을 지정하거나 실제 제출 용도를 요청한 자기소개서의 후보에서 제외한다.

채팅은 문항 유형, 지원 직무와 현재 글자 수 제한을 해당 턴에 저장한다. 초안을 다시 작성할 때는 같은 대화의 이전 설정을 조회하고 현재 근거로 본문을 구성한다. 새 요청에 직무나 길이가 있으면 그 값을 사용한다. 설정을 별도로 저장하기 전의 기록은 이전 작성 요청에서 읽어 온다. 이전 초안에서 직무를 찾을 수 없는 경우에는 확인된 사용자 목표를 지원 직무로 사용할 수 있는지 확인한다. 초안 안에서 자격증 상태를 수정해 달라는 요청은 초안에 반영한다. 자격증 상태를 별도로 진술하면 기억 정정 흐름에서 검증한다. 문서에 이미 입력된 항목과 수동 편집은 `fieldIds` 및 초안 리비전으로 관리한다. 제출 전 작성자는 `sources`와 `note`를 검토한다.

업로드는 multipart 대신 `fetch(url, {method: "POST", headers: {"Content-Type": file.type || "application/octet-stream"}, body: file})`로 전송한다. 최대 5MiB이며 DOCX 압축 해제 크기, PDF 페이지·필드 수에도 제한이 있다. 클라이언트에서 파일 형식을 미리 체크한 뒤 서버의 `415` 오류를 표시한다. 원본은 사용자별로 따로 보관되고 다운로드는 별도 초안이다.

### 오류 및 웹 연결 전 확인

- 세션이 없거나 만료되면 `401`과 `{"detail":"로그인이 필요해요."}`가 반환된다. 본문·경로 검증 오류는 `422`와 `{"detail":{"code":"invalid_input","message":"요청 입력값을 확인해 주세요."}}`다.
- 이력을 찾을 수 없으면 `404`와 `{"detail":{"code":"not_found","message":"대화를 찾을 수 없어요."}}`가 반환된다. 같은 `requestId`에 다른 본문을 보내면 `409`와 `detail.code=conflict`가 반환된다. 형식이 유효하지만 알려지지 않은 노드는 `200`의 `contextIssues`에 `unknown_skill`을 담는다.
- `413`은 업로드 크기 제한, `415`는 양식 미지원, `429`는 요청 과다다. 제공자 응답 오류는 `502`, 모델 또는 저장소 일시 오류는 `503`, 모델 시간 초과는 `504`로 전달될 수 있다. 시간 초과 응답 예시는 `{"detail":{"code":"model_timeout","message":"AI 응답 시간이 초과됐어요. 잠시 후 같은 질문을 다시 보내 주세요."}}`다. 채팅 요청이 생성 단계에서 실패하면 저장은 응답 성공 뒤로 미뤄진다. 같은 `requestId`와 본문으로 다시 보내면 기존 성공 응답을 재사용하거나 미완료 요청을 다시 처리한다.
- 프론트엔드에 공용 채팅 상태를 두고 페이지 전환 시 선택 정보만 교체한다. 사용자 전환·로그아웃 시 브라우저 상태를 비운다. 서버에 세션이 없는 로컬 시연 모드에서는 로그인 없이 개인화 API를 호출하지 않는다.
- 실제 사용자에게 연결하기 전에 PostgreSQL 어댑터, API 컨테이너 설치와 라우터 등록, 운영 보관·계정 삭제 연동이 필요하다. 실데이터의 생성형 AI 전달 허용 목록을 확정하고 자유 텍스트 개인정보 필터를 운영 정책에 맞게 검증한다. 현재 개발 저장소에는 사용자별 대화 32개, 대화당 최근 50턴, 문서 20개 제한이 있다. 인스턴스별 요청 제한은 운영 공용 제한으로 옮긴다.
- 기존 `api/app/assistant/memory_store.json`과 `history_store.json`은 개발 기록이다. `COPY app`을 쓰는 이미지의 빌드 컨텍스트와 팀 변경 파일에서 이 개발 기록을 제외한다. `DELETE /memory/{id}`는 장기 기억만 지우므로, 대화·첨부를 포함한 계정 전체 삭제는 운영 어댑터에서 연결한다.
- 제공된 DOCX·PDF 지원 범위에 실제 제출 양식이 들어오는지 확인한다. DOCX의 이미지·자유 배치, PDF의 한글 글꼴은 양식별 확인이 필요하다. 외부 제출 경로는 없다.

## 로컬 FastAPI HTTP 통합 테스트

저장소 루트에서 테스트 의존성을 설치하고 `api` 디렉터리에서 실행한다.

```powershell
python -m pip install -r api/app/assistant/requirements-test.txt
Set-Location api
python -m pytest -q app/assistant/test_http_integration.py
```

테스트는 임시 FastAPI 앱에 기존 라우터를 합쳐 실제 회원가입·로그인·로그아웃과 동일한 `current_user`를 실행한다. DB 의존성은 임시 SQLite로 연결하고 챗봇 저장소는 테스트 디렉터리에 둔다. 가상 계정 두 개가 각자 쿠키를 발급받으며 챗봇 모델만 모의 응답을 반환한다. `TestClient`가 ASGI 요청을 처리하므로 브라우저·외부 HTTP 포트·Gemini 키가 필요 없다. 기존 세션 발급과 `current_user`의 만료 판단을 검증한다. 원본 앱의 전역 미들웨어와 실제 웹 프록시 연결은 서버 등록 이후 확인할 범위다.

인증·만료·로그아웃, 사용자 간 이력·기억 분리, 동일 대화 ID로 페이지 이동, 직무·스킬 정보 전달, 요청 검증, 중복 요청과 충돌, 공고 챗봇 경로 공존을 검사한다.

## 실제 Gemini 로컬 검증

저장소 루트에서 API와 어시스턴트 의존성을 설치하고 `api`에서 실행한다.

```powershell
python -m pip install -r api/requirements.txt -r api/app/assistant/requirements.txt
Set-Location api
python -m app.assistant.live_check
```

기본 실행은 키 설정 여부와 단계별 호출 계획만 출력한다. 현재 셸에 `GEMINI_API_KEY`가 주입되어 있고 호출 비용을 확인했다면 `python -m app.assistant.live_check --live`로 검증한다. 키를 출력하거나 `.env`를 열지 않는다. 스크립트는 별도의 임시 저장소에서 가상 학생 `demo001`과 가상 공고·스킬·이력서만 사용한다. `main.py`, 웹 서버, 기존 대화 저장소가 필요 없다.

| 검증 | 예상 Gemini 호출 |
|---|---:|
| SQLD 취득 진술 추출 및 저장 | 2 |
| 새 대화에서 저장된 자격증으로 답변 | 1 |
| 페이지 이동 후 직전 대화 이어가기 | 2 |
| 데이터 분석 스킬 노드와 선수학습 상담 | 1 |
| 가상 채용·창업 공고 상담 | 1 |
| 챗봇에서 이력서 자동 입력, 지원동기 초안 생성과 내보내기 | 1 |

전체 검증의 정상 흐름은 생성 요청 8회다. 재시도와 대체 모델 조회까지 포함한 총 HTTP 상한도 8회다. 공고 조건 판정과 이력서의 등록값 자동 입력은 로컬에서 수행한다. 실행할 프로젝트의 요금제와 토큰 과금을 확인한다. 다른 모델은 `--model`로 명시할 수 있다. [Google 공식 요금표](https://aistudio.google.com/docs/pricing)

직접 대화하는 기존 진입점은 `python -m app.assistant.service`다. CLI의 코드 기본값은 `gemini-2.5-flash`이며, 프로젝트에서 사용할 모델은 `GEMINI_MODEL`로 지정할 수 있다. 여섯 항목의 자동 검증은 `live_check`가 별도로 수행한다. [Google 모델 지원 일정](https://aistudio.google.com/docs/deprecations)

종료 코드 `0`은 실행 계획 출력 성공 또는 실제 시나리오 전부 통과, `1`은 시나리오 실패, `2`는 키나 의존성 등 실행 환경 문제를 뜻한다. 키 미설정으로 종료하면 실제 Gemini 검증은 수행되지 않는다.


### 기억 저장과 모델 오류 진단

같은 키와 동일한 `--model` 값으로 다음 모드를 별도로 실행할 수 있다. 생성 모드에서 `--live`를 빼면 상한만 확인한다.

```powershell
python -m app.assistant.live_check --check-model
python -m app.assistant.live_check --live --probe
python -m app.assistant.live_check --live --recall-only
python -m app.assistant.live_check --live --memory-only
python -m app.assistant.live_check --live --context-only --retries 0 --trace-context
python -m app.assistant.live_check --list-models
```

| 모드 | 정상 요청 수 | 전체 HTTP 요청 상한 |
|---|---:|---:|
| `--live` | 생성 8회 | 8회 |
| `--live --memory-only` | 생성 2회 | 2회 |
| `--live --probe` | 생성 1회 | 4회 |
| `--live --recall-only` | 생성 1회 | 4회 |
| `--live --context-only` | 생성 3회 | 3회 |
| `--check-model` 또는 `--list-models` | 메타데이터 GET 1회 | 1회 |

상한에는 실패 요청, 503 재시도, 대체 모델 메타데이터 조회가 포함된다. 전체 검증의 정상 흐름은 8회가 필요하므로, 재시도가 발생하면 뒤쪽 시나리오가 상한에서 중단될 수 있다. 모든 정상 시나리오에 호출을 배정하려면 `--live --retries 0`을 사용한다. 기본값은 2회이고 `--retries 0` 또는 `--retries 1`로 줄일 수 있다. 503 뒤의 대기는 1초, 2초 순서이며, 응답 및 기억·대화 저장은 요청 재시도가 끝난 뒤 기존 흐름에서 처리한다. [Google의 재시도 지침](https://aistudio.google.com/docs/troubleshooting#retry-strategy)

`--probe`는 짧은 일반 텍스트만 전송한다. `--recall-only`는 임시 저장소에 가상 자격증 진술을 먼저 기록하고, 그 자격증을 프로젝트 실습에 활용하는 방법을 Gemini에 묻는다. 두 모드를 같은 모델에서 비교하면 일반 생성과 개인화 경로의 응답 여부를 구분할 수 있다. `--live --memory-only`는 진술 추출과 답변을 확인한다.

`--context-only`는 같은 가상 대화 ID로 `home`에서 `profile`로 이동하는 두 턴과 `tree` 상담 한 턴을 검증한다. `--trace-context`는 가상 대화 ID·페이지·선택 노드와 그 선수학습, 이전 턴과 모델 원응답·표시 응답에 기대 정보가 있는지를 출력한다. 응답 원문, 전체 프롬프트, 인증 헤더와 키는 출력하지 않으며 추가 호출도 없다. 대화 ID는 서버의 이력 조회에 사용한다. Gemini에는 현재 페이지, 이전 턴과 페이지, 카탈로그에서 확인한 현재 직무·스킬 정보가 전달된다.

`--check-model`은 해당 키가 지정 모델의 메타데이터를 읽을 수 있는지와 `generateContent` 지원 표시를 확인한다. 생성 요청이 재시도 후에도 HTTP 503을 반환하면 남은 요청 한도 안에서 같은 키의 `models.list` 첫 페이지를 1회 조회한다. `--list-models`로 목록만 따로 조회할 수도 있다. 후보가 나타나도 모델은 그대로 사용한다. 후보의 실제 생성 권한과 할당량은 해당 모델의 생성 결과에서 확인해야 한다. [Google 모델 API](https://aistudio.google.com/api-reference/models)

기억 시나리오에는 `기억 추출 진단` 줄이 표시된다. `extraction`은 `missing_updates`, `invalid_updates`, `empty_updates`, `received` 등을 구분한다. `field_shapes`는 알려진 필드의 존재 여부와 타입, 허용된 종류·동작 코드만 보여준다. `validation`은 후보별 거절 이유 또는 `accepted`를, `memory_committed`는 답변까지 완료된 뒤 기억의 저장 여부를 보여준다. 키, 인증 헤더, 사용자 발언, 자격증 이름, 근거 인용구, 원본 프롬프트는 출력하지 않는다.

기존 `model_unavailable` 하나로는 과거 HTTP 상태를 복원할 수 없다. 새 CLI는 오류 코드와 요청 작업, 수신한 Gemini HTTP 상태, 허용된 Google 오류 종류를 표시한다. 응답이 도착하기 전의 연결 오류나 소켓 시간 초과에는 HTTP 상태가 없다.

| 표시 예시 | 의미 |
|---|---|
| `model_not_found / generateContent / Gemini HTTP 404` | 지정 모델 또는 생성 경로를 찾지 못함 |
| `model_authentication / … / Gemini HTTP 400 / API_KEY_INVALID` 또는 HTTP 401 | API 키 또는 인증 오류 |
| `model_access_denied / … / Gemini HTTP 403` | 키·프로젝트·모델 접근 제한 |
| `model_rate_limited / … / Gemini HTTP 429` | 호출 한도 |
| `model_service_unavailable / … / Gemini HTTP 503` | Gemini 서비스 일시 장애 |
| `model_timeout` | 소켓 시간 초과 또는 Gemini HTTP 408/504 |
| `model_invalid_json` | HTTP 응답 JSON 또는 생성된 답변 JSON 파싱 실패 |
| `model_invalid_response / consultation / answer_schema` | 상담 응답의 `answer` 필드 누락 또는 형식 오류 |

### 상담 성능 로그

로컬 수동 대화에서 로그를 보려면 키를 주입한 상태로 `python -m app.assistant.service --trace-timing`을 실행한다. 서비스에서는 `app.assistant.model` 로거를 `INFO`로 설정한다. 단계, 소요 시간, 호출·시도 횟수, 전송 JSON의 바이트 수, 적용 타임아웃과 오류 유형을 기록한다. 제공자가 사용량을 보내면 프롬프트·출력·사고 토큰 수도 기록한다.

- `upstream_open`은 연결부터 응답 헤더 수신까지 걸린 시간이고 `upstream_read`는 응답 본문 읽기 시간이다. 헤더 수신 전 시간에는 네트워크와 Gemini 처리 대기가 함께 포함된다.
- `local_ms`에는 문맥 구성, 직렬화, 응답 검증, 저장이 포함된다. `backoff_ms`는 재시도 대기이며 `calls`는 모델 호출, `attempts`는 재시도를 포함한 전송 횟수다.
- `phase=draft_render`는 서버가 실제로 초안 문장을 구성하는 단계다. 저장된 정보만으로 작성할 수 있으면 `calls=0`이고, 모델에서 경험 근거를 고르면 `stage=narrative`가 추가로 표시된다.
- 기본 소켓 타임아웃은 8초다. 채팅 처리 시작부터 12초의 공통 예산을 적용해 이후 호출과 503 재시도에 남은 시간만 배정한다. 예산으로 다음 호출을 제한하며 소켓 읽기는 전송 계층의 타임아웃을 따른다.
- 사용자 진술이 포함된 직무 비교는 상담과 기억 후보 추출을 한 번에 요청한다. 최신 대화 3턴과 요약 600자, 관련 근거를 전달하고 실제로 언급한 직무의 카탈로그를 우선 사용한다.

## 오프라인 테스트

저장소 루트에서 기존 `api/.venv`를 사용한다. 필요한 테스트 패키지가 빠진 경우에만 같은 가상환경에 `api/app/assistant/requirements-test.txt`를 설치한다.

```powershell
Set-Location api
$env:DATABASE_URL = 'sqlite://'
$env:GEMINI_API_KEY = ''
$env:KSTARTUP_API_KEY = ''
$env:WORK24_API_KEY = ''
$testRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('cuk-assistant-' + [guid]::NewGuid().ToString('N'))
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider -q --basetemp $testRoot
```

어시스턴트 테스트는 가상 학생 두 명, 채용·창업 공고 각 한 건과 분기가 있는 가상 스킬트리를 사용한다. DOCX·AcroForm PDF·JSON 양식은 테스트가 만든다. 모델과 HTTP 전송은 모의 응답을 사용한다. `test_personal_advisor.py`는 자격증 준비 상태 정정, 진로 변경, 화면 이동·노드 변경, 최대 50턴 보관과 계정 격리, 카탈로그와 문서의 지시문 방어, 길이 제한 및 지원 경험의 근거를 검증한다.

### 수동 대화 점검

오프라인에서는 `api`에서 다음 명령으로 임시 저장소와 모의 모델을 준비한다. `ask`로 요청을 보내고 `app.model.calls[-1][1]`에서 모의 모델에 전달된 상담 근거를 확인한다. 가상 데이터만 사용한다.

```powershell
.\.venv\Scripts\python.exe -B -i -c "from tempfile import TemporaryDirectory; from pathlib import Path; from app.assistant.test_chat import make_assistant, ask, update; tmp = TemporaryDirectory(); app = make_assistant(Path(tmp.name))"
```

```python
ask(app, "나 SQLD 취득했어.")
change = "사실 취득한 게 아니라 준비 중이야."
app.model.updates[change] = [update("certification", "replace", "", change, progress="preparing")]
ask(app, change)
ask(app, "내가 취득한 자격증은?").answer
tree = {"page": "tree", "job_id": "mock-ai-engineer", "skill_id": "mock-pandas"}
ask(app, "이 노드의 선수학습은?", **tree).answer
ask(app, "NumPy랑 뭐가 달라?", **tree)
ask(app, "어떤 걸 먼저 배우는 게 좋아?", **tree)
app.model.calls[-1][1]["skillGraph"]
```

모의 모델은 정해진 예시 응답을 반환한다. 자연어 응답 품질은 실제 Gemini를 연결한 로컬 앱에서 다음 순서로 확인할 수 있다. 화면을 바꿀 때 같은 `conversationId`를 유지한다. 직접 채팅하려면 `api`에서 `python -m app.assistant.service`를 사용하고, 화면 선택을 바꿔가며 시험하려면 등록된 로컬 라우터에 다음 `context`를 보낸다.

처음부터 검증할 때는 CLI에 전용 `--store` 경로를 지정한다. 같은 저장소와 사용자로 다시 실행하면 대화가 새로 시작되고, 이전 실행에서 저장한 자격증 상태를 조회할 수 있다. 이전 실행의 대화 ID를 `--conversation-id`로 지정하면 기존 초안 직후의 주제 전환도 확인할 수 있다.

| 대화 흐름 | 확인할 동작 |
|---|---|
| “SQLD를 취득했어” → “사실 취득한 게 아니라 준비 중이야” → “내가 취득한 자격증은?” | 동일 기억의 상태가 준비 중으로 바뀌고 취득 목록에서 빠진다. |
| `mock-ai-engineer/mock-pandas` 선택 → “이게 뭐야?” → “NumPy랑 뭐가 달라?” → “어떤 걸 먼저 배우는 게 좋아?” | Pandas를 기준으로 답하고 두 기술의 카탈로그 관계와 일반 학습 순서를 구별한다. |
| “Python은 초급이고 평일 하루 40분 가능해” → “다음에 뭘 공부해?” → `mock-feature-engineering`으로 이동 → “이 노드를 생략하면?” | 사용자 진술에 맞춰 학습을 제안하며, 새 노드의 연결과 후속 단계가 답변에 반영된다. |
| “데이터 분석가와 AI 엔지니어를 비교해 줘” → “이제 데이터 분석가를 목표로 할래” → 화면 이동 후 “현재 목표 기준으로 부족한 역량은?” | 역할과 준비 방향을 비교하고, 새 목표와 사용자 역량 및 확인되지 않은 역량을 구분한다. |
| “나는 인공지능학과 학생이고 데이터 분석에 관심이 있어. 데이터 분석가와 데이터 엔지니어 중 무엇이 더 잘 맞을까? 추천 이유와 부족한 역량도 알려줘.” | 두 직무를 모두 설명하고, 추천 이유와 확인되지 않은 역량을 제시한다. 정상 경로에서는 로그에 생성 호출 1회가 표시된다. |
| “데이터 분석 직무 지원동기를 300자 이내로 작성해줘. 내가 말하지 않은 프로젝트나 경력은 넣지 마.” → “방금 작성한 지원동기를 120자 이내로 줄이고, SQLD는 취득한 것이 아니라 준비 중인 것으로 표현해줘.” | 첫 응답은 짧은 초안과 보강 질문 하나를 제공한다. 다음 응답은 직무와 이전 초안의 근거를 유지하고 SQLD 준비 상태를 반영한다. 새 대화에서 두 번째 요청만 보내도 120자 이내의 초안을 제공한다. |
| “나 SQLD 자격증을 취득했어. 사실 취득한 건 아니고 지금 준비 중이야. 그럼 내가 취득한 자격증은 뭐야?” | 같은 발언의 최신 상태를 사용해 SQLD를 취득 목록에서 제외하고 준비 상태를 표시한다. |
| “데이터 분석 직무 지원동기를 300자 이내로 작성해줘.” → 같은 발언의 SQLD 정정·조회 → “데이터 분석가와 데이터 엔지니어 중 무엇이 더 잘 맞을까?” | 초안 작성에서 자격증 조회로 전환하고 준비 중인 상태를 저장한다. 이어서 두 직무의 적합도를 현재 관심과 역량으로 비교한다. 저장된 역량이 부족하면 다음 비교에 필요한 근거를 안내한다. |
| “데이터 분석 직무 지원동기를 300자 이내로 작성해줘. 없는 경력은 만들지 마.” → 관심 분야와 자격증 준비 상태를 알려 준 뒤 “방금 이야기한 내 관심과 SQLD 준비 상태를 반영해서 지원동기를 다시 작성해줘.” | 첫 응답에 초안이 포함된다. 후속 응답은 300자 한도와 지원 직무를 이어받고, 최신 관심과 준비 상태를 연결해 작성한다. |
| 지원동기 작성 → SQLD 준비 중으로 기억 정정 → 데이터 분석가와 데이터 엔지니어 비교 → “아까 데이터 분석 직무 지원동기를 300자 이내로 다시 작성해줘. 지금까지 말한 관심사와 SQLD 준비 상태를 반영해줘.” | 재작성과 반영 조건을 함께 처리한다. 새 진술이 없는 마지막 턴은 기억 추출이나 상담 모델 호출을 거치지 않는다. |
| “그 설명은 내가 선택한 노드와 달라” → `profile` 이동 후 “아까 Pandas는 어디에 썼지?” | 화면 선택을 재확인하고, 명시적으로 언급한 이전 스킬 문맥으로 되돌아간다. |

스킬트리 담당자는 현재 웹과 동일한 카탈로그 버전, 노드 ID, 간선 방향과 누락 관계의 의미를 백엔드에 제공한다. 백엔드 담당자는 실제 검증 출처, 사용자별 저장·삭제 정책, 라우터와 운영 저장소 구성을 확인한다. 프론트엔드 담당자는 화면 전환 시 최신 ID를 전송하고 가상 배지, 기억 진행 상태, 초안 출처와 확인 질문을 표시한다.
