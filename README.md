# CUK Career AI

현장실습과 창업 기회를 연결하는 AI 진로 스킬트리 — 2026학년도 가톨릭대학교 생성형 AI 경진대회 출품작 (팀 나 혼자만 레벨업).

## 구조

- `web/` — Next.js 16 웹. 현재는 브라우저 저장 모드로 전체 흐름이 동작한다.
- `api/` — (예정) FastAPI·PostgreSQL(pgvector)·Redis 워커·Gemini.
- `docs/DEPLOY.md` — 배포 계획.

## 실행

```bash
cd web
npm install
npm run dev
```

## 웹 코드 안내

| 위치 | 내용 |
|---|---|
| `src/lib/types.ts` | 프론트·백엔드 공통 데이터 계약 |
| `src/lib/data/departments.ts` | 가톨릭대 학부 학과 목록(출처·확인일 포함) |
| `src/lib/data/catalog.ts` | 직무·역량 사전 |
| `src/lib/data/opportunities.ts` | 시연용 가상 공고 |
| `src/lib/engine.ts` | 규칙 엔진(3값 판정)·추천·스킬트리·알림·근거 챗봇·공고 파서 |
| `src/lib/store.tsx` | 클라이언트 상태(가상 시계 포함) |

## 시연 순서 (기획서 4.8)

1. `/onboarding` → "민지" 빠른 시작 → 스킬트리
2. 기회 카드 → 공고 상세: 조건 판정·근거·지원 퀘스트·챗봇
3. `/onboarding` → "서연"(프랑스어문화학과·창업) → 창업 경로
4. `/admin` → 새 공고 등록 → 스킬트리의 "새 기회 열림"
5. `/admin` → 정정 공고 처리 → `/notifications`에서 이전 알림 무효·재예약 확인, 가상 시계로 날짜 넘기기

## 원칙

- 화면의 "가상 공고"는 시연용 데이터이며 실제 모집이 아니다.
- 이름·학번·연락처·성적은 받지 않는다(가명 ID).
- 날짜와 명시 조건은 코드가 판정하고, 근거가 없으면 답하지 않는다.
