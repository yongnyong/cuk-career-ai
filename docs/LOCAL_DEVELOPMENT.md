# Windows 로컬 개발

이 저장소의 Next.js 웹과 FastAPI API를 같은 PC에서 실행한다. 웹은 로컬 API로 연결한다. 계정·세션·학생 프로필·관리자 설정은 `api/dev.db`, 공개 수집 공고와 공고별 역량 근거는 `api/career.db`에 저장한다.

## 현재 PC에서 실행

PowerShell 창 두 개를 열고 각각 저장소 루트에서 실행한다.

첫 번째 창:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev-api.ps1
```

두 번째 창:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev-web.ps1
```

- 웹: http://127.0.0.1:3000
- API 상태: http://127.0.0.1:8000/api/health
- API 문서: http://127.0.0.1:8000/docs
- 각 창에서 Ctrl+C로 종료한다.

실행 스크립트는 API의 DB 주소와 웹의 API 주소를 로컬 값으로 지정한다. API 포트가 이미 사용 중이면 `dev-api.ps1 -Port 8001`, `dev-web.ps1 -ApiPort 8001`로 함께 바꾼다. 웹 포트는 `dev-web.ps1 -Port 3001`로 바꿀 수 있다.

이번 PC에는 Node.js가 있지만 npm 명령이 PATH에 없어, 초기 웹 설치에는 제공된 pnpm을 통해 npm 10.9.4를 실행했다. 설치 후 위 스크립트는 Node로 Next.js를 직접 실행하므로 npm 명령이 없어도 된다.

## PyCharm에서 열기

1. **File → Open**에서 `cuk-career-ai` 폴더 전체를 연다.
2. **Settings → Python Interpreter**에서 기존 로컬 인터프리터를 추가하고 `api/.venv/Scripts/python.exe`를 선택한다. 이미 만든 가상환경을 그대로 사용한다.
3. 하단 Terminal에 PowerShell 탭 두 개를 열고, 각 탭의 위치를 저장소 루트로 맞춘 뒤 위의 API·웹 실행 명령을 각각 실행한다.

웹 스크립트는 PATH의 Node를 우선 사용한다. 없으면 이 PC에 설치된 Codex 런타임의 Node를 찾아 사용하므로 PyCharm 터미널에 npm이나 Node 명령이 등록되지 않았어도 실행할 수 있다. 코드를 수정하면 두 개발 서버가 변경 사항을 반영하며, 각 터미널에서 Ctrl+C로 종료한다.

## 새 PC에서 초기 설치

Node.js 20.9 이상과 Python 3.10 이상을 준비한다.

```powershell
cd api
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
cd ..\web
npm ci
```

`web/.env.local`을 만들고 다음 한 줄을 저장한다. 이 파일은 Git에서 제외된다. 실행 스크립트도 같은 주소를 지정한다.

```dotenv
API_URL=http://127.0.0.1:8000
```

## 키와 데이터

계정·프로필·화면 시연은 AI 키 없이 실행할 수 있다. 새 SQLite DB에는 실제 수집 공고가 없으며 시연 계정으로 가상 공고를 확인할 수 있다. 실제 공고 수집과 Gemini 챗봇은 각각 필요한 API 키를 설정한 뒤 별도로 실행한다. 기본 개발 서버 시작 시 수집기를 자동 실행하지 않는다.

스킬트리는 현재 공고와 `api/app/career/evidence.json`의 검수된 자료를 이용해 개인별 경로와 추천 퀘스트를 계산한다. 추천 노드의 상세를 열면 로컬 API가 로그인된 Codex CLI로 준비 행동을 구체화할 수 있다. 모델을 사용할 수 없는 경우 기본 준비 행동을 표시한다. 공고 상세의 채팅과 공고 수집은 각각 기존 설정을 사용한다.

이 PC의 `api/career.db`에는 기존 수집 DB의 공개 공고 396건을 가져왔다. 앱의 ‘기회 → 전체 공고’에서 확인한다. 서버 실행 중에 가져왔으면 브라우저를 새로고침한다. 수집 DB가 갱신됐을 때는 `api` 폴더에서 다음 명령으로 다시 반영한다. 같은 공고는 중복 생성되지 않으며 마감 정정은 이력으로 남는다.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m app.import_postings --source ..\..\data\career.db
```

`api/career.db`는 Git에 포함할 수 있는 공개 공고 DB다. 계정용 `dev.db`는 Git 제외 대상이다. 기존 SQLite 계정 DB 안의 `postings` 테이블은 API 시작 시 공고 DB로 검증 후 이동한다. 새 클론은 포함된 공고 DB를 바로 사용하고 계정 DB를 별도로 생성한다. 공고 DB 위치는 `CAREER_DATABASE_URL`로 지정할 수 있다.

마감이 확인되지 않은 공고는 ‘기한 확인’으로 표시한다. 원문 링크와 학과·직무 매칭 참고 정보를 제공하며, 지원 조건과 준비 근거는 검수된 항목을 사용한다.

가져오기 과정에서 저장된 본문의 자격요건·우대사항 문단을 규칙으로 읽어 `skillEvidence`를 만든다. 스킬 ID와 함께 원문 문장·문단 ID·필수/우대·다부문 공고 여부를 저장하고, 스킬트리 추천이 그 문장을 인용한다. 현재 396건 중 16건에서 직접 연결 가능한 근거 17개를 추출했다. 저장된 상세에 역량 내용이 없는 공고는 기존 학과·직무 매칭 정보와 원문 링크를 제공한다. 시험 대체 조건은 검수된 조건 그룹에서 판정한다.

## 기존 검사

API:

```powershell
cd api
.\.venv\Scripts\python.exe -m pytest -q
```

웹은 처음 클론한 뒤 Next.js의 라우트 타입을 먼저 생성해야 `LayoutProps`를 인식한다.

```powershell
cd web
node node_modules/next/dist/bin/next typegen
node node_modules/typescript/bin/tsc --noEmit
node node_modules/eslint/bin/eslint.js src
node --test tests/skill-tree.test.mjs
node node_modules/next/dist/bin/next build
```

빌드는 현재 레이아웃에서 사용하는 Google 폰트를 다운로드하므로 네트워크 연결이 필요하다.

## 이 PC에서 확인한 결과 (2026-11-18)

- API 기존 테스트: 32개 통과. Starlette/AnyIO 사용 중단 예정 경고 1개.
- 웹: `next typegen` 후 TypeScript 검사와 ESLint 통과.
- 개발 서버: 웹 HTML 200, CSS 파일 200, 웹의 `/api/health` 프록시 `{"ok":true}` 확인.
- 프로덕션 빌드: 미통과. Google 폰트 다운로드 제한을 해소한 뒤에도 Turbopack이 CSS 처리 자식 프로세스의 조기 종료를 보고했다. 원인은 확정하지 못했으며 개발 서버의 페이지·CSS 응답은 정상이다. 배포 전에는 별도로 해결하고 빌드를 다시 확인해야 한다.

저장소는 `codex/local-development` 브랜치에서 준비했다. 현재 추가한 파일은 로컬 실행 스크립트와 이 안내이며, 모델 기능이나 원격 서비스는 변경하지 않았다.
