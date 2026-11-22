// 직무 트랙에서 배운 내용을 적용해 볼 선택 과제. 기업의 채용 조건과는 출처가 다르다.
function exercise(id: string, name: string, anchors: string[], action: string, completion: string) {
  return { id, name, anchors, action, completion, independent: false };
}

// An introductory task relates to the track skill but can be started before completing it.
function starter(id: string, name: string, anchors: string[], action: string, completion: string) {
  return { ...exercise(id, name, anchors, action, completion), independent: true };
}

export const PRACTICE = [
  starter("PR-ROLE-COMPARISON", "목표 직무 공고 비교표", [], "같은 직무의 공고 두 건을 골라 일의 내용, 지원 요건, 우대 조건을 각각 대조하세요.", "두 원문 링크와 확인 날짜, 공통 조건과 한 곳에서만 요구한 조건을 표로 남기세요."),
  starter("PR-COURSE-EVIDENCE", "전공 과제와 직무 역량 연결표", [], "수강한 과목이나 팀 과제 하나를 골라 목표 직무의 어느 업무에서 활용할 수 있는지 찾아보세요.", "결과물, 내가 한 일, 관련 업무와 연결한 이유를 한 줄씩 기록하세요."),
  starter("PR-LABEL-GUIDE", "학습 데이터 라벨링 지침", ["SK-ML-EVAL", "SK-DL"], "공개 예시 열 건을 분류하고 두 사람이 다르게 판단할 만한 경계 사례를 찾아보세요.", "라벨 정의, 경계 사례, 제외 기준을 적고 처음 보는 예시로 지침을 점검하세요."),
  exercise("PR-SPLIT-AUDIT", "학습·평가 데이터 누수 검사", ["SK-DA"], "예측 시점과 관측 단위를 정하고 같은 개체나 미래 정보가 평가 데이터로 새어 들어가는지 점검하세요.", "분할 코드, 겹치는 개체 수, 제외한 열과 이유를 남기세요."),
  exercise("PR-TRAIN-REPLAY", "학습 실험 재현 스크립트", ["SK-PY-01"], "간단한 모델 실험을 하나의 명령으로 다시 실행하도록 환경, 설정값과 난수 시드를 기록하세요.", "새 환경에서 실행한 명령과 재실행 결과, 값이 달랐다면 그 차이를 저장하세요."),
  exercise("PR-ERROR-TAXONOMY", "오분류 사례 원인 분석", ["SK-ML-EVAL"], "오분류 예측을 유형별로 나누고 특히 성능이 낮은 입력 조건을 찾아보세요.", "유형별 건수, 대표 사례와 다음 실험에서 확인할 가설을 남기세요."),
  exercise("PR-INFERENCE-TESTS", "추론 입력 검증 테스트", ["SK-PY-01"], "모델에 들어갈 입력 형식을 정의하고 빈 값, 잘못된 자료형, 알 수 없는 범주를 검사하세요.", "정상 입력과 각 오류 입력의 기대 결과를 자동 테스트로 남기세요."),
  exercise("PR-DEPLOY-ROLLBACK", "모델 버전 교체·복구 실습", ["SK-DEPLOY"], "로컬 데모에서 모델 버전을 교체한 뒤 이전 버전으로 복구해 보세요.", "교체 전후의 예측, 버전 식별자와 복구 후 확인 절차를 기록하세요."),
  starter("PR-COUNSEL-CONSENT", "모의 상담 첫 회기 안내문", ["PSY-INTERVIEW", "SK-COUNSEL", "SP-COUNSEL"], "가상 상담 실습을 처음 접하는 사람에게 진행 순서와 기록 방식을 설명하는 안내문을 쓰세요.", "실습 목적과 질문·중단 방법을 담아 동료에게 읽혀 보고 불분명한 표현을 수정하세요."),
  exercise("PR-FOLLOWUP-QUESTIONS", "후속 질문 자기피드백", ["PSY-INTERVIEW", "SP-COUNSEL"], "가상의 면접 대화를 읽고 답변을 유도한 질문을 열린 질문으로 다시 작성하세요.", "기존 질문, 수정 질문, 바뀐 의도를 나란히 비교한 피드백지를 남기세요."),
  starter("PR-RESEARCH-PLAN", "연구용 데이터 수집 명세서", ["PSY-STAT", "SW-RESEARCH", "SK-SCI-PAPER", "SK-RESEARCH"], "연구 질문을 검증할 자료의 각 열에 이름, 관찰 단위, 허용값과 결측 처리 기준을 정하세요.", "명세서와 같은 형식의 예시 데이터 행을 만들고 다른 사람이 그 기준대로 입력할 수 있는지 확인하세요."),
  starter("PR-BENEFICIARY-MAP", "수혜자·비용 부담자 관계도", ["SW-SOCIAL", "SK-BMC", "SK-NPO"], "가상 사업에서 서비스를 이용하는 사람, 비용을 내는 사람, 운영하는 기관을 구분하세요.", "각 주체가 얻는 가치와 부담을 표시하고 아직 확인해야 할 가정을 적으세요."),
  exercise("PR-PARTNER-PLAN", "지역 협력기관 제안서", ["SW-SOCIAL", "SW-PROGRAM", "SK-NPO"], "실제 공개 사업을 조사해 함께할 수 있는 지역 기관과 협업 내용을 설계하세요.", "기관 선정 근거, 양측 역할, 필요한 자원과 첫 회의 의제를 담은 초안을 남기세요."),
  starter("PR-PILOT-DECISION", "파일럿 계속·중단 결정표", ["SK-IDEA", "SK-MVP"], "아이디어를 시험하기 전에 어떤 결과에서 계속하거나 설계를 바꿀지 정하세요.", "가설, 측정 지표와 판정 기준을 정하고 가상의 결과에 적용해 보세요."),
  starter("PR-SOURCE-COMPARE", "사료 이본 대조표", ["HIS-SOURCE", "HIS-ARCHIVE", "HIS-HERITAGE"], "같은 사건이나 구절을 다룬 공개 자료 두 종을 골라 작성 시기와 표현 차이를 대조하세요.", "서지정보, 서로 다른 대목과 가능한 해석을 주석으로 남기세요."),
  exercise("PR-TRANSLATION", "고전 번역 대조본", ["HIS-SOURCE"], "짧은 공개 사료를 현대어로 옮기고 해석이 갈릴 만한 단어를 살펴보세요.", "원문과 번역문, 다른 번역 후보와 선택 이유를 함께 남기세요."),
  starter("PR-CATALOGUING", "기록물 목록과 색인", ["HIS-SOURCE", "HIS-ARCHIVE", "HIS-CONTENT", "HIS-C-HANJA"], "공개 자료 다섯 점에 식별자, 생산자, 시기, 주제어를 붙여 검색 가능한 목록을 만드세요.", "목록 파일과 주제어로 자료 한 점을 찾아낸 예시를 남기세요."),
  starter("PR-ACCESSIBLE-LESSON", "수업 자료 접근성 점검", ["SP-TEACH", "SP-TYPES", "SK-SPED"], "짧은 활동지 한 장을 골라 글자, 이미지 설명, 지시문의 이해 가능성을 점검하세요.", "수정 전후 자료와 바꾼 세 항목의 이유를 기록하세요."),
  starter("PR-OBSERVATION", "가상 활동 관찰 기록지", ["SP-TEACH", "SP-ASSESS", "SP-COUNSEL", "SW-SKILL", "PSY-TEST"], "가상 활동을 정해 제삼자도 확인할 수 있는 행동과 관찰자의 해석을 나눠 적으세요.", "관찰 항목, 기록 예시와 해석 시 주의할 점을 담은 양식을 만드세요."),
  starter("PR-PUBLIC-PROCESS", "행정 신청 절차 안내", ["SK-KHIST", "SK-NCS", "SK-POLICY", "SW-POLICY"], "기관이 공개한 신청 절차 하나를 처음 접하는 이용자 입장에서 따라가 보세요.", "공식 출처, 준비 자료, 접수부터 결과 통지까지를 정리한 안내를 남기세요."),
  starter("PR-ISSUE-MEMO", "쟁점·근거 검토 메모", ["SK-LAW-DOC", "SK-POLICY", "SW-POLICY", "PSY-CRIME"], "공개 자료로 확인할 수 있는 가상 사례를 정하고 사실, 쟁점, 확인이 필요한 사항을 구분하세요.", "각 주장 옆에 근거를 붙이고 남은 질문을 정리한 메모를 작성하세요."),
  starter("PR-RECONCILE", "거래 명세 대사표", ["ACC-FIN", "SK-ACC", "SK-FIN"], "가상 거래 명세와 입금 내역을 대조하고 누락·중복·금액 불일치를 구분하세요.", "대사 규칙, 불일치 목록과 재확인할 항목을 남기세요."),
  starter("PR-ENV-SAMPLING", "환경 관측자료 수집 설계", ["ENV-AIR", "ENV-WATER", "ENV-RENEW", "SK-LAB-ANAL"], "확인할 환경 지표에 맞춰 공개 관측소, 측정 간격과 비교 기간을 선택하세요.", "선택 근거와 자료 누락·단위 차이를 처리할 계획을 남기세요."),
  starter("PR-REQUIREMENTS", "기능 요구사항·인수 조건", ["SK-WEB", "SK-EMB", "ICE-PROG", "ICE-LOGIC", "SK-CIRCUIT", "ICE-SIGNAL"], "만들려는 기능 하나에 대해 입력, 원하는 동작과 실패 상황을 설명하세요.", "요구사항별로 구현 여부를 확인할 시험 입력과 기대 출력을 적으세요."),
  starter("PR-DESIGN-BRIEF", "디자인 브리프와 시안 비교", ["SK-DESIGN-TOOL", "CLO-PATTERN", "CLO-ILLUST", "SK-FASHION", "SK-ARTS-PLAN"], "이용자와 제약을 정의하고 같은 목적의 시안 두 개를 스케치하세요.", "선택 기준과 최종 시안을 결정한 이유를 남기세요."),
  starter("PR-CUSTOMER-JOURNEY", "고객 여정·이탈 지점 지도", ["SK-MKT", "CLO-BIGDATA", "SK-SNS", "SK-TRADE", "SK-CONTENT"], "한 제품을 처음 발견해서 구매하거나 문의하기까지 단계를 적어 보세요.", "단계별 고객 질문, 이탈 가능 지점과 검증할 개선안을 남기세요."),
  starter("PR-RECORD-TRACE", "기록 추적성 점검", ["SK-GMP", "SK-BIO-QC", "SK-HACCP", "SK-PHARM-INTERN", "SK-CLIN"], "가상 업무 기록에서 누가, 언제, 어떤 버전을 작성·수정했는지 거슬러 올라가 보세요.", "기록 연결표와 출처나 수정 이력을 확인할 수 없었던 항목을 정리하세요."),
  exercise("PR-DATA-CHECKS", "데이터 품질 자동 검사", ["SK-DA", "SK-SQL"], "표 데이터에서 키 중복, 허용 범위, 누락값을 검사하는 규칙을 작성하세요.", "잘못된 예시 행을 넣었을 때 해당 규칙이 실패하는 실행 기록을 남기세요."),
  exercise("PR-MODEL-CARD", "모델 카드 작성", ["SK-ML-EVAL"], "평가한 모델의 의도한 용도, 학습 데이터 범위와 적용하기 어려운 사례를 문서화하세요.", "모델 버전, 평가 세트, 사용상 제약을 다른 사람이 확인할 수 있는 카드로 저장하세요."),
  exercise("PR-LATENCY", "추론 지연시간 측정", ["SK-DEPLOY"], "같은 모델 서비스에서 입력 크기나 배치 크기를 바꾸며 응답 시간을 재세요.", "실행 환경, 반복 횟수, 중앙값과 느린 요청의 시간을 표로 남기세요."),
  exercise("PR-QUAL-CODING", "모의 면접 전사·코딩표", ["PSY-INTERVIEW", "SW-RESEARCH"], "가상 면접의 발화에 주제 코드를 붙이고 애매한 문장의 분류 기준을 정하세요.", "가상 발화, 코드 정의, 판단을 수정한 사례를 정리하세요."),
  exercise("PR-QUESTION-PILOT", "설문 문항 예비검토표", ["PSY-STAT", "PSY-TEST", "SW-RESEARCH"], "측정할 개념을 정하고 이중 질문이나 응답을 유도하는 표현을 찾아 고치세요.", "초안과 수정 문항, 수정 이유를 한 줄씩 대응시킨 표를 남기세요."),
  exercise("PR-REFERRAL", "상담기관 의뢰 절차도", ["PSY-COMM", "SP-COUNSEL"], "가상 상황을 정하고 공개된 지역기관 안내에서 접수 창구와 절차를 찾아보세요.", "연락 경로, 대상, 필요한 확인 사항과 출처를 넣은 절차도를 남기세요."),
  exercise("PR-PILOT-BUDGET", "소셜벤처 파일럿 예산안", ["SW-SOCIAL"], "작은 시범사업을 정하고 이용자 수와 운영 기간에 따라 필요한 비용을 추정하세요.", "단가 근거, 고정비·변동비와 참여 규모별 총액을 담은 예산표를 저장하세요."),
  exercise("PR-TEST-PROTOCOL", "시제품 사용성 테스트 기록", ["SK-MVP"], "시제품의 주요 기능 하나를 정해 사용자가 수행할 과제와 관찰 항목을 작성하세요.", "동의를 얻은 테스트나 모의 테스트의 관찰 기록과 수정한 화면을 함께 남기세요."),
  exercise("PR-PROGRAM-LOGIC", "복지사업 논리모형", ["SW-PROGRAM", "SK-NPO"], "프로그램 자원·활동·산출·기대 변화를 연결하고 각 연결에 필요한 가정을 적으세요.", "논리모형 한 장과 가장 먼저 확인할 가정 하나를 남기세요."),
  exercise("PR-MODEL", "모델 성능 비교표", ["SK-ML-EVAL"], "공개 예제 데이터의 같은 평가 세트에서 기준 모델과 개선 모델을 비교하세요.", "평가 지표, 두 모델의 결과, 잘못 예측한 사례를 표에 기록하세요."),
  exercise("PR-EDA", "탐색적 데이터 분석 노트북", ["SK-DA", "ENV-DATA", "SK-BIOINFO"], "공개 데이터에서 질문을 정하고 결측값과 분포를 살펴보세요.", "원자료 출처, 그래프, 해석을 넣고 처음부터 다시 실행되는 노트북을 저장하세요."),
  exercise("PR-DEMO", "서비스 실행 데모", ["SK-DEPLOY", "SK-WEB"], "만든 서비스에서 입력 한 건이 결과로 이어지는 과정을 재현해 보세요.", "실행 방법, 예시 입력과 출력, 실패했을 때의 예시를 함께 남기세요."),
  exercise("PR-SURVEY", "설문 분석 결과표", ["PSY-STAT", "SW-RESEARCH", "SK-STAT"], "공개되었거나 가상으로 만든 설문 자료로 집단별 응답 차이를 비교하세요.", "문항, 집계표, 표본의 한계를 설명하는 메모를 저장하세요."),
  exercise("PR-INTERVIEW", "모의 상담면접 질문지", ["PSY-INTERVIEW", "SK-COUNSEL", "SP-COUNSEL"], "가상의 첫 면접 상황을 정하고 시작 질문과 후속 질문을 작성하세요.", "질문의 목적과 모의 면접 후 바꾼 질문을 함께 남기세요."),
  exercise("PR-SESSION", "집단 프로그램 진행안", ["PSY-GROUP", "SW-PROGRAM", "SK-NPO"], "가상의 참여 대상과 회차 목표를 정하고 활동 순서를 설계하세요.", "시간표, 준비물, 참여자 피드백 문항을 담은 진행안을 저장하세요."),
  exercise("PR-DISCOVERY", "고객 인터뷰 기록지", ["SK-IDEA"], "확인할 고객 문제를 정하고 답을 유도하지 않는 질문으로 모의 인터뷰를 하세요.", "질문, 익명화한 답변 요약, 바뀐 가설을 남기세요."),
  exercise("PR-ASSUMPTION", "사업모델 가설 검증표", ["SK-BMC"], "사업모델에서 가장 불확실한 가정 하나를 고르고 작은 검증 방법을 설계하세요.", "가설, 관찰할 지표, 계속할지 판단할 기준을 표로 남기세요."),
  exercise("PR-IMPACT", "사회적 가치 측정표", ["SW-SOCIAL"], "해결하려는 문제와 수혜 대상을 정하고 활동 횟수와 결과의 변화를 구분하세요.", "변화 지표, 자료 수집 방법, 측정 시점을 표에 기록하세요."),
  exercise("PR-CAMPAIGN", "캠페인 성과 측정안", ["SK-MKT", "SK-SNS", "CLO-BIGDATA"], "캠페인 하나를 골라 목표 행동과 채널별 지표를 정하세요.", "지표 산식, 측정 기간, 결과에 따라 바꿀 항목을 적으세요."),
  exercise("PR-STORYBOARD", "콘텐츠 스토리보드", ["SK-CONTENT", "SK-VIDEO", "HIS-CONTENT"], "특정 독자를 위한 콘텐츠를 장면 단위로 설계하세요.", "장면 순서, 메시지, 필요한 자료가 있는 스토리보드를 남기세요."),
  exercise("PR-COST", "원가·손익 분석표", ["ACC-COST", "ACC-FIN", "SK-FIN"], "가상의 제품을 정하고 가격이나 원가가 달라질 때 손익을 비교하세요.", "입력값, 계산식, 조건별 손익표를 포함한 파일을 남기세요."),
  exercise("PR-TRADE", "해외 거래처 제안 메일", ["SK-TRADE", "CLO-C-TRADE"], "가상의 거래처를 정하고 제품, 제안 조건, 회신받을 내용을 외국어로 정리하세요.", "메일 초안과 거래 조건 확인표를 함께 저장하세요."),
  exercise("PR-CIRCUIT", "회로 시뮬레이션 기록", ["SK-CIRCUIT", "ICE-LOGIC"], "시뮬레이터에서 입력값을 바꾸며 예상 출력과 실제 출력을 비교하세요.", "회로도와 입력·출력 비교표를 남기세요."),
  exercise("PR-TEST", "프로그램 테스트 케이스", ["ICE-PROG", "SK-ALGO"], "작성한 함수의 정상 입력과 경계값에 대한 결과를 예측해 보세요.", "입력, 기대 결과, 실행 결과가 담긴 테스트 파일을 저장하세요."),
  exercise("PR-QUALITY", "품질 점검 기록지", ["SK-BIO-QC", "SK-GMP", "SK-HACCP", "SK-LAB-ANAL"], "가상의 품질 점검 자료에서 누락된 기록과 허용 기준을 벗어난 항목을 찾아보세요.", "점검 항목, 판단 근거, 다시 확인할 사항을 표로 남기세요."),
  exercise("PR-LITERATURE", "연구 논문 비교표", ["SK-SCI-PAPER", "SK-RESEARCH", "SW-GRAD"], "같은 질문을 다룬 논문 두 편의 연구 설계와 결론을 비교하세요.", "출처, 자료, 방법, 한계를 담은 비교표를 저장하세요."),
  exercise("PR-POLICY", "정책 대안 비교표", ["SW-POLICY", "SK-POLICY", "SK-LAW-DOC"], "공개 자료를 바탕으로 같은 문제를 다루는 대안 두 개를 비교하세요.", "대상, 기대 효과, 한계, 출처를 담은 표를 남기세요."),
  exercise("PR-LESSON", "수업 활동지", ["SP-TEACH", "SK-SPED", "SK-KOR-TEACH"], "가상의 학습자와 학습 목표를 정하고 목표에 맞는 연습 활동을 만드세요.", "활동지와 학습 목표 달성 여부를 확인할 문항을 저장하세요."),
  exercise("PR-SOURCES", "사료 주석 카드", ["HIS-SOURCE"], "공개 사료 한 점의 작성 시기와 배경을 확인하고 해석이 필요한 대목을 고르세요.", "사료 출처, 발췌, 주석, 남은 질문을 카드에 정리하세요."),
  exercise("PR-SWATCH", "의류 소재·패턴 비교판", ["CLO-FABRIC", "CLO-PATTERN", "SK-FASHION"], "같은 용도의 의류 두 점에서 소재와 패턴이 어떻게 다른지 비교하세요.", "관찰 근거와 디자인 선택 이유를 넣은 비교판을 저장하세요."),
  exercise("PR-MONITOR", "환경 지표 추세표", ["ENV-WATER", "ENV-AIR", "ENV-RENEW"], "공개 관측자료에서 한 지역과 기간을 고르고 환경 지표의 변화를 비교하세요.", "출처, 단위, 날짜별 그래프와 해석을 남기세요."),
  exercise("PR-RESOURCES", "지역 자원 안내 지도", ["SW-SKILL", "SK-VOL", "SP-ASSESS"], "가상의 이용자를 정하고 지역 기관이 공개한 지원 서비스를 찾아보세요.", "대상, 이용 방법, 확인 날짜와 공식 링크를 담은 지도를 저장하세요."),
  exercise("PR-RUNSHEET", "공연 운영 큐시트", ["SK-ARTS-PLAN", "SK-PERF"], "공연 한 회의 준비부터 정리까지 필요한 전환과 담당 역할을 적어 보세요.", "시각, 담당, 전환 신호, 비고가 적힌 큐시트를 남기세요."),
];

export type Practice = (typeof PRACTICE)[number];
