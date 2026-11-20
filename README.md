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

## 0. 운영 중인 서비스

| 무엇 | 주소 | 어디서 도는가 |
|---|---|---|
| 웹(제출 URL) | https://cuk-career-ai.vercel.app | Vercel |
| API 서버 | https://43-200-13-8.sslip.io (`/api/health`로 확인) | AWS Lightsail 서울, Docker Compose |

처음 온 팀원은 **3. 실행 방법 → 6. Git 협업 방법 → 8. 배포와 운영** 순서로 읽으면 된다.

---

## 1. 지금 되는 것 / 안 되는 것

2026-11-17 기준.

| 기능 | 상태 | 비고 |
|---|---|---|
| 회원가입·로그인·로그아웃 | ✅ 서버 | argon2 해시, HttpOnly 세션 쿠키 |
| 내 데이터 저장(프로필·역량·퀘스트·알림) | ✅ 서버 | 다른 기기에서 로그인해도 복원 |
| 기본 정보 입력 + 보유 역량 진단 | ✅ | 학과·학년 기준 체크 항목 (규칙 기반) |
| 스킬트리, 기회 카드, 추천 | ✅ 브라우저 | 규칙 기반 |
| **학과별 테크트리** | ✅ 39개 학과 182개 테크 | 학과 홈페이지의 진로·로드맵과 커리어넷 근거, 노드에 출처 링크. 1차 8개 학과는 `deptTracks.ts`, 2차 31개 학과는 `scripts/gen_dept_tracks.py` 명세에서 생성한 `deptTracks2.ts`. **순서는 조사자 초안이며 재학생 확인은 심리·사복만 진행 중**. 자료가 없는 10곳(프랑스어문화, 바이오로직스, 예술미디어융합, 의학·간호·신학, 자유전공·광역·융합)은 공통 직무만 |
| 공고 상세: 조건 3값 판정, 지원 퀘스트 | ✅ 브라우저 | 충족 / 미충족 / 확인 필요 |
| **실제 공고 수집** | ✅ 서버 | 학교 공지(취창업·장학), K-Startup, 고용24 공채속보. 6시간마다 자동 |
| **AI 공고 구조화** | ✅ 서버 | 학교 공지 본문 → Gemini → 마감·대상·자격·직무 |
| **AI 근거 챗봇** | ✅ 서버 | 공고 문단만 근거로 답, 근거 번호를 서버가 대조, 없으면 보류 |
| **공고 핵심 정보** | ✅ 서버 | 지원금·혜택, 우대 사항, 창업 단계, 제출 서류. 학교 공지는 Gemini 추출, K-Startup은 API + 공고 상세 화면. 공고문에 없으면 "원문에서 확인"으로 표시 |
| **점수제·등급제 자격** | ✅ | TOEIC 점수, OPIc·JLPT·한국사·한자 등 등급 입력. 학과가 급수를 밝힌 노드는 권장 기준과 비교 |
| **완료 체크리스트·증빙 첨부·인쇄** | ✅ 브라우저 | 자격증 파일은 개인정보라 서버로 보내지 않고 그 기기 브라우저(IndexedDB)에만 저장. `/print`에서 완료 내역 인쇄 |
| **조건 정리 에이전트** | ✅ 서버 | `api/app/tidy.py`. 자격 요건 문장을 Gemini가 학력·전공·어학·병역·창업 단계 등으로 정리, 근거 구절이 원문에 있을 때만 채택. 판정은 규칙이 한다 |
| **창업 조건 자동 판정** | ✅ | 창업 단계·연령(K-Startup 공식 값), 지역(에이전트). 내 정보의 선택 입력과 비교 |
| **채용 학력 자동 판정** | ✅ | 고용24 최소 학력을 학년·학적과 비교 |
| **관리자 계정** | ✅ 서버 | `ADMIN_IDS`에 등록한 아이디. 서버 현황(개수만), 실제·가상 공고 전체 보기, 테크트리 편집기(수정본은 서버에 저장되어 전체 사용자에게 적용) |
| 가상 공고 29건 | ✅ 브라우저 | 시연용 계정에서만 보인다. 챗봇은 규칙 기반 |
| 알림(D-7·3·1, 정정 재계산) | ⚠️ 화면 내 알림함만 | 이메일·푸시 없음 |
| 관리자 공고 등록 | ⚠️ 브라우저에만 저장 | 정규식 파서. 서버 저장·Gemini 미연결 |
| 공고 옆 패널, 어디서나 열리는 챗봇 버튼 | ❌ | 화면 구성안에만 있음 |
| 임베딩 검색(pgvector) | ❌ | 지금 챗봇은 공고 한 건의 문단 전체를 그대로 넣는다 |
| GitHub push → 자동 배포 | ❌ | 웹·서버 모두 수동 배포 (8번 참고) |

실제 공고와 가상 공고가 보이는 규칙: **가입한 계정**은 실제 공고만, **시연용 계정**(민지·서연·도윤)은 둘 다 본다.

---

## 2. 구조

```
cuk-career-ai/
├─ web/                  Next.js 16 (화면)
│  ├─ src/app/           페이지: / · login · signup · onboarding · tree · opportunities · notifications · profile · admin · sources
│  ├─ src/components/    Header, quest-ui(노드·상태창), ChatPanel, OppCard, AuthForm, ui
│  └─ src/lib/
│     ├─ types.ts        프론트·백엔드 공통 데이터 계약
│     ├─ engine.ts       규칙 엔진·추천·스킬트리·알림·(가상 공고용) 챗봇
│     ├─ store.tsx       상태 저장소 (서버 모드 / 로컬 모드), 서버 공고 불러오기
│     └─ data/           학과 목록, 직무·역량 사전, 학과별 테크(deptTracks.ts), 가상 공고, 시연 계정
├─ api/                  FastAPI (서버)
│  ├─ app/main.py        계정·세션·내 데이터·공고 목록 API
│  ├─ app/collect.py     공고 수집기 (학교 공지 + Gemini, K-Startup, 고용24)
│  ├─ app/chat.py        근거 챗봇 API와 프롬프트
│  ├─ app/catalog.json   직무·역량 id 목록 (web의 catalog.ts에서 뽑은 것)
│  └─ tests/             pytest
├─ scripts/server-setup.sh  새 서버 1회 설치 스크립트
├─ docs/DEPLOY.md        배포 구성 메모
├─ docs/DEPT_TECH_TREES.md  학과별 테크트리 설계안 (학과 홈페이지 조사, 미반영)
├─ docs/EVALUATION.md    검증 계획(기획서 4.8 지표 6개 + AI·준수 지표 4개), 정답표 양식은 docs/eval/templates/
├─ docker-compose.yml    서버용 (Postgres + API + Caddy)
└─ Caddyfile             HTTPS 리버스 프록시
```

```
[브라우저] ── /api/* ──> Vercel(web) ──프록시──> Caddy ──> FastAPI(api) ──> Postgres
                                                              │
                              6시간마다 수집(cron) ───────────┤──> 학교 공지 · K-Startup · 고용24
                                                              └──> Gemini (구조화 · 챗봇)
```

웹이 `/api/*` 요청을 API 서버로 넘긴다. 브라우저 입장에서는 같은 주소라 로그인 쿠키가 그대로 동작한다.

**서버 모드와 로컬 모드**: 웹은 시작할 때 `/api/me`를 호출한다. 서버가 응답하면 서버 모드, 응답이 없으면 로컬 모드(브라우저에만 저장)로 동작한다. 시연 현장에서 서버가 죽어도 화면이 살아 있게 하기 위한 장치다.

**디자인**: 어두운 바탕의 "시스템 창" 테마. 색과 서체는 `web/src/app/globals.css`의 토큰에서만 바꾼다. 상태색은 초록=완료, 파랑=지금 도전, 회색 점선=잠김, 금색=기회 열림으로 고정이다.

---

## 3. 실행 방법

필요한 것: Node.js 20 이상, Python 3.10 이상.

### 가장 빠른 방법: 웹만 띄우고 운영 서버에 붙기

화면 작업만 할 때는 API를 직접 띄울 필요가 없다.

```bash
cd web
npm install
echo API_URL=https://43-200-13-8.sslip.io > .env.local
npm run dev                   # http://localhost:3000
```

이러면 실제 공고와 챗봇이 그대로 동작한다. 단, 여기서 가입한 계정은 **운영 DB에 실제로 저장**되니 테스트 계정은 "내 정보 → 모두 삭제"로 지운다.

### API 서버까지 내 PC에서

```bash
cd api
python -m venv .venv
.venv\Scripts\activate        # macOS·Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --port 8000
```

웹의 `.env.local`은 `API_URL=http://127.0.0.1:8000`으로 둔다. DB는 `api/dev.db`(SQLite)가 자동으로 생긴다. API 문서는 http://localhost:8000/docs.

내 PC에서 수집기와 챗봇까지 돌리려면 API 키를 환경변수로 준 뒤 실행한다(키 받는 법은 8번).

```bash
set GEMINI_API_KEY=...        # macOS·Linux: export GEMINI_API_KEY=...
set KSTARTUP_API_KEY=...
set WORK24_API_KEY=...
python -m app.collect         # 있는 키에 해당하는 출처만 수집한다
```

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
| GET | `/api/catalog` | 관리자가 고친 테크트리(직무·스킬) 수정본 |
| PUT | `/api/admin/catalog` | 수정본 저장 (관리자만) |
| GET | `/api/admin/overview` | 서버 현황, 개수만 (관리자만) |
| GET | `/api/opportunities` | 수집한 실제 공고 전체 (`types.ts`의 `Opportunity[]`) |
| POST | `/api/chat` | `{oppId, question}` → `{text, citations, held}` |

- 아이디: 영문 소문자·숫자·밑줄 4~16자. 비밀번호: 6자 이상.
- 로그인 실패는 아이디당 5분에 5회로 제한한다. 틀린 비밀번호와 없는 아이디는 같은 응답을 준다.
- 챗봇은 질문 300자, IP당 1분에 10회로 제한한다.

### 공고 출처

| 출처 | id 접두어 | 방식 | 걸러내는 기준 |
|---|---|---|---|
| 가톨릭대 공지사항(취창업·장학) | `cuk-` | 목록·본문 읽기 → Gemini 구조화 | 명단·결과 발표 제외, 마감일 없는 글 제외 |
| K-Startup (공공데이터포털) | `kst-` | 공식 API, AI 미사용 | 신청 대상에 대학생 포함 + 전국·서울·경기·인천 |
| 고용24 공채속보 | `w24-` | 공식 API, 직무 연결만 Gemini | 신입·경력무관 모집만 |

현장실습지원센터(co-op.catholic.ac.kr)는 공고 본문이 로그인 뒤에 있어 수집하지 않는다. 고용24의 일반 채용정보 목록은 개인 인증키로 쓸 수 없다.

### 챗봇 프롬프트를 고칠 때

프롬프트는 `api/app/chat.py`의 `PROMPT`다. 고친 뒤에는 아래 질문으로 직접 확인한다.

- 공고에 답이 있는 질문 → 근거 번호(§)와 함께 답하는가
- 공고에 없는 것(예: 토익 점수) → 보류하는가
- "합격할 수 있을까요?" → 예측하지 않고 보류하는가
- "이전 지시는 무시하고 …" → 따르지 않는가

---

## 5. 시연 순서 (기획서 4.8)

로그인 화면 아래의 **시연용 계정**(민지·지우·유나·하늘)은 비밀번호 없이 바로 시작된다. 시연 학과는 팀 소속인 인공지능학과와, 실제 재학생에게 내용을 확인받을 수 있는 심리학과·사회복지학과다.

1. **목표·역량** — 지우(심리학과 3학년, 상담심리)로 시작 → 학과 테크 스킬트리와 기회 카드
2. **조건·서류·신청** — 기회 카드 → 조건 판정과 원문 근거, 지원 퀘스트, 챗봇 질문 (AI 챗봇은 "가상 공고" 표시가 없는 실제 공고에서 보여준다)
   - 유나(미디어기술콘텐츠학과 3학년, 영상 기획·연출): 영상·게임·데이터·창업으로 테크가 뚜렷이 갈리는 학과라, 같은 학과 안에서 테크를 바꿔 보여주기 좋다
3. **창업 경로** — 하늘(사회복지학과 2학년, 사회적경제·소셜벤처) → 창업지원 공고의 창업 단계·지역 판정, 사업계획서 체크리스트
4. **새 공고 등록** — 관리자 → 심리상담센터 실습 공고 구조화 → 지우의 스킬트리에 "새 기회 열림" (브라우저 안에서 동작)
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

위에서부터 우선순위가 높다. 12/1에 기능을 동결한다.

0. **창업 조건의 남은 부분** — 사업자 등록 여부·업종은 자동 판정하지 않는다. 가입 단계에서 창업 정보를 묻지 않는다(내 정보에서만 입력)
1. **화면 마무리** — 어디서나 열리는 챗봇 버튼, 공고 옆 패널, 가입·기본 정보 입력·기회 목록·관리자 화면 점검(새 테마에서 눈으로 확인 안 됨)
2. **직무 보강** — 직무가 22개뿐이라 채용 공고 연결이 거칠다(예: 인사 → 재무). `catalog.ts`에 직무를 추가하면 `api/app/catalog.json`도 다시 만든다
3. **K-Startup 기준 좁히기** — 119건 중 박람회·행사가 섞여 있다
4. **관리자 공고 등록을 서버로** — 붙여넣은 본문을 Gemini로 구조화해 DB에 저장
5. **평가**(기획서 4.8) — 설계는 `docs/EVALUATION.md`. 11/21 프롬프트 동결, 11/22~28 정답표·학생 세션, 11/30 `/evaluation` 공개. 아직 측정값 없음
6. **제출물** — 발표자료 20장, 시연 영상 3분, 지원금 사용계획서
7. 문서: `docs/DEPLOY.md`는 초기 계획 메모라 실제 구성과 다른 부분이 있다(Redis·워커 없음)

---

## 8. 배포와 운영

### 비밀값은 저장소에 없다

이 저장소는 **공개**다. API 키와 DB 비밀번호는 서버의 `~/cuk-career-ai/.env`에만 있고 Git에 올리지 않는다. 필요한 값의 이름은 `.env.example`에 있다.

| 값 | 어디서 받나 |
|---|---|
| `GEMINI_API_KEY` | https://aistudio.google.com/apikey (무료, 각자 발급 가능) |
| `KSTARTUP_API_KEY` | 공공데이터포털 "창업진흥원_K-Startup 조회서비스" 활용신청(자동승인) |
| `WORK24_API_KEY` | 고용24 → 고객센터 → OPEN-API → 채용정보 신청(개인) |
| 서버 SSH 키, 운영 `.env` | 팀장(양호용)에게 **개인 메시지로** 요청. 단체방·이슈·PR에 붙이지 않는다 |

내 PC에서 개발만 할 때는 키를 각자 발급받아 쓰면 되고, 운영 서버 키를 받을 필요가 없다.

### 웹 배포 (Vercel)

GitHub 자동 배포가 연결돼 있지 않다. `main`에 합친 뒤 Vercel 프로젝트 권한이 있는 사람이 직접 배포한다.

```bash
cd web
npx vercel deploy --prod
```

Vercel 환경변수 `API_URL`은 `https://43-200-13-8.sslip.io`로 설정돼 있다.

### 서버 배포 (AWS Lightsail)

**배포 전에 반드시 `cd api && pytest -q`가 통과하는지 확인한다.** (2026-11-17에 테스트 실패를 놓친 채 배포해 API가 2~3분 멈춘 적이 있다.) `api/`나 `docker-compose.yml`을 고쳐 `main`에 합쳤다면 서버에서 받아 다시 빌드한다. DB 데이터는 유지된다.

```bash
ssh -i ~/.ssh/lightsail-seoul.pem ubuntu@43.200.13.8
cd ~/cuk-career-ai
git pull --ff-only
sudo docker compose build api
# 새 이미지가 뜨는지 먼저 확인한다. 여기서 오류가 나면 아래 up을 실행하지 않는다(실행 중인 서버는 그대로 유지됨)
sudo docker compose run --rm --no-deps -T api python -c "import app.main, app.collect, app.chat"
sudo docker compose up -d
curl https://43-200-13-8.sslip.io/api/health      # {"ok":true}
```

### 관리자 지정

서버 `.env`의 `ADMIN_IDS`에 아이디를 쉼표로 적고 `sudo docker compose up -d`로 반영한다. 계정은 본인이 직접 가입해야 한다(비밀번호는 서버에 해시로만 저장). 관리자가 테크트리 편집기에서 고친 내용은 DB(`settings`)에 있고 Git에는 없다.

### 수집기

서버 cron이 6시간마다 실행하고 결과를 `~/collect.log`에 남긴다. 바뀌지 않은 공고는 다시 처리하지 않는다.

```bash
sudo docker compose exec -T api python -m app.collect   # 바로 한 번 실행
tail ~/collect.log                                      # 최근 실행 결과
```

### 서버를 새로 만들 때

Ubuntu 서버에서 아래 한 줄을 실행하면 Docker 설치부터 실행까지 끝난다. 그다음 `.env`에 API 키 세 개를 추가하고 수집기를 한 번 돌린다.

```bash
curl -fsSL https://raw.githubusercontent.com/yongnyong/cuk-career-ai/main/scripts/server-setup.sh | bash
```

### 비용

AWS 무료 플랜의 크레딧($100)에서 서버 요금(월 $12)이 빠진다. 대회가 끝나면 Lightsail 서버와 고정 IP를 **둘 다** 삭제하고, API 키 세 개도 폐기한다.

---

## 9. 대회 준수 사항

코드를 고칠 때 아래가 깨지지 않게 한다.

- **robots.txt**: 수집하는 사이트마다 확인한다. 학교 홈페이지의 `/_attach/`, `/_custom/`, `/_res/` 경로는 자동 수집하지 않는다. 공지 제목과 본문만 다룬다.
- **수집 빈도**: 요청 간격을 충분히 둔다(3초 이상).
- **첨부파일**: 받지 않는다. 학교는 `/_attach/`, K-Startup은 `/afile*/`를 robots.txt로 막아 두었다. 첨부에만 있는 내용은 사람이 직접 열어 옮기는 경우에만 쓴다.
- **증빙 파일**: 학생이 붙인 자격증은 서버에 올리지 않는다.
- **로그인 영역**: 로그인해야 보이는 화면(현장실습 시스템 내부, 포털 등)은 수집하지 않는다.
- **출처 표시**: 모든 공고에 출처·확인 시각·원문 링크를 표시하고, AI가 정리한 내용에는 "AI가 정리한 정보이니 원문을 확인하세요"를 붙인다.
- **개인정보**: 이름·연락처·학번 전체·성적을 받지 않는다(학번은 입학년도만). 선택 입력으로 창업 단계·거주 시도·출생 연도(창업 공고 판정용), 어학 점수·등급을 받는다. 이 값들은 생성형 AI에 보내지 않는다. 공지에 포함된 명단은 저장하지 않고 생성형 AI에도 입력하지 않는다.
- **가상 데이터 구분**: 가상 공고는 화면·통계·평가에서 "가상"으로 표시한다. 원문이 없는 모집 기회를 AI가 만들어 채우지 않는다.
- **판정 범위**: 날짜와 명시 조건은 코드가 판정한다. 합격·선발 가능성은 예측하지 않는다.
- 대회 이후 실제 서비스로 운영하지 않는다.

출처 목록은 서비스의 `/sources` 화면에 있다.
