import { DEPARTMENT_SOURCE } from "@/lib/data/departments";

const SOURCES = [
  {
    cite: "가톨릭대학교 교수학습개발원(2026.10.21.), '2026학년도 가톨릭대학교 생성형 AI 경진대회 공고'",
    url: "https://www.catholic.ac.kr/ko/campuslife/notice.do?articleNo=276913&mode=view",
    use: "대회 주제, 공개·가상 데이터 조건, 제출 일정 확인",
  },
  {
    cite: "가톨릭대학교 공식 공지사항",
    url: "https://www.catholic.ac.kr/ko/campuslife/notice.do",
    use: "교내 공고의 우선 확인 경로",
  },
  {
    cite: `${DEPARTMENT_SOURCE.label} (${DEPARTMENT_SOURCE.checkedAt} 확인)`,
    url: DEPARTMENT_SOURCE.url,
    use: "학과 목록",
  },
  { cite: "K-Startup 창업지원포털", url: "https://www.k-startup.go.kr/", use: "외부 창업지원 공고 확인 경로" },
  { cite: "TOEIC 공식 안내", url: "https://exam.toeic.co.kr/", use: "어학 시험 확인 경로" },
  { cite: "OPIc 공식 안내", url: "https://www.opic.or.kr/", use: "어학 시험 확인 경로" },
  { cite: "데이터자격검정(DataQ)", url: "https://www.dataq.or.kr/", use: "SQLD·ADsP 확인 경로" },
  { cite: "Q-Net", url: "https://www.q-net.or.kr/", use: "국가기술자격 확인 경로" },
];

const PRINCIPLES = [
  ["robots.txt 준수", "수집하는 사이트마다 규칙을 확인해요. 학교 홈페이지의 /_attach/, /_custom/, /_res/ 경로는 자동 수집하지 않고, 공지 제목과 본문만 다뤄요."],
  ["수집 빈도", "서버에 부담을 주지 않도록 요청 간격을 충분히 둬요."],
  ["출처 표시", "모든 공고에 출처·확인 시각·원문 링크를 표시하고, AI가 정리한 내용에는 원문 확인 안내를 붙여요."],
  ["개인정보 보호", "이름·학번·연락처·성적을 받지 않고 가명 ID만 써요. 창업 공고 판정을 원하는 경우에만 창업 단계·거주 시도·출생 연도를 선택해서 적을 수 있고, 어학 점수와 자격증 파일도 본인이 적거나 붙인 것만 써요(자격증 파일은 서버로 보내지 않고 내 기기에만 저장). 이 정보는 생성형 AI에 보내지 않아요. 챗봇은 맞춤 답을 위해 학과·학년·재학 상태·목표(취업/창업·직무·창업 단계)·완료한 노드와, 대화에서 내가 직접 말한 내용(예: 준비 중인 자격증, 하루 공부 시간)만 AI에 보내요. 로그인 계정의 대화와 기억은 서버에 저장되고 '대화 지우기'·'AI가 기억하는 나'에서 지우거나 탈퇴하면 삭제돼요. 시연 계정의 대화는 서버 메모리에만 잠시 둬요. 공지에 포함된 명단 등 개인정보는 저장하지 않고 생성형 AI에도 입력하지 않아요."],
  ["가상 데이터 구분", "원문이 없는 모집 기회를 AI가 만들어 채우지 않아요. 시연용 가상 공고는 화면·통계·평가에서 실제 공개 공고와 구분해요."],
  ["판정 범위", "날짜와 명시적 자격 조건은 규칙 엔진이 검사하고, 합격·선발 가능성은 예측하지 않아요."],
];

export default function Sources() {
  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <h1 className="text-xl font-bold">출처와 데이터 원칙</h1>
      <section className="card p-5">
        <h2 className="font-bold">참고 자료</h2>
        <ul className="mt-3 space-y-3 text-sm">
          {SOURCES.map((x) => (
            <li key={x.url}>
              <p>출처: {x.cite}</p>
              <a href={x.url} target="_blank" rel="noreferrer" className="break-all text-xs text-blue-700 underline">
                {x.url}
              </a>
              <p className="text-xs text-slate-500">{x.use}</p>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-xs text-slate-500">위 공식 페이지는 확인 경로이며 데이터 이용 권한을 의미하지 않아요.</p>
      </section>
      <section className="card p-5">
        <h2 className="font-bold">데이터 원칙</h2>
        <dl className="mt-3 space-y-3 text-sm">
          {PRINCIPLES.map(([k, v]) => (
            <div key={k}>
              <dt className="font-medium">{k}</dt>
              <dd className="text-slate-600">{v}</dd>
            </div>
          ))}
        </dl>
      </section>
    </div>
  );
}
