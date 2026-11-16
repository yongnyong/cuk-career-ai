# CUK Career AI

현장실습과 창업 기회를 연결하는 AI 진로 스킬트리.
2026학년도 가톨릭대학교 생성형 AI 경진대회 본선 출품작 (팀 **나 혼자만 레벨업**).

흩어진 교내외 공지를 모아 학생의 학과·학년·목표·보유 역량에 맞는 공고만 골라 알리고, 공식 신청처까지 연결한다.
학생은 RPG형 스킬트리에서 준비 상태를 확인하고, 실제 공고가 들어오면 해당 노드에서 새 기회가 열린다.

| 일정 | 내용 |
|---|---|
| 12/2(수) 23:59 | 발표자료(20장 이내)·서비스 URL·시연 영상(3분 이내) 제출 |
| 12/4(금) 18:30 | 본선 발표 (발표·시연 10분 + 질의응답 3분, 전원 참석) |

---

## 1. 지금 되는 것 / 안 되는 것

| 기능 | 상태 | 비고 |
|---|---|---|
| 회원가입·로그인·로그아웃 | ✅ 서버 | argon2 해시, HttpOnly 세션 쿠키 |
| 내 데이터 저장(프로필·역량·퀘스트·알림) | ✅ 서버 | 다른 기기에서 로그인해도 복원 |
| 기본 정보 입력 + 보유 역량 진단 | ✅ | 학과·학년 기준 체크 항목 (규칙 기반) |
| 스킬트리, 기회 카드, 추천 | ✅ 브라우저 | 규칙 기반 |
| 공고 상세: 조건 3값 판정, 지원 퀘스트 | ✅ 브라우저 | 충족 / 미충족 / 확인 필요 |
| 근거 기반 챗봇 | ⚠️ 대체 구현 | 키워드·문단 매칭. Gemini 미연결 |
| 공고 등록·AI 구조화 | ⚠️ 대체 구현 | 정규식 파서. Gemini 미연결 |
| 알림(D-7·3·1, 정정 재계산) | ⚠️ 화면 내 알림함만 | 가상 시계로 시연. 이메일·푸시 없음 |
| 공고 데이터 | ⚠️ 가상 29건 | 브라우저에만 있음. 실제 공개 공고 0건 |
| 실제 공고 수집기 | ❌ | |
| Gemini 구조화·RAG 챗봇 | ❌ | |
| 알림 큐(Redis 워커) | ❌ | |
| 배포 | ❌ | Vercel 로그인·VPS 생성 대기 |

---

## 2. 구조

```
cuk-career-ai/
├─ web/                  Next.js 16 (화면)
│  ├─ src/app/           페이지: / · login · signup · onboarding · tree · opportunities · notifications · profile · admin · sources
│  ├─ src/components/    Header, AuthForm, ChatPanel, OppCard, RequireProfile, ui
│  └─ src/lib/
│     ├─ types.ts        프론트·백엔드 공통 데이터 계약
│     ├─ engine.ts       규칙 엔진·추천·스킬트리·알림·챗봇·공고 파서·역량 진단
│     ├─ store.tsx       상태 저장소 (서버 모드 / 로컬 모드)
│     └─ data/           학과 목록, 직무·역량 사전, 가상 공고, 시연 계정
├─ api/                  FastAPI (서버)
│  ├─ app/main.py        계정·세션·내 데이터 API
│  └─ tests/             pytest
├─ docs/DEPLOY.md        배포 계획
├─ docker-compose.yml    서버 배포용 (Postgres + API + Caddy)
└─ Caddyfile             HTTPS 리버스 프록시
```

```
[브라우저] ── /api/* ──> Next.js(web) ──프록시──> FastAPI(api) ──> DB
```

웹이 `/api/*` 요청을 API 서버로 넘긴다. 브라우저 입장에서는 같은 주소라 로그인 쿠키가 그대로 동작한다.

**서버 모드와 로컬 모드**: 웹은 시작할 때 `/api/me`를 호출한다. 서버가 응답하면 서버 모드(계정·데이터가 서버에 저장), 응답이 없으면 로컬 모드(브라우저에만 저장)로 동작한다. 시연 현장에서 서버가 죽어도 화면이 살아 있게 하기 위한 장치다.

---

## 3. 실행 방법

필요한 것: Node.js 20 이상, Python 3.10 이상.

### 웹

```bash
cd web
npm install
cp .env.example .env.local    # API_URL=http://127.0.0.1:8000 로 수정
npm run dev                   # http://localhost:3000
```

`API_URL`을 비워 두면 서버 없이 로컬 모드로 동작한다.

### API 서버

```bash
cd api
python -m venv .venv
.venv\Scripts\activate        # macOS·Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --port 8000
```

로컬에서는 DB를 따로 띄우지 않아도 된다. `api/dev.db`(SQLite) 파일이 자동으로 생긴다.
API 문서는 서버를 띄운 뒤 http://localhost:8000/docs 에서 볼 수 있다.

### 검사

```bash
cd api && pytest -q            # 서버 테스트
cd web && npx tsc --noEmit     # 타입 검사
cd web && npx eslint src       # 린트
cd web && npm run build        # 빌드
```

PR을 올리기 전에 네 가지를 모두 통과시킨다.

---

## 4. API

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/api/health` | 서버 상태 |
| POST | `/api/auth/signup` | 가입. `{id, password}` → 세션 쿠키 발급 |
| POST | `/api/auth/login` | 로그인. 내 데이터(`state`)를 함께 반환 |
| POST | `/api/auth/logout` | 로그아웃 |
| GET | `/api/me` | 내 아이디와 데이터 (로그인 필요) |
| PUT | `/api/me/state` | 내 데이터 저장 (최대 200KB) |
| DELETE | `/api/me` | 계정과 데이터 삭제 |

- 아이디: 영문 소문자·숫자·밑줄 4~16자. 비밀번호: 6자 이상.
- 로그인 실패는 아이디당 5분에 5회로 제한한다.
- 틀린 비밀번호와 없는 아이디는 같은 응답을 준다.

---

## 5. 시연 순서 (기획서 4.8)

로그인 화면 아래의 **시연용 계정**(민지·서연·도윤)은 비밀번호 없이 바로 시작된다.

1. **목표·역량** — 민지(인공지능학과 3학년)로 시작 → 스킬트리와 기회 카드
2. **조건·서류·신청** — 기회 카드 → 조건 판정과 원문 근거, 지원 퀘스트, 챗봇 질문
3. **창업 경로** — 서연(프랑스어문화학과 2학년) → 창업지원 공고 연결
4. **새 공고 등록** — 관리자 → AI 구조화 → 스킬트리에 "새 기회 열림"
5. **마감 정정** — 관리자 → 정정 처리 → 알림에서 이전 알림 무효·재예약 확인, 가상 시계로 날짜 넘기기

새 계정 흐름: 회원가입 → 기본 정보(학과·학년·학번·학적) → 보유 역량 진단 → 목표 직무 → 스킬트리.

---

## 6. Git 협업 방법

### 기본 규칙

- `main`은 항상 **빌드되고 시연 가능한 상태**로 둔다. `main`에 직접 push하지 않는다.
- 작업마다 브랜치를 만들고, Pull Request(PR)로 합친다.
- PR은 작게, 하루 안에 합칠 수 있는 크기로 나눈다. 마감이 가까울수록 큰 PR은 충돌이 난다.

### 처음 한 번

```bash
git clone https://github.com/yongnyong/cuk-career-ai.git
cd cuk-career-ai
```

그다음 위 **3. 실행 방법**대로 웹과 API를 설치한다.

### 작업할 때마다

```bash
git switch main
git pull                               # 최신 main 받기
git switch -c feat/gemini-structuring  # 작업 브랜치 만들기

# ... 코드 수정 ...

git status                             # 무엇이 바뀌었는지 확인
git add web/src/lib/engine.ts          # 올릴 파일만 골라 담기
git commit -m "공고 구조화를 Gemini 호출로 교체"
git push -u origin feat/gemini-structuring
```

push 후 GitHub에서 **Compare & pull request**를 눌러 PR을 만든다. 다른 팀원 1명이 확인하면 **Squash and merge**로 합친다.

### 브랜치 이름

| 접두어 | 용도 | 예 |
|---|---|---|
| `feat/` | 새 기능 | `feat/notice-crawler` |
| `fix/` | 버그 수정 | `fix/dday-timezone` |
| `docs/` | 문서 | `docs/deploy-guide` |
| `chore/` | 설정·정리 | `chore/docker-compose` |

### 커밋 메시지

한 줄 요약을 먼저 쓰고, 필요하면 한 줄 띄고 이유를 적는다. "무엇을 했는지"보다 **왜 했는지**가 남아야 한다.

```
정정 공고 처리 시 이전 예약 알림 무효화

마감이 바뀌면 이전 버전의 D-day 알림이 그대로 발송되던 문제.
버전 번호를 멱등키에 포함해 새 버전 기준으로 다시 예약한다.
```

### main이 먼저 바뀌었을 때

```bash
git switch main && git pull
git switch feat/내-브랜치
git merge main          # 충돌이 나면 파일을 열어 고친 뒤 git add → git commit
```

### 역할별 주 작업 폴더

같은 파일을 동시에 고치면 충돌이 난다. 아래 구분을 기본으로 하고, 남의 영역을 고칠 때는 먼저 말한다.

| 담당 | 주 작업 위치 |
|---|---|
| 양호용 (PM·AI·검색) | `api/` 의 AI 구조화·검색·RAG, `web/src/lib/engine.ts`의 추천·챗봇 |
| 박정현 (백엔드·데이터) | `api/` 의 DB·규칙 엔진·알림, `docker-compose.yml` |
| 김수민 (프론트·UX·QA) | `web/src/app/`, `web/src/components/` |

`web/src/lib/types.ts`는 프론트와 백엔드가 함께 쓰는 계약이다. 바꿀 때는 PR 설명에 적고 모두에게 알린다.

### 올리면 안 되는 것

- `.env`, `.env.local` — API 키와 DB 비밀번호. 실수로 올렸다면 **키를 즉시 폐기하고 새로 발급**한다(커밋을 지워도 기록에 남는다).
- `node_modules/`, `.venv/`, `.next/`, `*.db` — `.gitignore`에 이미 들어 있다.
- 명단·연락처 등 개인정보가 담긴 공지 원문이나 첨부파일.

### 자주 하는 실수

| 상황 | 해결 |
|---|---|
| `main`에서 바로 수정해 버림 | 커밋 전이면 `git switch -c feat/이름` 으로 브랜치만 새로 만들면 수정 내용이 따라온다 |
| 방금 커밋 메시지를 잘못 씀 (push 전) | `git commit --amend -m "새 메시지"` |
| 파일 하나를 수정 전으로 되돌리고 싶음 | `git restore 파일경로` (되돌릴 수 없으니 주의) |
| push가 거절됨 | 원격이 먼저 바뀐 것. `git pull` 후 다시 push. `--force`는 쓰지 않는다 |

---

## 7. 앞으로 할 일

기획서 일정 기준이며, 위에서부터 우선순위가 높다.

1. **배포** — Vercel(웹) + VPS(API). `docs/DEPLOY.md` 참고
2. **공고를 서버로** — 공고·버전·근거 문단 테이블, 관리자 등록 API
3. **Gemini 구조화** — 공고 원문 → JSON, 신뢰도 0.8 미만은 검수 대기
4. **RAG 챗봇** — 문단 임베딩(pgvector) + 키워드 검색, 서버에서 근거 ID 대조
5. **실제 공고 수집** — 학교 공지·K-Startup, robots.txt 준수
6. **알림 큐** — Redis 워커, 이메일 발송
7. **평가** — 필드 정확도, 자격 오판, 챗봇 근거 일치 (실측값만 발표)

---

## 8. 대회 준수 사항

코드를 고칠 때 아래가 깨지지 않게 한다.

- **robots.txt**: 수집하는 사이트마다 확인한다. 학교 홈페이지의 `/_attach/`, `/_custom/`, `/_res/` 경로는 자동 수집하지 않는다. 공지 제목과 본문만 다룬다.
- **수집 빈도**: 요청 간격을 충분히 둔다(3초 이상).
- **출처 표시**: 모든 공고에 출처·확인 시각·원문 링크를 표시하고, AI가 정리한 내용에는 "AI가 정리한 정보이니 원문을 확인하세요"를 붙인다.
- **개인정보**: 이름·연락처·학번 전체·성적을 받지 않는다(학번은 입학년도만). 공지에 포함된 명단은 저장하지 않고 생성형 AI에도 입력하지 않는다.
- **가상 데이터 구분**: 가상 공고는 화면·통계·평가에서 "가상"으로 표시한다. 원문이 없는 모집 기회를 AI가 만들어 채우지 않는다.
- **판정 범위**: 날짜와 명시 조건은 코드가 판정한다. 합격·선발 가능성은 예측하지 않는다.
- 대회 이후 실제 서비스로 운영하지 않는다.

출처 목록은 서비스의 `/sources` 화면에 있다.
