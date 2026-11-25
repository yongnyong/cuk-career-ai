// The issuer describes the exam. The job mapping and explanation are our editorial choices.
export interface CareerCredential {
  id: string;
  name: string;
  officialUrl: string;
  jobs: string[];
  reason: string;
  stage: number;
  // Only a credential name can establish a direct posting requirement.
  explicitPattern: string;
  observation?: string;
  reuseExisting?: boolean;
}

export const CAREER_CREDENTIALS: CareerCredential[] = [
  {
    id: "CERT-YOUTH-2", name: "청소년상담사 2급",
    officialUrl: "https://www.q-net.or.kr/qnet/html/guide67/guide_01.html",
    jobs: ["psy-counsel"], stage: 4,
    reason: "청소년 전문상담을 이어갈 때 검토할 장기 목표예요. 상담 관련 석사 또는 학사·경력 등 응시 경로와 자격연수 요건을 공식 안내에서 확인하세요. 학부 재학생의 즉시 응시 여부는 자동 판정하지 않아요.",
    explicitPattern: "청소년\\s*상담사\\s*2\\s*급",
  },
  {
    id: "PSY-C-CLIN", name: "임상심리사 2급", reuseExisting: true,
    officialUrl: "https://www.q-net.or.kr/crf005.do?gId=&id=crf00503&jmCd=9540",
    jobs: ["psy-counsel", "psy-clinical"], stage: 3,
    reason: "상담과 함께 심리평가 업무로 진로를 넓히려는 학생에게 제안해요. 학위와 실습수련·실무경력 등 응시요건을 확인한 뒤 준비 일정을 정하세요.",
    explicitPattern: "(?<!정신건강)임상\\s*심리사\\s*2\\s*급",
  },
  {
    id: "PSY-C-SURVEY", name: "사회조사분석사 2급", reuseExisting: true,
    officialUrl: "https://www.q-net.or.kr/crf005.do?id=crf00503&jmCd=9521",
    jobs: ["psy-org", "psy-research"], stage: 2,
    reason: "HR·조직문화나 소비자 조사에서 설문 설계와 조사자료 분석 역량을 쌓고 싶을 때 선택할 수 있어요.",
    explicitPattern: "사회\\s*조사\\s*분석사\\s*2\\s*급",
  },
  {
    id: "CERT-AWS-AI", name: "AWS Certified AI Practitioner",
    officialUrl: "https://aws.amazon.com/ko/certification/certified-ai-practitioner/",
    jobs: ["ai-research", "ai-engineer", "ai-data"], stage: 1,
    reason: "AWS의 AI·ML·생성형 AI 개념과 활용 사례를 정리하려는 학생을 위한 기초 선택지예요. 연구·개발 경험은 별도 프로젝트와 함께 준비하세요.",
    explicitPattern: "AWS\\s+Certified\\s+AI\\s+Practitioner\\b",
  },
  {
    id: "CERT-NVIDIA-LLM", name: "NVIDIA-Certified Associate · Generative AI LLMs",
    officialUrl: "https://www.nvidia.com/en-us/learn/certification/generative-ai-llm-associate/",
    jobs: ["ai-research", "ai-engineer"], stage: 2,
    reason: "생성형 AI·LLM 응용을 개발하고 통합하는 기초 개념을 자격으로 정리하려는 학생에게 제안해요. 준비할 때 NVIDIA 솔루션 중심의 출제 범위를 확인하세요.",
    explicitPattern: "NVIDIA[\\s-]*(?:Certified\\s+Associate|NCA)[\\s:·-]*(?:Generative\\s+AI(?:\\s+and)?\\s+LLMs|GENL)\\b",
  },
  {
    id: "CERT-ACP-PREMIERE", name: "Adobe Certified Professional · Premiere",
    officialUrl: "https://certifiedprofessional.adobe.com/premiere",
    jobs: ["mtc-video"], stage: 2, observation: "premiere_editing",
    reason: "영상 기획·연출 중 편집을 맡고 싶을 때, 타임라인 편집과 음향·자막·출력 역량을 자격으로 보여줄 수 있어요.",
    explicitPattern: "(?:Adobe Certified Professional|\\bACP)\\s*(?:[·:–-]\\s*)?(?:in\\s+)?(?:Digital Video Using (?:Adobe )?)?Premiere(?:\\s+Pro)?\\b",
  },
  {
    id: "CERT-ACP-AE", name: "Adobe Certified Professional · After Effects",
    officialUrl: "https://certifiedprofessional.adobe.com/after-effects",
    jobs: ["mtc-vfx"], stage: 2, observation: "after_effects",
    reason: "영상 특수효과 직무에서 쓰는 레이어 합성과 모션 그래픽 제작 역량을 증명하는 선택지예요.",
    explicitPattern: "(?:Adobe Certified Professional|\\bACP)\\s*(?:[·:–-]\\s*)?(?:in\\s+)?(?:Visual Effects (?:&|and) Motion Graphics Using (?:Adobe )?)?After Effects\\b",
  },
  {
    id: "CERT-ACP-PS", name: "Adobe Certified Professional · Photoshop",
    officialUrl: "https://certifiedprofessional.adobe.com/photoshop",
    jobs: ["marketer", "biz-marketing", "clo-marketing"], stage: 2, observation: "PR-IMAGE-RETOUCH",
    reason: "디지털 광고 소재를 직접 제작하는 역할을 원할 때, 이미지 보정과 레이어 편집 역량을 증명할 수 있어요.",
    explicitPattern: "(?:Adobe Certified Professional|\\bACP)\\s*(?:[·:–-]\\s*)?(?:in\\s+)?(?:Visual Design Using (?:Adobe )?)?Photoshop\\b",
  },
  {
    id: "CERT-SNS-ADS", name: "SNS광고마케터 1급",
    officialUrl: "https://www.ihd.or.kr/introducesubject10.do",
    jobs: ["marketer", "biz-marketing", "clo-marketing"], stage: 2,
    reason: "SNS 유료 광고를 운영하고 싶을 때, 매체별 광고 설정과 성과 측정 지식을 점검할 수 있어요.",
    explicitPattern: "SNS\\s*광고\\s*마케터\\s*1\\s*급",
  },
  {
    id: "CERT-TAX", name: "전산세무",
    officialUrl: "https://license.kacpta.or.kr/",
    jobs: ["acc-tax", "acc-corp", "finance"], stage: 2,
    reason: "기장과 세무 신고 업무를 목표로 할 때, 회계 프로그램으로 거래와 세무 자료를 처리하는 능력을 전산세무 2급 또는 1급으로 증명할 수 있어요.",
    explicitPattern: "전산\\s*세무(?=\\s*[12]\\s*급)",
  },
  {
    id: "CERT-BIGDATA", name: "빅데이터분석기사",
    officialUrl: "https://www.q-net.or.kr/crf005.do?id=crf00503&jmCd=1324",
    jobs: ["ai-data", "ds-analyst", "ds-scientist", "data-analyst"], stage: 3,
    reason: "분석 기획부터 모델링과 결과 해석까지 준비하는 학생에게 맞아요. 응시 가능 여부는 본인의 학력·경력과 시행기관 기준으로 확인하세요.",
    explicitPattern: "빅\\s*데이터\\s*분석\\s*기사",
  },
  {
    id: "CERT-POWER-BI", name: "Microsoft Power BI 데이터 분석 전문가",
    officialUrl: "https://learn.microsoft.com/ko-kr/credentials/certifications/data-analyst-associate/",
    jobs: ["data-analyst", "ds-analyst", "ds-consult", "mtc-data"], stage: 2, observation: "power_bi",
    reason: "대시보드로 의사결정을 지원하고 싶을 때, Power BI 데이터 모델링과 시각화 역량을 증명할 수 있어요.",
    explicitPattern: "(?:Microsoft Certified:\\s*)?Power\\s*BI\\s*(?:Data Analyst Associate|데이터\\s*분석\\s*전문가\\s*어소시에이트)",
  },
  {
    id: "CERT-AWS-DATA", name: "AWS Certified Data Engineer – Associate",
    officialUrl: "https://aws.amazon.com/ko/certification/certified-data-engineer-associate/",
    jobs: ["ds-engineer"], stage: 3,
    reason: "AWS에서 수집·변환 파이프라인을 구현하고 운영해 본 뒤, 데이터 품질과 운영 역량을 함께 증명하는 심화 선택지예요.",
    explicitPattern: "AWS\\s+Certified\\s+Data\\s+Engineer\\s*[-–—]?\\s*Associate\\b",
  },
  {
    id: "CERT-AWS-ML", name: "AWS Certified Machine Learning Engineer – Associate",
    officialUrl: "https://aws.amazon.com/ko/certification/certified-machine-learning-engineer-associate/",
    jobs: ["ai-engineer"], stage: 3,
    reason: "학습한 모델을 AWS 서비스에 배포하고 운영하는 직무를 목표로 할 때, 구현·모니터링 실무 경험을 자격으로 증명할 수 있어요.",
    explicitPattern: "AWS\\s+Certified\\s+Machine\\s+Learning\\s+Engineer\\s*[-–—]?\\s*Associate\\b",
  },
];

export const credentialsForJob = (jobId: string) => CAREER_CREDENTIALS.filter(c => c.jobs.includes(jobId));
