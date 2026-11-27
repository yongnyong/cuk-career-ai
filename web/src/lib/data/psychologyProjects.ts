// Service-authored work samples. They are independent choices, not application requirements.
export const PSYCHOLOGY_PROJECTS = [
  { id: "PSY-PROJECT-SURVEY", name: "심리학 설문 연구 프로젝트 완성",
    completion: "연구 질문, 설문지, 익명화한 분석 데이터, 분석 방법과 결과·한계를 포함한 보고서를 남기세요. 공개 데이터나 가상 자료를 사용할 때는 그 사실을 명시하세요.",
    priority: ["psy-counsel", "psy-org", "psy-research"] },
  { id: "PSY-PROJECT-DATA", name: "공개 심리 데이터 분석 프로젝트 완성",
    completion: "공개 데이터의 출처와 이용 조건을 적고, 분석 코드 또는 통계 프로그램 파일, 시각화, 결과 해석과 한계를 함께 남기세요.", priority: ["psy-research", "psy-clinical"] },
  { id: "PSY-PROJECT-EXPERIMENT", name: "인지심리 실험 구현",
    completion: "실행 가능한 실험, 자극·실험 절차·측정 항목, 실행 방법과 분석 결과를 남기세요. 시연용 가상 반응은 실제 참여자 결과와 구분하세요.", priority: ["psy-research"] },
  { id: "PR-PSY-PROGRAM", name: "심리교육 프로그램 개발", reuseExisting: true,
    completion: "대상과 교육 목표, 이론적 근거, 회기별 활동, 진행 자료와 효과 평가 계획을 하나의 프로그램으로 묶으세요. 개발한 계획과 실제 운영 결과를 구분하세요.", priority: ["psy-counsel", "psy-clinical", "psy-develop"] },
  { id: "PSY-PROJECT-CAREER", name: "진로 탐색 워크숍 개발",
    completion: "대상과 목표, 진행안, 참여자 활동지와 피드백 설문을 묶고 각 활동을 선택한 근거를 설명하세요.", priority: ["psy-counsel", "psy-org"] },
  { id: "PSY-PROJECT-ORGANIZATION", name: "조직문화·직무만족 조사 프로젝트 완성",
    completion: "조사 설계와 문항, 공개·가상 데이터의 출처, 분석 결과와 개선 제안 보고서를 남기세요. 가상 결과를 실제 조직 조사 결과로 표현하지 마세요.", priority: ["psy-org"] },
  { id: "PSY-PROJECT-UX", name: "사용자 조사·사용성 평가 프로젝트 완성",
    completion: "평가 대상과 과업, 조사 질문, 비식별 관찰 기록, 문제 분석과 개선안을 남기세요. 실제 조사와 가상 시연을 구분하세요.", priority: ["psy-research", "psy-org"] },
  { id: "PSY-PROJECT-REPLICATION", name: "심리학 연구 재현 프로젝트 완성",
    completion: "원 연구의 출처와 재현 범위, 재현 절차와 분석 자료, 원 연구와 결과를 비교한 보고서 및 한계를 남기세요.", priority: ["psy-research", "psy-clinical"] },
];

export const psychologyProjectById = new Map(PSYCHOLOGY_PROJECTS.map(project => [project.id, project]));
