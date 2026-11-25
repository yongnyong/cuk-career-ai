# 창업 시연 DB

아이디어와 팀을 보유한 학생의 창업 준비를 위한 공개 공고 표본이다.
초기 표본은 가톨릭대 공고 7건과 기업마당 공고 9건이다. K-Startup 추가 수집 결과는 문서 아래에 기록한다.
2026년 모집 공고이며 마감된 공고도 시연·추출 검증에 포함한다.
공고 후보 URL은 `api/app/startup_collect.py`의 `SAMPLE_URLS`에서 관리한다.

## 파일과 실행

DB 기본 경로는 `api/startup.db`이다. 계정과 취업 DB는 별도 저장소를 사용한다.
필요한 패키지는 창업 수집 전용 목록으로 설치한다.

```powershell
cd "C:\Users\jhpar\Documents\New project\cuk-career-ai\api"
.\.venv\Scripts\python.exe -m pip install -r requirements-startup.txt
.\.venv\Scripts\python.exe -X utf8 -m app.startup_collect
```

저장된 자료의 현황을 확인하거나 네트워크 요청 없이 추출 규칙을 다시 적용할 수 있다.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m app.startup_collect --summary
.\.venv\Scripts\python.exe -X utf8 -m app.startup_collect --reextract
```

`--limit 5`는 앞의 공고 5건만 수집한다. `--skip-pdfs`는 HTML만 수집한다.
`--db`로 별도 DB 파일 경로를 지정할 수 있다.
`--summary --export startup-demo.json`으로 공개 자료를 JSON으로 내보낼 수 있다.
DB는 기존 `*.db` 제외 규칙에 따라 로컬에 저장된다. 공유할 때는 DB 또는 내보낸 공개 자료를 함께 전달한다.

## 테이블

| 테이블 | 저장 내용 |
| --- | --- |
| `postings` | 원문 제목·링크·확인 시각, 공고 유형, 접수 기간과 상태, 대상·혜택 원문, 검토 과제 |
| `sources` | HTML 본문, PDF 페이지 표식이 있는 추출문, 첨부 목록, 내용 해시와 이전 수집본 |
| `attachments` | 원문 첨부 명칭과 안정적인 링크, 양식·참고자료 분류, 열람 상태 |
| `submission_requirements` | 표준 제출물 명칭, 원문 명칭, 의무·단계·적용 조건·마감, 출처 ID·근거 문장·줄 번호 |
| `startup_nodes` | 제출물·준비 과제를 통합한 공통 노드와 서비스에서 정한 완료 기준 |
| `startup_node_evidence` | 노드별 공고·서류·양식·평가지표 근거, 적용 조건, 원문 줄 범위와 PDF 페이지 |
| `startup_node_edges` | 해당 공고에서의 양식 구성과 심사 대비 준비 과제 연결 |

같은 제출물을 여러 출처가 설명하면 근거별 행을 보존한다.
`requirements`는 근거 행 수이고 `unique_requirement_groups`는 공고·서류·의무·단계의 조합 수이다.
기존 화면과 관심사 분기는 후속 연결 대상이다.

## 해석 기준

- `required`는 명시적인 제출 안내에서 추출한 항목이다.
- `optional`은 선택·자율 제출 표현이 확인된 항목이다.
- `conditional`은 본선 진출, 최종 선발, 해당자, 사업자 유형 등 적용 조건이 있는 항목이다.
- `needs_review`는 파일명만 확인됐거나 적용 대상이 불분명한 후보이다.
- 모든 항목의 `review_status`는 초기값 `unreviewed`이다. 규칙 추출 결과에 대한 전수 수동 확정을 의미하지 않는다.

`stage`는 `application`, `finalist`, `agreement`, `unknown` 중 하나이다.
본문의 접수 마감과 개별 자료 제출 마감을 별도로 보관한다.
정규화한 날짜의 정밀도는 일 단위이며, 시각과 세부 제출 방법은 원문과 근거 문장에서 확인한다.
`within_announced_period`는 수집 당시 공고상 접수 기간에 해당한다는 뜻이다.
예산 소진 여부, 수시모집, 당일 마감 시각은 `needs_review`로 처리한다.
접수 상태는 마지막 수집 시점의 값이므로 실제 추천 시 현재 시각으로 재평가해야 한다.

PDF 텍스트 추출 8건이 포함된다. HWP 18건, HWPX·ZIP·JPG 각 1건과 이미지형 PDF 1건은 추가 확인이 필요하다.
매뉴얼·포스터·FAQ 등 참고 첨부 9건은 링크와 파일명을 보관한다.
이미지에만 적힌 조건과 첨부 전용 제출 목록의 완전성은 아직 검증 대상이다.
근거가 추출되지 않은 공고를 서류가 없는 공고로 해석하면 안 된다.

수집은 공개 페이지를 대상으로 사이트별 간격을 두고 수행한다.
기업마당 다운로드 버튼의 임시 토큰은 요청에만 쓰고 DB·JSON에는 저장하지 않는다.
공고 단위 트랜잭션과 내용 해시를 이용해 재실행 시 중복을 방지하고 이전 출처를 보존한다.

## 조회 예시

```sql
SELECT p.title, r.document_type, r.necessity, r.stage,
       r.condition_text, r.deadline_date, r.evidence_quote
FROM submission_requirements r
JOIN postings p ON p.id = r.posting_id
WHERE r.posting_id = 'cuk-277825';
```

```sql
SELECT p.title, r.document_type, s.url, r.evidence_line, r.evidence_quote
FROM submission_requirements r
JOIN postings p ON p.id = r.posting_id
JOIN sources s ON s.id = r.source_id
WHERE r.necessity = 'needs_review';
```

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/test_startup.py tests/test_collect.py tests/test_career_db.py -q
```

## 창업 노드 추출

```powershell
.\.venv\Scripts\python.exe -X utf8 -m app.startup_nodes --export startup_nodes.json
.\.venv\Scripts\python.exe -X utf8 -m app.startup_nodes --posting cuk-277825
.\.venv\Scripts\python.exe -X utf8 -m app.startup_nodes --include-review
.\.venv\Scripts\python.exe -X utf8 -m app.startup_nodes --web-export ../web/src/lib/data/startupCatalog.json
```

수집과 `--reextract`를 실행하면 노드도 함께 재생성한다.
`--posting`을 여러 번 지정하면 선택한 공고들의 근거만 조회할 수 있다.
`--export`의 JSON에는 노드별 원문 근거와 공고별 조건, 연결 정보가 포함된다.

공통 문서 명칭은 같은 노드로 묶고, 필수·선택·본선 진출 조건과 마감은 공고별 근거에 둔다.
같은 공고에 PDF 자료가 여러 개 있어도 `posting_count`는 공고 하나로 센다.
신청서·발급 증빙과 사업 준비 과제는 `kind`로 조회할 수 있다.
사업자등록증 준비 노드는 공고의 해당자 조건을 확인해 필요한 증빙을 준비하는 과제이다.

세부 준비 노드는 실제 신청 양식의 제목과 명시된 심사 항목에서 생성한다.
예를 들어 시장진입 전략이라는 심사 항목을 시장 진입전략 수립이라는 준비 과제로 변환한다.
노드 제목·완료 기준은 서비스가 정한 표현이며 원문 인용은 `quote`에 별도로 보관한다.
`form_section`은 양식 항목, `evaluation`은 심사 대비 준비 과제이며 제출 의무는 `unspecified`이다.
노드 연결은 문서 구성과 심사 대비 준비 과제의 연관성을 나타낸다.

사전에 정규화하지 않은 사업 관련 양식 제목도 새 노드 후보로 저장한다.
개인정보·동의·서약 등 행정 항목은 해당 후보 추출에서 제외한다.
후보의 의미와 완료 기준은 추가 확인 대상으로 두고 `--include-review`에서 조회한다.
알려진 개념도 원문 근거가 발견된 경우에만 노드에 포함한다.

## 회원가입과 화면 연결

회원가입의 관심 분야에서 취업 또는 창업을 선택한다.
선택값은 계정 상태에 저장되며 기본 정보 설정 후 프로필에도 저장된다.
기존 프로필은 주 목표 직무가 창업가 또는 창업가 기반 경로이면 창업, 나머지는 취업으로 해석한다.
내 정보의 목표·소속 다시 설정에서 관심 분야를 바꿀 수 있다.

창업 화면에는 산출물 5개와 세부 준비 과제 17개를 표시한다.
신청·발급 증빙은 공고 상세의 제출물 목록에서 안내한다.
추천 퀘스트는 모집 기간에 해당하는 연결 공고가 있는 미완료 노드를 우선한다.
마감 공고의 양식과 심사 기준은 근거 자료로 보존하고 지난 공고 표시를 붙인다.

웹은 `/api/startup/catalog`에서 창업 DB 자료를 읽고, 연결 시연의 기본 자료로 `web/src/lib/data/startupCatalog.json`을 사용한다.
DB를 갱신하면 위의 `--web-export` 명령으로 웹 기본 자료를 갱신한다.
일 단위 마감은 한국 시간의 마감일까지 유효한 것으로 계산한다.
지원 자격의 지역·소속·업력은 상세 원문 확인 대상으로 안내한다.
학생별 활용 시에는 관심 공고와 해당 공고의 적용 조건을 기준으로 노드를 선택한다.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/test_startup_nodes.py tests/test_startup.py tests/test_collect.py tests/test_career_db.py -q
```
# 창업진흥원과 K-Startup 공개 공고 추가 수집

`api` 폴더에서 실행한다. API 키 없이 공식 공개 목록과 상세 HTML을 읽는다.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m app.startup_public_collect --pages 2 --limit 40 --audit-dir '../../data/startup_public_audit'
```

- 창업진흥원 사업공고 첫 페이지와 K-Startup 모집중 목록의 지정 페이지를 탐색한다. 사이트 전체 수집을 의미하지 않는다.
- 두 목록에서 연결되는 같은 공고는 K-Startup 공고 번호로 중복 제거한다.
- 각 도메인의 robots.txt를 요청 전에 확인하고 사본을 저장한다. 가장 긴 경로 규칙, 와일드카드, 사용자 에이전트 그룹을 판정한다. 규칙을 확인하지 못하면 중단한다. K-Startup은 정상 규칙 텍스트도 HTML Content-Type으로 제공하므로 본문 형식을 검증한다.
- 요청 간격은 최소 3초다. 리디렉션은 자동 추적하지 않고 401·403·429가 발생하면 상세 수집을 멈춘다.
- 운영기관·운영사 모집 및 입찰 등은 제외한다. 저장된 공고가 모든 학생에게 지원 가능하다는 의미는 아니다.
- 이번 수집기는 본문만 읽는다. 첨부 PDF·HWP·이미지의 추가 조건과 양식은 미확보 상태로 남긴다.
- 각 공고를 트랜잭션으로 저장하고 출처 문장과 제출서류의 근거를 대조한다. 기존 공고와 이력은 보존한다.
- 수집 전 startup DB 백업, robots 사본, 저장 성공 HTML, 목록별 출처, 제외·실패 내역과 전후 통계를 audit 폴더에 남긴다. 공고 HTML과 백업은 Git에 올리지 않는다.
- 종료 시 창업 노드 근거를 재생성한다. 앱 공고 DB 동기화는 로컬 DB 경로를 명시해 `python -m app.startup_publish`로 별도 실행한다.

## 2026년 11월 26일 실행 결과

- 공고 16건에서 53건으로 확대했다. 창업진흥원과 K-Startup 목록에서 연결된 공고를 중복 제거해 37건 추가했다.
- 제출서류 근거 47건에서 77건, 노드 근거 80건에서 111건으로 증가했다. 노드 종류는 기존 32개이며, 근거 증가가 노드 종류 증가를 의미하지 않는다.
- 새 공고 중 36건은 공고상 접수기간 내이며 1건은 마감 상태다. 신청 자격 충족이나 현재 모집 지속을 자동 확정하지 않는다.
- 운영기관·전문가 위원단 등 8건을 제외했다. 본문이 제공되지 않은 상세 페이지 14건은 저장하지 않고 실패 내역에 남겼다.
- 자동 대조에서 출처 밖 제출서류 근거 0건, SQLite 외래키 오류 0건이었다. 문서 이름 전체의 추출 정확도·재현율을 측정한 결과는 아니다.
- 실행 보고서와 백업은 저장소 상위 `data/startup_public_audit/20261125T171848Z`에 있다. startup.db와 앱 공고 DB 동기화를 완료했다.
