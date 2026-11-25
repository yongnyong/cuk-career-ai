# 공고 DB 공유 파일

로컬 `career.db`와 `startup.db`의 공고·출처·추출 근거를 Git으로 전달하기 위한 JSONL 스냅샷이다. 한 줄이 한 레코드이므로 변경된 공고를 Git diff로 확인할 수 있다.

- `career.jsonl`: 앱 공고 형식의 4,952건. 창업 공고 53건도 포함한다.
- `startup.jsonl`: 창업 공고 53건과 본문·서류·노드 근거·이력. career 파일의 창업 공고와 같은 공고를 별도의 근거 구조로 보존한다.
- `manifest.json`: 파일별 SHA-256, 용량, 테이블별 행 수.

회원 DB인 `dev.db`, 회원·대화 테이블, 환경 파일, API 키, 임베딩 캐시는 내보내지 않는다. 출처 공고에 포함된 공개 사업 안내 문장은 들어 있다. 실제 모집 여부와 지원 조건은 원문에서 다시 확인해야 한다.

## 갱신하기

프로젝트 루트에서 실행한다.

```powershell
cd api
.\.venv\Scripts\python.exe -X utf8 -m app.public_snapshot export
```

갱신 후 `data/public` 변경을 커밋한다. SQLite 원본과 `dev.db`는 Git에 추가하지 않는다.

## 팀원이 DB 복원하기

의존성이 설치된 `api` 폴더에서 실행한다. 기본 실행은 기존 DB를 덮어쓰지 않고 `career.shared.db`, `startup.shared.db`를 생성한다.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m app.public_snapshot restore
```

처음 설치해서 `api/career.db`, `api/startup.db`가 아직 없는 경우, 서버를 시작하기 전에 아래 명령으로 기본 경로에 복원할 수 있다.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m app.public_snapshot restore --career career.db --startup startup.db
```

대상 파일이 하나라도 이미 존재하면 중단한다. 기존 DB 삭제·덮어쓰기는 수행하지 않는다. 두 파일의 체크섬·행 수·외래키·SQLite 무결성이 확인된 뒤에만 대상 DB를 생성한다. 검색 인덱스와 임베딩은 서버에서 다시 생성한다.

이미 DB가 있는 환경에서 공유 사본을 사용할 경우, 서버 프로세스의 `CAREER_DATABASE_URL`과 `STARTUP_DB_PATH`를 각 공유 DB의 절대 경로로 설정한다. `scripts/dev-api.ps1`은 career DB를 기본 경로로 고정하므로 해당 스크립트를 그대로 실행하면 공유 사본 설정이 적용되지 않는다.
