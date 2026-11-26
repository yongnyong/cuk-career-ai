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

const BASE_CREDENTIALS: CareerCredential[] = [
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

const AI_JOBS = ["ai-research", "ai-engineer", "ai-data"];
const PSYCHOLOGY_JOBS = ["psy-counsel", "psy-clinical", "psy-develop", "psy-org", "psy-crime", "psy-research", "psy-center"];

const ADDITIONAL_CREDENTIALS: CareerCredential[] = [
  {
    id: "SK-SQLD", name: "SQLD",
    officialUrl: "https://www.dataq.or.kr/",
    jobs: AI_JOBS, stage: 1, reuseExisting: true,
    reason: "데이터 조회·가공을 위한 SQL 역량을 준비하는 선택지예요.",
    explicitPattern: "SQLD",
  },
  {
    id: "SK-ADSP", name: "ADsP",
    officialUrl: "https://www.dataq.or.kr/",
    jobs: AI_JOBS, stage: 1, reuseExisting: true,
    reason: "분석 기획과 데이터 분석의 기초 개념을 정리할 때 선택해요.",
    explicitPattern: "ADsP",
  },
  {
    id: "SK-INFO-PE", name: "정보처리기사",
    officialUrl: "https://www.q-net.or.kr/crf005.do?id=crf00503&jmCd=1320",
    jobs: AI_JOBS, stage: 3, reuseExisting: true,
    reason: "소프트웨어 설계·구현 역량을 준비하는 선택지예요. 응시요건은 공식 안내에서 확인하세요.",
    explicitPattern: "정보처리기사",
  },
  {
    id: "CERT-AWS-CLOUD", name: "AWS Certified Cloud Practitioner",
    officialUrl: "https://aws.amazon.com/certification/certified-cloud-practitioner/",
    jobs: AI_JOBS, stage: 1,
    reason: "AWS의 클라우드 개념과 서비스 구조를 준비할 때 선택해요.",
    explicitPattern: "AWS Certified Cloud Practitioner",
  },
  {
    id: "CERT-AWS-SAA", name: "AWS Certified Solutions Architect – Associate",
    officialUrl: "https://aws.amazon.com/certification/certified-solutions-architect-associate/",
    jobs: AI_JOBS, stage: 2,
    reason: "AWS 기반 서비스 인프라 설계가 목표일 때 선택해요.",
    explicitPattern: "AWS Certified Solutions Architect – Associate",
  },
  {
    id: "CERT-AWS-DEV", name: "AWS Certified Developer – Associate",
    officialUrl: "https://aws.amazon.com/certification/certified-developer-associate/",
    jobs: AI_JOBS, stage: 2,
    reason: "AWS 기반 애플리케이션 개발·배포 경험과 연결해 준비하세요.",
    explicitPattern: "AWS Certified Developer – Associate",
  },
  {
    id: "CERT-GCP-ACE", name: "Google Cloud Associate Cloud Engineer",
    officialUrl: "https://cloud.google.com/learn/certification/cloud-engineer",
    jobs: AI_JOBS, stage: 2,
    reason: "Google Cloud 서비스 배포·운영을 경험한 뒤 검토하세요.",
    explicitPattern: "Google Cloud Associate Cloud Engineer",
  },
  {
    id: "CERT-GCP-ML", name: "Google Cloud Professional Machine Learning Engineer",
    officialUrl: "https://cloud.google.com/learn/certification/machine-learning-engineer",
    jobs: AI_JOBS, stage: 4,
    reason: "Google Cloud 모델 개발·배포·운영 경험과 연결할 심화 목표예요.",
    explicitPattern: "Google Cloud Professional Machine Learning Engineer",
  },
  {
    id: "CERT-GCP-DATA", name: "Google Cloud Professional Data Engineer",
    officialUrl: "https://cloud.google.com/learn/certification/data-engineer",
    jobs: AI_JOBS, stage: 4,
    reason: "데이터 처리 파이프라인을 설계하고 운영한 뒤 검토할 심화 목표예요.",
    explicitPattern: "Google Cloud Professional Data Engineer",
  },
  {
    id: "CERT-NVIDIA-MULTIMODAL", name: "NVIDIA-Certified Associate · Generative AI Multimodal",
    officialUrl: "https://www.nvidia.com/en-us/learn/certification/generative-ai-multimodal-associate/",
    jobs: AI_JOBS, stage: 2,
    reason: "이미지·텍스트를 함께 사용하는 생성형 AI 응용이 목표일 때 선택해요.",
    explicitPattern: "NVIDIA-Certified Associate · Generative AI Multimodal",
  },
  {
    id: "PSY-C-YOUTH", name: "청소년상담사 3급",
    officialUrl: "https://www.q-net.or.kr/qnet/html/guide67/guide_01.html",
    jobs: PSYCHOLOGY_JOBS, stage: 3, reuseExisting: true,
    reason: "상담 관련 학위 등 응시요건과 합격 후 연수요건을 확인하세요.",
    explicitPattern: "청소년상담사 3급",
  },
  {
    id: "PSY-C-COUNSEL", name: "상담심리사 2급 — 한국상담심리학회",
    officialUrl: "https://www.koreanpsychology.or.kr/psychology/license.html",
    jobs: PSYCHOLOGY_JOBS, stage: 3, reuseExisting: true,
    reason: "학회가 정한 학력·수련·시험·심사요건을 확인하는 상담 진로 목표예요.",
    explicitPattern: "상담심리사 2급",
  },
  {
    id: "CERT-PSY-COUNSELOR", name: "전문상담사 2급 — 한국상담학회",
    officialUrl: "https://www.counselors.or.kr/portal/service/kca_qualification_rule",
    jobs: PSYCHOLOGY_JOBS, stage: 3,
    reason: "학회가 정한 수련자격·수련충족심사·시험 등 취득요건을 확인하세요.",
    explicitPattern: "전문상담사 2급",
  },
  {
    id: "PSY-C-JOB", name: "직업상담사 2급",
    officialUrl: "https://www.q-net.or.kr/",
    jobs: PSYCHOLOGY_JOBS, stage: 2, reuseExisting: true,
    reason: "진로·취업지원 직무를 목표로 할 때 선택하는 자격이에요.",
    explicitPattern: "직업상담사 2급",
  },
  {
    id: "PSY-C-MH", name: "정신건강임상심리사 2급",
    officialUrl: "https://www.ncmh.go.kr/",
    jobs: PSYCHOLOGY_JOBS, stage: 4, reuseExisting: true,
    reason: "관련 학위·과목과 지정 수련기관의 수련 경로를 확인할 장기 목표예요.",
    explicitPattern: "정신건강임상심리사 2급",
  },
  {
    id: "CERT-PSY-CLINICAL-1", name: "임상심리사 1급",
    officialUrl: "https://www.q-net.or.kr/",
    jobs: PSYCHOLOGY_JOBS, stage: 4,
    reason: "학력·수련·경력 등 응시요건을 확인하는 임상 분야 심화 목표예요.",
    explicitPattern: "임상심리사 1급",
  },
  {
    id: "CERT-PSY-SURVEY-1", name: "사회조사분석사 1급",
    officialUrl: "https://www.q-net.or.kr/",
    jobs: PSYCHOLOGY_JOBS, stage: 4,
    reason: "조사·분석 경력을 쌓은 뒤 응시요건을 확인할 심화 목표예요.",
    explicitPattern: "사회조사분석사 1급",
  },
 ];

export const CAREER_CREDENTIALS: CareerCredential[] = [
  ...BASE_CREDENTIALS.map(credential => {
    const extraJobs = ["CERT-BIGDATA", "CERT-AWS-AI", "CERT-AWS-DATA", "CERT-AWS-ML", "CERT-NVIDIA-LLM"].includes(credential.id)
      ? AI_JOBS : ["CERT-YOUTH-2", "PSY-C-CLIN", "PSY-C-SURVEY"].includes(credential.id) ? PSYCHOLOGY_JOBS : [];
    return { ...credential, jobs: [...new Set([...credential.jobs, ...extraJobs])] };
  }),
  ...ADDITIONAL_CREDENTIALS,
];

export function credentialPriority(id: string, jobId: string) {
  const credential = CAREER_CREDENTIALS.find(item => item.id === id && item.jobs.includes(jobId));
  if (!credential || ![...AI_JOBS, ...PSYCHOLOGY_JOBS].includes(jobId)) return undefined;
  const preferred: Record<string, string[]> = {
    "ai-research": ["SK-SQLD", "CERT-NVIDIA-LLM", "CERT-NVIDIA-MULTIMODAL"],
    "ai-engineer": ["SK-SQLD", "SK-INFO-PE", "CERT-AWS-ML"],
    "ai-data": ["SK-SQLD", "SK-ADSP", "CERT-BIGDATA"],
    "psy-counsel": ["PSY-C-YOUTH", "PSY-C-COUNSEL", "CERT-PSY-COUNSELOR"],
    "psy-clinical": ["PSY-C-CLIN", "PSY-C-MH"],
    "psy-org": ["PSY-C-SURVEY", "PSY-C-JOB"],
    "psy-research": ["PSY-C-SURVEY"],
  };
  const rank = preferred[jobId]?.includes(id) ? 1 : credential.stage >= 4 ? 3 : 2;
  return { rank, label: rank === 1 ? "우선 검토" : rank === 2 ? "선택 준비" : "장기·심화 목표", reason: credential.reason };
}

export const credentialsForJob = (jobId: string) => CAREER_CREDENTIALS.filter(c => c.jobs.includes(jobId));
