import type { TreeNode } from "./engine";
import type { RecommendedQuest } from "./types";
import { scaleOf } from "./data/catalog";
import { postingProjectById } from "./data/postingProjects";
import { preparationCompletionBySkill } from "./preparationRoutes";

type Work = readonly [title: string, completion: string];

// These are suggested work samples. They do not change the source skill or its requirements.
const samples: Record<string, Work> = {
  "AI-WRITE": ["모델 카드 작성", "만든 모델의 용도, 학습 데이터, 평가 지표와 실패 사례를 모델 카드에 적고 실행 가능한 모델이나 저장소를 연결하세요."],
  "AI-CAP": ["AI 캡스톤 데모와 실행 안내서 만들기", "핵심 기능을 시연하는 링크나 영상, 예시 입력과 출력, 재실행 방법을 README에 남기세요."],
  "SK-PY-01": ["CSV 집계 스크립트 만들기", "예제 CSV를 읽어 항목별 건수를 출력하세요. 입력 파일, 코드, 예상 결과표를 함께 저장하고 다시 실행해 대조하세요."],
  "AI-ML": ["기준 모델 비교 노트북 만들기", "같은 평가 데이터로 기준 모델과 개선 모델을 실행하고 지표 비교표와 오차 사례를 저장하세요."],
  "AI-NLP": ["문장 분류 오류표 만들기", "예문별 정답·예측을 표로 만들고 틀린 문장의 원인과 수정할 점을 기록하세요."],
  "AI-CV": ["이미지 분류 결과판 만들기", "이미지별 정답과 예측을 나란히 놓고 성공·실패 예시와 모델의 한계를 표시하세요."],
  "AI-SPEECH": ["음성 인식 전사 비교표 만들기", "공개 음성의 기준 전사와 모델 전사를 대조해 누락·치환 사례와 재생 시점을 남기세요."],
  "SK-SCI-PAPER": ["연구 참여 기여 기록 작성", "실제로 참여한 연구의 질문, 본인이 맡은 일과 공유 가능한 결과나 발표 기록을 연결하세요."],
  "SK-SQL": ["집계·조인 SQL 파일 작성", "두 테이블을 조인해 질문 하나에 답하고 쿼리, 입력 예시, 결과표를 함께 저장하세요."],
  "SK-DA": ["데이터 분석 노트북 작성", "데이터 출처, 분석 질문, 재실행 가능한 코드, 결과 그래프와 해석을 남기세요."],
  "SK-PORT": ["대표 작업물 포트폴리오 묶기", "작업물별 목표와 본인 기여를 적고 결과를 확인할 수 있는 파일이나 링크를 연결하세요."],
  "MTC-PLAN": ["촬영용 영상 기획안 작성", "대상 시청자, 기획 의도, 도입·전개·결말, 장면별 촬영 장소와 예상 러닝타임을 담으세요."],
  "MTC-VIDEO": ["단편 영상 촬영본과 연출 노트 만들기", "직접 연출한 장면의 촬영본과 쇼트별 의도를 대조하고 촬영 중 바꾼 선택 하나를 설명하세요."],
  "SK-VIDEO": ["영상 편집본과 컷 목록 만들기", "편집한 영상과 컷별 타임코드, 자막 또는 음향 선택 이유를 남기세요."],
  "PSY-STAT": ["심리 설문 분석 보고서 작성", "공개·가상 설문으로 질문을 정하고 변수 정의, 집단별 결과표와 해석 한계를 기록하세요."],
  "PSY-INTERVIEW": ["모의 상담 면접 대화록 작성", "가상 사례의 질문과 응답을 짝지어 적고 후속 질문을 선택한 이유를 표시하세요."],
  "PSY-GROUP": ["집단상담 실습 진행일지 작성", "실습에서 맡은 역할, 진행 순서, 관찰 내용과 다음 회기 수정점을 익명으로 기록하세요."],
  "PSY-CAREER": ["진로상담 실습 사례지 작성", "실습 사례의 탐색 목표, 사용한 질문, 후속 활동을 개인 식별 정보 없이 정리하세요."],
  "PSY-COMM": ["지역사회상담 실습 사례지도 작성", "사례의 지원 필요와 연결 가능한 기관, 연계 근거를 익명 사례지도에 표시하세요."],
  "PSY-GRAD": ["대학원 진학 결과 기록", "입학이 확정된 과정과 전공을 기록하고, 확인 가능한 합격 또는 재학 증빙을 보관하세요."],
  "SW-SOCIAL": ["사회적기업 두 곳의 사업모델 비교표 작성", "공개 자료를 인용해 수혜자, 고객, 수익원, 사회적 성과를 같은 기준으로 비교하세요."],
  "SK-IDEA": ["고객 문제 가설 카드 작성", "고객, 문제가 발생하는 상황, 현재 해결 방법, 가설을 확인할 질문을 한 장에 적으세요."],
  "SK-BMC": ["사업모델 캔버스 작성", "고객·가치 제안·수익원 간 연결을 표시하고 검증할 가설을 하나 고르세요."],
  "SK-BIZPLAN": ["사업계획서 초안 작성", "고객 문제와 해결책, 검증 근거, 실행 일정과 예산을 한 문서에 담으세요."],
  "SK-MVP": ["핵심 기능 시제품 시연본 만들기", "사용자가 핵심 과업을 끝내는 과정을 시제품 링크나 시연 영상으로 남기세요."],
  "SW-PROGRAM": ["복지 프로그램 회차별 운영표 작성", "대상, 활동 목표, 회차별 진행안과 결과를 확인할 지표를 표에 담으세요."],
  "SK-ML-EVAL": ["모델 평가 스크립트 작성", "예측 파일과 정답을 읽어 평가 지표를 계산하고 테스트 입력에서 기대값과 일치하는지 확인하세요."],
  "SK-DL": ["학습된 모델과 추론 코드 공개용 패키지 만들기", "가중치와 의존성 목록, 예시 입력을 함께 묶어 새 환경에서도 예측을 재현하세요."],
  "SK-DEPLOY": ["예측 서비스 배포", "배포 주소에서 예시 입력으로 예측을 실행하고 요청 방법과 응답 예시를 README에 남기세요."],
  "SK-MKT": ["광고 캠페인 브리프 작성", "상품, 타깃, 핵심 메시지, 매체 예산과 성과 판단 기준을 담은 브리프를 만드세요."],
  "SK-SNS": ["채널 게시물 시리즈 제작", "직접 만든 게시물의 카피와 이미지·영상 원본, 발행 순서와 게시 일정을 묶으세요."],
  "SK-PPT": ["프로젝트 제안용 발표 덱 제작", "제안 대상, 해결할 문제, 제안 내용, 비용과 다음 결정을 설명하는 슬라이드를 만드세요."],
  "SK-RESUME": ["목표 공고에 맞춘 이력서 완성", "선택한 공고의 업무와 관련된 경험을 골라 본인의 역할과 성과를 담은 제출용 이력서를 저장하세요."],
  "KOR-CREATE": ["문예지 투고용 창작 원고 완성", "투고할 지면과 장르를 정하고, 해당 지면의 원고 규격에 맞춘 완성본을 만드세요."],
  "KOR-CONTEST": ["문예 공모전 응모", "공고의 응모 자격과 미발표작 조건을 확인하고 제출한 원고와 접수 확인을 남기세요."],
  "KLC-MATERIAL": ["한국어 수업용 교재 단원 제작", "대상 학습 수준에 맞춰 예시 대화, 어휘, 말하기 활동과 교사용 해설을 한 단원으로 묶으세요."],
  "KLC-TEST": ["한국어 수행평가 문항과 채점표 제작", "목표 언어 기능을 평가하는 문항별 예시 답안과 채점 기준을 만들어 같은 답안을 일관되게 채점할 수 있게 하세요."],
  "ENG-TRANS": ["영한 번역 납품본 완성", "사용할 권리가 있는 원문과 번역문을 대조하고, 고유명사와 전문용어를 용어집 기준으로 교정하세요."],
  "CHN-TRANS": ["중한 번역 교정본 완성", "원문과 번역 초안의 오역·누락을 바로잡고, 최종 번역문과 용어집을 함께 묶으세요."],
  "JPN-TRANS": ["일한 번역 납품본 완성", "독자와 매체에 맞춰 경어와 표기를 통일하고, 원문 대조를 마친 번역문을 저장하세요."],
  "CHE-MATERIAL": ["전자재료 후보 물성 비교 데이터시트 제작", "같은 용도의 후보 소재에 대해 공개 물성값, 측정 조건, 단위와 출처를 병기해 설계 조건에 맞는 소재를 고를 수 있게 하세요."],
  "CHE-EDU": ["화학 모의수업 시연 영상 제작", "개념 하나를 가르치는 수업을 촬영하고 학생의 오개념을 확인할 질문과 해설이 담긴 수업안을 함께 남기세요."],
  "SPD-CAD": ["실내 공간 CAD 평면도 제작", "공간의 치수와 축척, 벽·문·가구 배치를 표시한 편집 원본과 출력 도면을 만드세요."],
  "SPD-PORT": ["공간설계 포트폴리오 완성", "한 공간의 요구사항, 설계안, 최종 평면도와 투시도를 연결하고 본인 기여를 표시하세요."],
  "SPD-HOUSE": ["주거 공간 설계 패널 제작", "거주자의 요구와 동선을 반영해 평면도·단면도·공간 이미지를 발표용 설계 패널에 배치하세요."],
  "BMC-DIAG": ["분자질병진단 마이크로디그리 이수", "학내 이수 요건과 본인의 이수 내역을 대조하고 실제 이수 사실을 확인할 수 있는 기록을 보관하세요."],
  "BSW-SIGNAL": ["생체신호 시각화 뷰어 제작", "공개 예제 신호를 입력하면 시간축과 단위가 표시되는 파형을 탐색할 수 있게 만들고 실행 예시를 저장하세요."],
  "SK-RA": ["의료기기 인허가 제출자료 색인 작성", "공개 품목 사례의 대상과 적용 범위를 특정하고 공식 안내에 나온 문서명, 제출 단계, 근거 위치를 추적할 수 있게 연결하세요."],
  "MUS-MAJOR": ["오디션용 독주 녹음 완성", "지원할 오디션의 레퍼토리·촬영 규격을 확인해 연주를 녹음하고 곡명과 연주 구간을 표시하세요."],
  "MUS-ENSEMBLE": ["합주 공연 실황 편집본 제작", "실제 합주에서 맡은 파트와 공연 정보를 적고 공유 가능한 실황에서 해당 연주 구간을 선별하세요."],
  "MUS-STAGE": ["연주회 프로그램북 제작", "실제 준비한 공연의 곡목과 순서, 연주자, 곡 해설을 관객용 인쇄 파일로 편집하세요."],
  "DS-VIZ": ["탐색형 데이터 대시보드 제작", "공개 데이터의 출처와 갱신일을 표시하고 필터에 따라 지표와 그래프가 함께 바뀌는 대시보드를 만드세요."],
  "BIZ-OPS": ["재고 발주 시뮬레이터 제작", "수요와 납기를 입력해 발주 시점과 예상 재고를 계산하고 품절 시나리오를 재현할 수 있게 하세요."],
  "ACT-cuk-ai-camp-273142": ["취업캠프 지원용 자기소개서 완성", "캠프에서 선택한 채용공고와 문항별 최종 답변을 남기세요."],
  "ACT-cuk-ai-hackathon-277246": ["AI 해커톤 데모 제작", "해커톤에서 만든 프로토타입의 핵심 기능을 재현할 수 있는 코드나 시연 영상을 남기세요."],
  "ACT-cuk-ai-startup-277825": ["AI 창업경진대회 피치덱 완성", "사업모델과 아이디어를 설명하는 발표자료를 만들고 공고의 제출 규격과 대조하세요."],
  "ACT-cuk-enterprise-276247": ["강소기업 공모전 기업분석 보고서 완성", "발굴한 기업의 근거 자료와 인터뷰를 연결해 공모전에 낼 보고서를 만드세요."],
  "ACT-cuk-hult-277684": ["글로벌 창업경진대회 발표 덱 완성", "사업계획과 일치하는 발표자료를 만들어 대회 원문의 제출 항목과 대조하세요."],
  "ACT-cuk-python-273043": ["파이썬 실습 분석 노트북 완성", "실습 데이터와 코드로 결과를 재현하고 분석 그래프를 노트북에 남기세요."],
  "ACT-cuk-r-267403": ["R 시각화 스크립트 완성", "실습에서 쓴 데이터로 그래프를 다시 그릴 수 있는 R 코드와 출력 이미지를 저장하세요."],
};

const startupTitles: Record<string, string> = {
  problem: "사업계획서 고객 문제 항목 작성", item: "창업 아이템 소개 카드 작성",
  "team-capability": "팀 역할·담당 산출물 표 작성", "regional-value": "지역자원 활용 제안서 작성",
  market: "경쟁 대안 비교표 작성", "business-model": "수익모델 도식 작성",
  "customer-validation": "고객 가설 검증 계획표 작성", differentiation: "대안별 차별점 비교표 작성",
  "social-impact": "사회적 성과 측정표 작성", feasibility: "핵심 기능 구현 설계서 작성",
  execution: "사업화 실행계획표 작성", schedule: "개발 마일스톤 일정표 작성",
  funding: "자금 조달 계획표 작성", budget: "사업비 배분표 작성",
  "cost-breakdown": "단가·수량별 예산 산출표 작성", "item-images": "시제품 설명 이미지판 제작",
  "market-entry": "첫 고객 확보 실험안 작성",
};

export function questOutcome(node: TreeNode) {
  const { name, skill, kind, startup } = node;
  if (node.mine) return { title: name, completion: "스스로 정한 기준을 채우면 완료로 표시하세요.", label: "내 노드" };
  if (startup) {
    const title = startupTitles[skill.replace(/^SU-PREP-/, "")] ?? name;
    const completion = skill === "SU-PREP-problem"
      ? "목표 고객이 겪는 문제, 현재 대안의 한계와 관찰 근거를 사업계획서에 담으세요. 확인할 가설은 따로 표시하세요."
      : startup.completion;
    return { title, completion, label: "작업물" };
  }
  if (kind === "자격증" || kind === "어학") {
    const language = kind === "어학";
    const suggested = node.evidence?.find(e => e.preparation?.kind === "suggested");
    const direct = node.evidence?.find(e => e.reference.scope === "role" && e.preparation?.kind !== "suggested" && (e.basis === "required" || e.basis === "preferred"));
    const label = direct ? (direct.basis === "required" ? "공고 자격요건에 명시" : "공고 우대에 명시") : suggested ? "서비스 추천" : node.credentialOption ? "직무 선택 자격" : "트랙 준비";
    const record = language ? "공식 성적표" : "취득한 자격증 또는 발급기관의 취득 확인서";
    const completion = scaleOf(skill) ? `${record}에 표시된 실제 점수·등급을 기록하세요.` : `${record}에서 본인의 취득 결과를 확인하세요.`;
    const credentialName = skill === "CERT-TAX" && direct?.minimum ? `${name} ${direct.minimum}` : name;
    return { title: language ? `${name} 성적표 확보` : `${credentialName} 취득`, completion, label };
  }
  if (node.practice) return { title: name, completion: node.practice.completion, label: "직무 연습" };
  const route = node.preparationSignals?.[0]?.preparation;
  const sample = samples[skill];
  if (route) return {
    title: sample?.[0] ?? name,
    completion: route.kind === "direct" ? route.completion : sample?.[1] ?? route.completion,
    label: route.kind === "direct" ? "공고 명시" : "추천 작업물",
  };
  if (sample) return { title: sample[0], completion: sample[1], label: "추천 작업물" };
  const project = postingProjectById.get(skill);
  if (project) return { title: project.name, completion: project.completion, label: "추천 작업물" };
  const savedCompletion = preparationCompletionBySkill.get(skill);
  if (node.state !== "none" && savedCompletion) return { title: name, completion: savedCompletion, label: "작업물" };
  return undefined;
}

export function recommendedTitle(node: TreeNode, quest: RecommendedQuest) {
  if (quest.actionKind === "verify") return `${node.name} 보유 기록과 원문 조건 대조`;
  if (quest.actionKind === "improve" && scaleOf(node.skill)) return `${node.name} 목표 대비 점수·등급 갱신`;
  return questOutcome(node)?.title ?? node.name;
}
