"""학과별 테크 명세 → web/src/lib/data/deptTracks2.ts 생성.
실행: python scripts/gen_dept_tracks.py scripts/dept_urls.json web/src/lib/data/deptTracks2.ts
근거: 학과 홈페이지의 취업 및 진로(c)·전공로드맵(r), 커리어넷 학과정보(k). 내용은 docs/DEPT_TECH_TREES.md의 조사 결과.
스킬: (id, 이름, 종류, 근거)  /  테크: (id, 이름, 한 줄 설명, 공통 직무, 노드...)
노드 표기: "ID" 선택, "ID!" 필수, "ID<A,B" 선행. 예: "X!<A"
"""
import json
import sys
from pathlib import Path

raw = json.load(open(sys.argv[1], encoding="utf-8"))
out_path = Path(sys.argv[2])
K = "https://www.career.go.kr/cloud/w/major/uView?seq="

# 학과 id → (조사 자료의 학과명, 커리어넷 번호)
SRC = {
    "media-tech": ("미디어기술콘텐츠학과", 181), "ai": ("인공지능학과", 569), "data-science": ("데이터사이언스학과", 591),
    "cs": ("컴퓨터정보공학부", 569), "kor-lit": ("국어국문학과", 69), "philosophy": ("철학과", 548), "english": ("영어영문학부", 366),
    "chinese": ("중국언어문화학과", 520), "japanese": ("일어일본문화학과", 436), "korean-culture": ("한국어문화학과", 613),
    "sociology": ("사회학과", 243), "child": ("아동학과", 334), "intl": ("국제학부", 373), "law": ("법학과", 203),
    "economics": ("경제학과", 25), "public-admin": ("행정학과", 639), "business": ("경영학과", 23), "global-business": ("글로벌경영학과", 23),
    "chemistry": ("화학과", 649), "math": ("수학과", 298), "physics": ("물리학과", 177), "space-design": ("공간디자인ㆍ소비자학과", 10024),
    "food-nutrition": ("식품영양학과", 318), "biotech": ("생명공학과", 260), "biomed-chem": ("바이오메디컬화학공학과", 648),
    "ai-biomed": ("AI의공학과", 414), "biomed-science": ("의생명과학과", 261), "biomed-sw": ("바이오메디컬소프트웨어학과", 404),
    "music": ("음악과", 396), "vocal": ("성악과", 283), "pharmacy": ("약학과", 341),
}

SPEC = {
    "media-tech": dict(
        skills=[("MTC-PLAN", "콘텐츠 기획·스토리텔링", "교육", "c"), ("MTC-VIDEO", "영상 촬영·연출", "프로젝트", "c"), ("MTC-XR", "실감미디어(XR) 프로그래밍", "프로젝트", "c"),
                ("MTC-GAME", "게임 기획·개발", "프로젝트", "c"), ("MTC-VFX", "영상 특수효과(VFX) 제작", "프로젝트", "c"), ("MTC-DATA", "콘텐츠 데이터 분석", "교육", "c"),
                ("MTC-LICENSE", "문화예술 프로그램 기획·라이선싱", "교육", "c"), ("MTC-C-BROAD", "방송통신기사", "자격증", "k")],
        tracks=[("mtc-video", "영상 기획·연출", "영화·방송·유튜브 콘텐츠를 기획하고 연출한다", "content-planner", "MTC-PLAN!", "MTC-VIDEO!<MTC-PLAN", "SK-VIDEO", "SK-PORT<MTC-VIDEO", "MTC-C-BROAD"),
                ("mtc-xr", "실감미디어·게임", "실감미디어 프로그래밍과 게임 기획·개발", "sw-developer", "SK-PY-01!", "MTC-XR!<SK-PY-01", "MTC-GAME<SK-PY-01", "SK-ALGO", "SK-PORT<MTC-XR"),
                ("mtc-vfx", "영상 특수효과", "영화·게임·광고의 특수효과를 만든다", "content-planner", "MTC-VIDEO!", "MTC-VFX!<MTC-VIDEO", "SK-DESIGN-TOOL", "SK-PORT<MTC-VFX"),
                ("mtc-data", "콘텐츠 데이터·AI", "콘텐츠 데이터를 분석하고 AI를 적용한다", "data-analyst", "SK-PY-01!", "MTC-DATA!<SK-PY-01", "SK-DA<SK-PY-01", "SK-SQL", "SK-ADSP<SK-DA"),
                ("mtc-culture", "문화예술 기획·마케팅", "문화예술 프로그램 기획, 마케터, 라이선싱 관리", "arts-planner", "MTC-PLAN!", "MTC-LICENSE!<MTC-PLAN", "SK-MKT", "SK-SNS", "SK-ARTS-PLAN<MTC-LICENSE"),
                ("mtc-startup", "ICT 기획·창업", "ICT 분야 기획자, 프로그래밍 분야 창업", "founder", "MTC-PLAN!", "SK-WEB", "SK-IDEA!<MTC-PLAN", "SK-BMC<SK-IDEA", "SK-MVP<SK-BMC")]),
    "ai": dict(
        skills=[("AI-ML", "머신러닝·딥러닝", "교육", "r"), ("AI-NLP", "자연어처리", "교육", "r"), ("AI-CV", "컴퓨터비전·디지털영상처리", "교육", "r"), ("AI-SPEECH", "음성인식·합성", "교육", "r"),
                ("AI-IR", "정보검색", "교육", "r"), ("AI-GNN", "그래프마이닝·그래프신경망", "교육", "r"), ("AI-CAP", "인공지능 캡스톤디자인", "프로젝트", "r"), ("AI-FIELD", "인공지능 현장실습", "경험", "r"),
                ("AI-WRITE", "기술적 글쓰기", "역량", "r")],
        tracks=[("ai-research", "AI 연구원", "IT 기업에서 모델을 연구·개발한다", "ai-engineer", "SK-PY-01!", "AI-ML!<SK-PY-01", "AI-NLP<AI-ML", "AI-CV<AI-ML", "AI-SPEECH<AI-ML", "AI-CAP!<AI-ML", "AI-WRITE", "SK-SCI-PAPER<AI-CAP"),
                ("ai-robot", "로봇·자율주행", "로봇과 자율주행의 인지·판단 기술", "ai-engineer", "SK-PY-01!", "AI-ML!<SK-PY-01", "AI-CV!<AI-ML", "SK-EMB", "AI-CAP<AI-CV"),
                ("ai-data", "데이터과학 연구원", "데이터에서 패턴을 찾아 서비스에 쓴다", "data-analyst", "SK-PY-01!", "SK-DA!<SK-PY-01", "AI-ML<SK-DA", "AI-GNN<AI-ML", "SK-SQL", "AI-FIELD<SK-DA"),
                ("ai-sw", "소프트웨어·게임 개발", "소프트웨어 개발자, 게임 프로그래머", "sw-developer", "SK-PY-01!", "SK-ALGO!<SK-PY-01", "SK-WEB<SK-ALGO", "AI-IR", "SK-INFO-PE<SK-ALGO"),
                ("ai-startup", "AI 스타트업", "AI 기술로 창업하거나 스타트업에 합류한다", "founder", "AI-ML!", "AI-CAP!<AI-ML", "SK-IDEA", "SK-MVP<AI-CAP", "SK-IR<SK-MVP")]),
    "data-science": dict(
        skills=[("DS-VIZ", "데이터 수집·분석·시각화", "교육", "r"), ("DS-MULTI", "다변량 데이터 분석", "교육", "r"), ("DS-DIST", "분산컴퓨팅", "교육", "r"), ("DS-MINING", "데이터마이닝", "교육", "r"),
                ("DS-ML", "머신러닝·딥러닝", "교육", "r"), ("DS-CAP", "데이터사이언스 캡스톤디자인", "프로젝트", "r"), ("DS-DB", "데이터베이스", "교육", "r"),
                ("DS-C-SURVEY", "사회조사분석사", "자격증", "k"), ("DS-C-INFO", "정보처리기사", "자격증", "k")],
        tracks=[("ds-scientist", "데이터 사이언티스트", "분석 체계를 만들고 의사결정안을 도출한다", "data-analyst", "DS-VIZ!", "DS-ML!<DS-VIZ", "DS-MULTI<DS-VIZ", "DS-CAP!<DS-ML", "SK-ADSP"),
                ("ds-analyst", "빅데이터 분석가", "기업 데이터를 분석해 문제를 해결한다", "data-analyst", "DS-VIZ!", "SK-SQL!", "DS-MINING<DS-VIZ", "DS-C-SURVEY", "SK-SQLD<SK-SQL"),
                ("ds-engineer", "빅데이터 엔지니어", "빅데이터를 처리·개발하고 운영한다", "sw-developer", "DS-DB!", "DS-DIST!<DS-DB", "SK-ALGO", "DS-C-INFO<DS-DB", "SK-DEPLOY<DS-DIST"),
                ("ds-consult", "데이터 분석 컨설턴트", "컨설팅·금융·광고 분야에서 데이터로 자문한다", "data-analyst", "DS-VIZ!", "DS-MULTI!<DS-VIZ", "SK-PPT", "SK-TOEIC", "DS-CAP<DS-MULTI")]),
    "cs": dict(
        skills=[("CS-DS", "자료구조·알고리즘 설계", "교육", "r"), ("CS-OS", "운영체제·컴퓨터구조", "교육", "r"), ("CS-NET", "컴퓨터 네트워크", "교육", "r"), ("CS-SEC", "네트워크·시스템 보안", "교육", "r"),
                ("CS-DB", "데이터베이스 설계", "교육", "r"), ("CS-SE", "소프트웨어 공학", "교육", "r"), ("CS-EMB", "임베디드·모바일", "교육", "r"), ("CS-IS", "정보시스템 분석·설계", "교육", "r"),
                ("CS-C-LINUX", "리눅스마스터", "자격증", "k"), ("CS-C-NET", "네트워크관리사", "자격증", "k")],
        tracks=[("cs-dev", "소프트웨어 개발자", "서비스와 응용 프로그램을 만든다", "sw-developer", "CS-DS!", "CS-SE<CS-DS", "SK-WEB!<CS-DS", "CS-EMB<CS-DS", "CS-DB", "SK-INFO-PE<CS-DS", "SK-PORT<SK-WEB"),
                ("cs-system", "시스템 엔지니어", "서버·네트워크·운영 환경을 다룬다", "sw-developer", "CS-OS!", "CS-NET!<CS-OS", "CS-C-LINUX<CS-OS", "CS-C-NET<CS-NET", "SK-INFO-PE"),
                ("cs-security", "보안 전문가", "네트워크와 시스템을 보호한다", "sw-developer", "CS-NET!", "CS-SEC!<CS-NET", "CS-OS", "CS-C-LINUX", "SK-INFO-PE"),
                ("cs-consult", "정보화 컨설턴트", "조직의 정보시스템을 분석하고 설계한다", "data-analyst", "CS-IS!", "CS-DB!", "CS-SE<CS-IS", "SK-PPT", "SK-INFO-PE"),
                ("cs-public", "전산직 공무원", "공공기관의 전산 업무를 맡는다", "public-sector", "CS-DS!", "CS-DB", "SK-INFO-PE!<CS-DS", "SK-KHIST")]),
    "kor-lit": dict(
        skills=[("KOR-TEXT", "텍스트 분석·작성", "교육", "c"), ("KOR-EDIT", "교정·출판 편집", "교육", "c"), ("KOR-CREATE", "창작(시·소설·실용)", "프로젝트", "c"), ("KOR-TEACH", "독서·작문 지도", "교육", "c"),
                ("KOR-FEST", "학과 학술제·학술답사", "경험", "c"), ("KOR-CONTEST", "응용작품대회·문예 공모", "경험", "c"), ("KOR-C-TEACH", "중등 정교사 2급(국어)", "자격증", "k")],
        tracks=[("kor-edu", "국어 교육", "교사, 독서·논술 지도", "educator", "KOR-TEXT!", "KOR-TEACH!<KOR-TEXT", "KOR-C-TEACH<KOR-TEACH", "KOR-FEST"),
                ("kor-culture", "출판·언론·방송", "출판, 기자, 방송작가, 스토리텔러", "content-planner", "KOR-TEXT!", "KOR-EDIT!<KOR-TEXT", "KOR-FEST", "SK-WRITE", "SK-PORT<KOR-EDIT"),
                ("kor-ad", "광고·홍보", "광고회사, 기업 홍보, 카피라이터", "marketer", "KOR-TEXT!", "KOR-CONTEST", "SK-WRITE!<KOR-TEXT", "SK-MKT", "SK-SNS"),
                ("kor-writer", "창작", "시인, 소설가 등 작가", "content-planner", "KOR-CREATE!", "KOR-CONTEST!<KOR-CREATE", "KOR-FEST")]),
    "philosophy": dict(
        skills=[("PHI-LOGIC", "논리적 분석과 응용", "교육", "r"), ("PHI-READ", "철학 문헌 읽기·토론", "교육", "r"), ("PHI-ETHIC", "현대사회와 윤리 문제", "교육", "r"), ("PHI-EDU", "철학교과교육", "교육", "r"),
                ("PHI-C-TEACH", "중등 정교사 2급(철학)", "자격증", "k")],
        tracks=[("phi-edu", "논술·철학 교육", "아동 논술 교육, 윤리·철학 교사", "educator", "PHI-LOGIC!", "PHI-READ!", "PHI-EDU<PHI-READ", "PHI-C-TEACH<PHI-EDU"),
                ("phi-counsel", "청소년 상담", "청소년을 만나 고민을 듣는다", "welfare", "PHI-ETHIC!", "PHI-READ", "SK-COUNSEL<PHI-ETHIC", "SK-VOL"),
                ("phi-plan", "공연·전시 기획", "문화 콘텐츠를 기획한다", "arts-planner", "PHI-READ!", "SK-WRITE", "SK-CONTENT<PHI-READ", "SK-ARTS-PLAN<SK-CONTENT"),
                ("phi-biz", "기업·금융·IT", "논리력을 살려 기업과 금융권, IT로 간다(복수전공 권장)", "finance", "PHI-LOGIC!", "SK-PPT", "SK-COMP", "SK-TOEIC")]),
    "english": dict(
        skills=[("ENG-ESSAY", "영어 에세이 쓰기", "교육", "r"), ("ENG-PRES", "영어 발표", "교육", "r"), ("ENG-TRANS", "번역의 원리와 응용", "교육", "r"), ("ENG-LIT", "영미문학·스토리텔링", "교육", "r"),
                ("ENG-EDU", "영어교과교육론·지도법", "교육", "r"), ("ENG-C-TEACH", "중등 정교사(영어, 교직 이수)", "자격증", "c"), ("ENG-C-TRADE", "무역영어", "자격증", "k")],
        tracks=[("eng-global", "외국계기업·무역", "외국계기업과 무역회사에서 일한다", "overseas-sales", "ENG-ESSAY!", "ENG-PRES!<ENG-ESSAY", "SK-TOEIC!", "SK-OPIC", "ENG-C-TRADE"),
                ("eng-edu", "영어 교육", "교직 이수 후 영어 교사·강사", "educator", "ENG-ESSAY!", "ENG-EDU!<ENG-ESSAY", "ENG-C-TEACH<ENG-EDU", "SK-TOEIC"),
                ("eng-trans", "출판·통번역", "출판과 통번역 분야", "content-planner", "ENG-ESSAY!", "ENG-TRANS!<ENG-ESSAY", "ENG-LIT", "SK-PORT<ENG-TRANS"),
                ("eng-content", "문화마케팅·미디어콘텐츠", "문화마케팅·브랜딩, 미디어콘텐츠 창작·기획", "marketer", "ENG-LIT!", "ENG-PRES", "SK-CONTENT<ENG-LIT", "SK-MKT", "SK-SNS"),
                ("eng-public", "공기업·공공기관", "어학 능력을 살려 공공 부문으로 간다", "public-sector", "SK-TOEIC!", "SK-NCS!", "SK-KHIST", "SK-COMP")]),
    "chinese": dict(
        skills=[("CHN-TALK", "중국어 회화·프레젠테이션", "교육", "r"), ("CHN-BIZ", "통상중국어", "교육", "r"), ("CHN-TRANS", "AI 활용 중한번역 연습", "교육", "r"), ("CHN-CULTURE", "중국 지역문화", "교육", "r"),
                ("CHN-C-BCT", "BCT", "어학", "c"), ("CHN-C-TSC", "TSC", "어학", "c"), ("CHN-C-TCT", "TCT(번역능력인정시험)", "자격증", "c")],
        tracks=[("chn-trans", "통·번역", "국제회의 통역, 웹툰·미디어 번역", "content-planner", "CHN-TALK!", "CHN-TRANS!<CHN-TALK", "SK-HSK!", "CHN-C-TCT<CHN-TRANS"),
                ("chn-trade", "해외영업·유통", "중국 기업, 유통, 무역, 해외영업", "overseas-sales", "CHN-TALK!", "CHN-BIZ!<CHN-TALK", "SK-HSK!", "CHN-C-BCT", "CHN-C-TSC"),
                ("chn-content", "문화콘텐츠·엔터테인먼트", "출판, 게임, 여행, 스포츠 마케팅", "content-planner", "CHN-CULTURE!", "CHN-TALK", "SK-HSK", "SK-CONTENT<CHN-CULTURE"),
                ("chn-edu", "중국어 교육", "어린이 중국어 교육, 중국어 강사", "educator", "CHN-TALK!", "SK-HSK!", "CHN-C-TSC"),
                ("chn-public", "공무원·공기업", "외무영사, KOTRA 등", "public-sector", "SK-HSK!", "SK-NCS", "SK-KHIST", "SK-TOEIC")]),
    "japanese": dict(
        skills=[("JPN-TALK", "일본어 회화·작문·경어", "교육", "r"), ("JPN-TRANS", "일한 번역", "교육", "r"), ("JPN-NEWS", "시사 일본어 토론", "교육", "r"), ("JPN-SOC", "일본 사회·문화 이해", "교육", "r")],
        tracks=[("jpn-biz", "일본계·일본 진출 기업", "일본 기업 또는 일본에 진출한 국내 기업", "overseas-sales", "JPN-TALK!", "JPN-NEWS<JPN-TALK", "SK-JLPT!", "SK-TOEIC"),
                ("jpn-trans", "통·번역", "도서·영화·웹툰·웹소설 번역, 행사 통역", "content-planner", "JPN-TALK!", "JPN-TRANS!<JPN-TALK", "SK-JLPT!", "SK-PORT<JPN-TRANS"),
                ("jpn-edu", "일본어 교육", "교사, 강사, 교재 개발", "educator", "JPN-TALK!", "JPN-SOC", "SK-JLPT!"),
                ("jpn-local", "일본 현지 취업", "일본에서 일한다", "overseas-sales", "JPN-TALK!", "JPN-SOC!", "SK-JLPT!<JPN-TALK", "SK-RESUME")]),
    "korean-culture": dict(
        skills=[("KLC-TEACH", "한국어 교수법(말하기·듣기·읽기·쓰기 교육)", "교육", "r"), ("KLC-MATERIAL", "한국어 교재·교육 콘텐츠 제작", "프로젝트", "r"), ("KLC-TEST", "한국어능력평가", "교육", "r"),
                ("KLC-PRACT", "한국어 교실수업의 실제", "경험", "r"), ("KLC-CONTENT", "한국언어문화콘텐츠 설계", "프로젝트", "r"), ("KLC-C-TEACH", "한국어교원 2급", "자격증", "k")],
        tracks=[("klc-teacher", "한국어 교원", "외국인에게 한국어를 가르친다", "educator", "KLC-TEACH!", "KLC-PRACT!<KLC-TEACH", "KLC-TEST", "KLC-C-TEACH!<KLC-PRACT"),
                ("klc-content", "문화콘텐츠 전문가", "한국 문화 콘텐츠를 기획하고 쓴다", "content-planner", "KLC-CONTENT!", "KLC-MATERIAL<KLC-CONTENT", "SK-WRITE", "SK-VIDEO"),
                ("klc-material", "한국어 교재·콘텐츠 개발", "교재와 교육 콘텐츠를 만든다", "educator", "KLC-TEACH!", "KLC-MATERIAL!<KLC-TEACH", "KLC-TEST")]),
    "sociology": dict(
        skills=[("SOC-SURVEY", "사회조사·통계 분석", "교육", "r"), ("SOC-POLICY", "공공사회정책", "교육", "r"), ("SOC-CONFLICT", "사회갈등·사회운동 연구", "교육", "r"), ("SOC-CORP", "기업과 사회(경영학 연계)", "교육", "r"),
                ("SOC-C-SURVEY", "사회조사분석사", "자격증", "c")],
        tracks=[("soc-research", "사회조사·연구원", "공공·민간 연구소에서 사회를 조사한다", "data-analyst", "SOC-SURVEY!", "SK-STAT<SOC-SURVEY", "SOC-C-SURVEY!<SOC-SURVEY", "SK-POLICY"),
                ("soc-public", "공공정책·공무원", "정책을 만들고 집행한다", "public-sector", "SOC-POLICY!", "SOC-C-SURVEY", "SK-NCS", "SK-KHIST"),
                ("soc-media", "언론·콘텐츠", "기자, 아나운서, PD, 작가", "content-planner", "SOC-CONFLICT!", "SK-WRITE!", "SK-CONTENT<SK-WRITE", "SK-VIDEO"),
                ("soc-pr", "홍보·기획·마케팅", "기업의 홍보와 마케팅", "marketer", "SOC-CORP!", "SOC-SURVEY", "SK-MKT<SOC-CORP", "SK-SNS"),
                ("soc-ngo", "사회단체·국제 NGO", "시민사회에서 일한다", "npo", "SOC-CONFLICT!", "SK-VOL", "SK-NPO<SOC-CONFLICT", "SK-TOEIC")]),
    "child": dict(
        skills=[("CHD-DEV", "영유아 발달·교수방법", "교육", "c"), ("CHD-PLAY", "놀이지도", "교육", "c"), ("CHD-OBS", "아동관찰 및 행동연구", "교육", "c"), ("CHD-PRACT", "보육실습 6주 240시간", "경험", "c"),
                ("CHD-PARENT", "부모교육·아동상담", "교육", "c"), ("CHD-C-CARE", "보육교사 2급", "자격증", "c"), ("CHD-C-PLAY", "놀이심리재활사", "자격증", "c"), ("CHD-C-KINDER", "유치원 정교사(교직 이수)", "자격증", "c")],
        tracks=[("chd-care", "보육교사", "국공립·직장·재단 어린이집", "educator", "CHD-DEV!", "CHD-PLAY!<CHD-DEV", "CHD-OBS<CHD-DEV", "CHD-PRACT!<CHD-PLAY", "CHD-C-CARE!<CHD-PRACT"),
                ("chd-kinder", "유치원 교사", "교직과정을 이수해 유치원 정교사가 된다", "educator", "CHD-DEV!", "CHD-PLAY", "CHD-C-KINDER!<CHD-DEV", "CHD-C-CARE"),
                ("chd-therapy", "놀이심리재활사", "놀이로 아동의 발달을 돕는다", "welfare", "CHD-DEV!", "CHD-OBS!<CHD-DEV", "CHD-PARENT<CHD-OBS", "CHD-C-PLAY!<CHD-OBS"),
                ("chd-content", "교재교구·아동출판", "영유아 교재교구 개발, 아동문학 출판", "content-planner", "CHD-DEV!", "CHD-PLAY", "SK-CONTENT<CHD-PLAY", "SK-WRITE"),
                ("chd-policy", "육아정책·보육 행정", "연구원, 보육 행정·정책 담당", "public-sector", "CHD-DEV!", "CHD-PARENT", "SK-POLICY<CHD-DEV", "CHD-C-CARE")]),
    "intl": dict(
        skills=[("INT-AREA", "지역연구(미국·중국·일본·유럽·동남아)", "교육", "r"), ("INT-TRADE", "통상실무개론", "교육", "r"), ("INT-DEV", "국제개발협력", "교육", "r"), ("INT-DIPLO", "외교정책 분석", "교육", "r"),
                ("INT-METHOD", "국제학 방법론", "교육", "r")],
        tracks=[("int-gov", "정부·외교", "외교부, 산업통상자원부, KOICA 등", "public-sector", "INT-DIPLO!", "INT-AREA!", "SK-TOEIC!", "SK-KHIST", "SK-NCS"),
                ("int-trade", "통상·민간기업", "대기업·외국계기업의 통상과 해외 업무", "overseas-sales", "INT-TRADE!", "INT-AREA", "SK-TOEIC!", "SK-OPIC", "SK-TRADE<INT-TRADE"),
                ("int-ngo", "국제개발·시민단체", "국제개발협력과 NGO", "npo", "INT-DEV!", "INT-AREA", "SK-VOL", "SK-NPO<INT-DEV", "SK-TOEIC"),
                ("int-media", "언론", "방송·통신·신문사", "content-planner", "INT-AREA!", "INT-METHOD", "SK-WRITE!", "SK-TOEIC"),
                ("int-finance", "금융권", "은행·증권", "finance", "INT-TRADE!", "SK-FIN", "SK-TOEIC", "SK-COMP")]),
    "law": dict(
        skills=[("LAW-CIVIL", "민사법(민법총칙·채권·물권)", "교육", "r"), ("LAW-CRIM", "형사법(형법총론·각론)", "교육", "r"), ("LAW-CONST", "헌법", "교육", "r"), ("LAW-ADMIN", "행정법", "교육", "r"),
                ("LAW-COMM", "상법·회사법", "교육", "r"), ("LAW-LABOR", "노동법", "교육", "r"), ("LAW-FEST", "학술제·학회 활동", "경험", "c"), ("LAW-C-LABOR", "공인노무사", "자격증", "c")],
        tracks=[("law-school", "법학전문대학원", "로스쿨에 진학해 법조인이 된다", "legal", "LAW-CONST!", "LAW-CIVIL!", "LAW-CRIM!", "SK-TOEIC!", "LAW-FEST"),
                ("law-court", "법원직·검찰직 공무원", "법원과 검찰에서 일한다", "public-sector", "LAW-CONST!", "LAW-CRIM!", "LAW-CIVIL", "SK-KHIST", "SK-TOEIC"),
                ("law-admin", "일반행정직 공무원", "헌법·행정법을 바탕으로 공직에 진출한다", "public-sector", "LAW-CONST!", "LAW-ADMIN!<LAW-CONST", "SK-KHIST", "SK-TOEIC"),
                ("law-corp", "기업 법무·공기업", "상법·민법 지식으로 기업과 공기업에서 일한다", "legal", "LAW-COMM!", "LAW-CIVIL!", "SK-LAW-DOC<LAW-CIVIL", "SK-NCS", "SK-TOEIC"),
                ("law-labor", "공인노무사", "노동 관계 전문가", "legal", "LAW-LABOR!", "LAW-CIVIL", "LAW-C-LABOR!<LAW-LABOR")]),
    "economics": dict(
        skills=[("ECO-MICRO", "미시·거시경제 분석", "교육", "c"), ("ECO-METRIC", "계량 분석", "교육", "c"), ("ECO-FIN", "금융·화폐 경제", "교육", "c"), ("ECO-C-FP", "자산관리사(FP)", "자격증", "k"), ("ECO-C-CREDIT", "신용분석사", "자격증", "k")],
        tracks=[("eco-finance", "금융기관", "은행·증권에서 일한다", "finance", "ECO-MICRO!", "ECO-FIN!<ECO-MICRO", "ECO-C-FP", "ECO-C-CREDIT", "SK-TOEIC"),
                ("eco-corp", "기업 기획·조사", "기업의 기획·조사 부서, 컨설팅", "finance", "ECO-MICRO!", "ECO-METRIC!<ECO-MICRO", "SK-PPT", "SK-COMP", "SK-TOEIC"),
                ("eco-public", "정부·금융공기업", "경제 정책과 금융공기업", "public-sector", "ECO-MICRO!", "ECO-FIN", "SK-NCS!", "SK-KHIST", "SK-TOEIC"),
                ("eco-research", "연구기관", "국책·민간 연구소", "data-analyst", "ECO-METRIC!", "SK-STAT<ECO-METRIC", "SK-POLICY", "SK-SCI-PAPER<SK-STAT")]),
    "public-admin": dict(
        skills=[("PA-POLICY", "정책 분석·평가", "교육", "c"), ("PA-MANAGE", "공공 관리·조직", "교육", "c"), ("PA-C-ADMIN", "행정사", "자격증", "k"), ("PA-C-LABOR", "공인노무사", "자격증", "k")],
        tracks=[("pa-gov", "공무원", "중앙·지방 정부, 경찰·검찰·법원", "public-sector", "PA-POLICY!", "PA-MANAGE!", "SK-KHIST!", "SK-TOEIC"),
                ("pa-public", "공공기관·공기업", "공사·공단에서 일한다", "public-sector", "PA-MANAGE!", "SK-NCS!", "SK-KHIST", "SK-COMP", "SK-TOEIC"),
                ("pa-research", "정책 연구소", "정책을 평가하고 연구한다", "data-analyst", "PA-POLICY!", "SK-POLICY!<PA-POLICY", "SK-STAT"),
                ("pa-expert", "전문 자격", "행정사, 노무사, 관세사 등", "legal", "PA-POLICY!", "PA-C-ADMIN", "PA-C-LABOR")]),
    "business": dict(
        skills=[("BIZ-MKT", "마케팅·시장조사·마케팅데이터분석", "교육", "r"), ("BIZ-FIN", "재무관리·투자론", "교육", "r"), ("BIZ-HR", "인적자원관리·조직행위론", "교육", "r"), ("BIZ-OPS", "생산운영·SCM", "교육", "r"),
                ("BIZ-STRATEGY", "경영전략·국제경영", "교육", "r"), ("BIZ-FIELD", "경영학 현장실습", "경험", "r"), ("BIZ-CAP", "경영학 캡스톤디자인", "프로젝트", "r"),
                ("BIZ-C-CONSULT", "경영지도사", "자격증", "k"), ("BIZ-C-LOGIS", "물류관리사", "자격증", "k"), ("BIZ-C-SURVEY", "사회조사분석사", "자격증", "k")],
        tracks=[("biz-marketing", "마케팅", "시장을 조사하고 브랜드를 키운다", "marketer", "BIZ-MKT!", "BIZ-C-SURVEY", "SK-MKT!<BIZ-MKT", "BIZ-FIELD", "SK-SNS"),
                ("biz-finance", "재무·금융", "기업 재무와 금융권", "finance", "BIZ-FIN!", "SK-FIN!<BIZ-FIN", "SK-COMP", "SK-TOEIC"),
                ("biz-hr", "인사·조직", "채용, 교육, 조직문화", "finance", "BIZ-HR!", "BIZ-FIELD<BIZ-HR", "BIZ-C-CONSULT", "SK-TOEIC"),
                ("biz-ops", "생산운영·물류", "생산과 공급망을 관리한다", "finance", "BIZ-OPS!", "BIZ-C-LOGIS<BIZ-OPS", "SK-COMP"),
                ("biz-strategy", "경영전략·국제경영", "전략 기획과 해외 사업", "overseas-sales", "BIZ-STRATEGY!", "BIZ-CAP<BIZ-STRATEGY", "SK-PPT", "SK-TOEIC!"),
                ("biz-startup", "창업", "사업을 직접 시작한다", "founder", "BIZ-STRATEGY!", "BIZ-CAP", "SK-IDEA!", "SK-BMC<SK-IDEA", "SK-BIZPLAN<SK-BMC")]),
    "global-business": dict(
        skills=[("GB-FIN", "다국적 기업 재무전략·M&A와 가치평가", "교육", "r"), ("GB-SCM", "글로벌 공급망 전략", "교육", "r"), ("GB-ESG", "다국적 기업과 ESG 경영", "교육", "r"), ("GB-MKT", "글로벌 마케팅·소비자행동", "교육", "r"),
                ("GB-STRATEGY", "국제경영·글로벌 경영전략", "교육", "r")],
        tracks=[("gb-foreign", "외국기업", "외국계 기업에서 일한다", "overseas-sales", "GB-STRATEGY!", "GB-MKT", "SK-TOEIC!", "SK-OPIC"),
                ("gb-finance", "금융기관", "은행·증권·투자", "finance", "GB-FIN!", "SK-FIN<GB-FIN", "SK-TOEIC"),
                ("gb-corp", "대기업·중견기업", "기획, 마케팅, 공급망", "finance", "GB-STRATEGY!", "GB-SCM", "GB-ESG", "SK-PPT", "SK-TOEIC"),
                ("gb-public", "공공기관·공무원", "공사·공기업, 7·9급", "public-sector", "GB-ESG", "SK-NCS!", "SK-KHIST!", "SK-TOEIC")]),
    "chemistry": dict(
        skills=[("CHE-ORG", "유기화학·유기합성 실험", "교육", "r"), ("CHE-ANAL", "분석화학·기기분석", "교육", "r"), ("CHE-PHYS", "물리화학·전기화학", "교육", "r"), ("CHE-INORG", "무기화학·나노재료화학", "교육", "r"),
                ("CHE-MATERIAL", "소재화학(유기·전자재료)", "교육", "r"), ("CHE-RESEARCH", "소재화학연구(심화연구)", "경험", "r"), ("CHE-EDU", "화학교과교육론", "교육", "r"), ("CHE-C-CHE", "화공기사", "자격증", "k")],
        tracks=[("che-pharma", "제약·바이오", "제약회사와 바이오 기업", "bio-qa", "CHE-ORG!", "CHE-ANAL!", "SK-LAB-ANAL<CHE-ANAL", "SK-GMP", "CHE-RESEARCH<CHE-ORG"),
                ("che-semi", "반도체·전자재료", "반도체와 전자 부품 소재", "electronics", "CHE-INORG!", "CHE-MATERIAL!<CHE-INORG", "CHE-PHYS", "CHE-RESEARCH<CHE-MATERIAL"),
                ("che-energy", "에너지·이차전지", "배터리와 에너지 소재", "env-engineer", "CHE-PHYS!", "CHE-MATERIAL<CHE-PHYS", "CHE-C-CHE", "CHE-RESEARCH<CHE-PHYS"),
                ("che-consumer", "화장품·생활용품", "화장품, 세제, 위생용품", "bio-qa", "CHE-ORG!", "CHE-ANAL!", "SK-LAB-ANAL<CHE-ANAL", "SK-BIO-QC"),
                ("che-research", "연구소·대학원", "석·박사 후 연구직", "bio-researcher", "CHE-ANAL!", "CHE-RESEARCH!", "SK-SCI-PAPER<CHE-RESEARCH"),
                ("che-edu", "화학 교사", "교직과정을 이수해 화학을 가르친다", "educator", "CHE-ORG!", "CHE-EDU!")]),
    "math": dict(
        skills=[("MAT-ANAL", "해석학·대수학", "교육", "r"), ("MAT-STAT", "확률론·수리통계학·자료분석", "교육", "r"), ("MAT-FIN", "금융수학·전산금융·위험관리론", "교육", "r"), ("MAT-ML", "기계학습의 수학적 이론·딥러닝", "교육", "r"),
                ("MAT-PROG", "수학프로그래밍·계산수학", "교육", "r"), ("MAT-C-ACTUARY", "보험계리사", "자격증", "k"), ("MAT-C-SURVEY", "사회조사분석사", "자격증", "k")],
        tracks=[("mat-finance", "금융·리스크", "금융수학으로 금융권과 보험으로 간다(로드맵 기준)", "finance", "MAT-STAT!", "MAT-FIN!<MAT-STAT", "MAT-C-ACTUARY<MAT-FIN", "SK-FIN"),
                ("mat-data", "데이터·AI", "수학적 기반으로 데이터와 AI를 다룬다(로드맵 기준)", "data-analyst", "MAT-STAT!", "MAT-PROG!", "MAT-ML<MAT-PROG", "SK-PY-01", "MAT-C-SURVEY"),
                ("mat-pure", "대학원·교육", "수학을 더 공부하거나 가르친다(로드맵 기준)", "educator", "MAT-ANAL!", "MAT-STAT", "SK-SCI-PAPER<MAT-ANAL")]),
    "physics": dict(
        skills=[("PHY-LAB", "현대·고급물리학실험", "교육", "r"), ("PHY-COMP", "전산물리와 딥러닝", "교육", "r"), ("PHY-SEMI", "반도체·고체물리학", "교육", "r"), ("PHY-QUANT", "양자역학·전자기학", "교육", "r"),
                ("PHY-SIM", "복잡계 시뮬레이션 나노디그리", "교육", "r")],
        tracks=[("phy-semi", "반도체·디스플레이", "전기·전자·반도체 산업체", "electronics", "PHY-QUANT!", "PHY-SEMI!<PHY-QUANT", "PHY-LAB", "SK-CIRCUIT"),
                ("phy-research", "연구소·대학원", "국공립·대기업 연구소", "bio-researcher", "PHY-QUANT!", "PHY-LAB!", "SK-SCI-PAPER<PHY-LAB"),
                ("phy-sim", "시뮬레이션·데이터", "전산물리와 딥러닝으로 금융·기술평가까지", "data-analyst", "PHY-COMP!", "PHY-SIM<PHY-COMP", "SK-PY-01!", "SK-DA<SK-PY-01")]),
    "space-design": dict(
        skills=[("SPD-DRAW", "제도·표현기법", "교육", "r"), ("SPD-CAD", "CAD(Computer Aided Design)", "교육", "r"), ("SPD-HOUSE", "주택설계", "프로젝트", "r"), ("SPD-INTERIOR", "실내디자인 프로젝트", "프로젝트", "r"),
                ("SPD-VMD", "VMD(비주얼머천다이징)·실내 코디네이션", "교육", "r"), ("SPD-FURN", "가구디자인 종합설계", "프로젝트", "r"), ("SPD-PORT", "포트폴리오 디자인", "프로젝트", "r"),
                ("SPD-CONSUMER", "소비자학 캡스톤디자인(소비자조사·상품기획)", "프로젝트", "r"), ("SPD-C-INTERIOR", "실내건축기사", "자격증", "k"), ("SPD-C-COLOR", "컬러리스트기사", "자격증", "k")],
        tracks=[("spd-interior", "인테리어 디자인", "주거·상업·전시 공간을 설계한다", "designer", "SPD-DRAW!", "SPD-CAD!<SPD-DRAW", "SPD-INTERIOR!<SPD-CAD", "SPD-C-INTERIOR<SPD-INTERIOR", "SPD-PORT<SPD-INTERIOR"),
                ("spd-house", "주택설계·도시재생", "단독주택·아파트 설계, 문화공간 기획", "designer", "SPD-DRAW!", "SPD-CAD!<SPD-DRAW", "SPD-HOUSE!<SPD-CAD", "SPD-PORT<SPD-HOUSE"),
                ("spd-vmd", "VMD·실내 코디네이션", "매장 연출과 인테리어 스타일링", "designer", "SPD-VMD!", "SPD-C-COLOR", "SPD-PORT<SPD-VMD", "SPD-FURN"),
                ("spd-consumer", "소비자조사·상품기획", "소비자를 조사하고 상품과 서비스를 기획한다", "marketer", "SPD-CONSUMER!", "SK-MKT<SPD-CONSUMER", "SK-STAT", "SK-COMP"),
                ("spd-cs", "기업 CS·유통", "기업 고객 서비스, 소매유통", "marketer", "SPD-CONSUMER!", "SK-PPT", "SK-COMP")]),
    "food-nutrition": dict(
        skills=[("FN-PROCESS", "식품가공학·식품화학 실험", "교육", "r"), ("FN-CLINIC", "임상영양학·식사요법", "교육", "r"), ("FN-ASSESS", "영양판정·영양교육 및 상담", "교육", "r"), ("FN-MEAL", "단체급식관리·급식경영학", "교육", "r"),
                ("FN-FIELD", "영양사 현장실습", "경험", "r"), ("FN-MKT", "외식마케팅", "교육", "r"), ("FN-C-TEACH", "영양교사(교직 이수)", "자격증", "c"), ("FN-C-SANIT", "위생사", "자격증", "k")],
        tracks=[("fn-dietitian", "임상·급식 영양사", "병원과 단체급식의 영양사", "food", "FN-CLINIC!", "FN-MEAL!", "FN-FIELD!<FN-MEAL", "SK-DIET!<FN-FIELD", "FN-C-SANIT"),
                ("fn-teacher", "영양교사", "학교에서 급식과 영양 교육을 맡는다", "educator", "FN-ASSESS!", "FN-MEAL!", "SK-DIET!<FN-MEAL", "FN-C-TEACH!<SK-DIET"),
                ("fn-research", "식품기업 연구원", "식품을 개발하고 품질을 관리한다", "food", "FN-PROCESS!", "SK-HACCP<FN-PROCESS", "SK-LAB-ANAL", "FN-C-SANIT"),
                ("fn-md", "식품 MD·외식경영", "식품 상품기획과 외식 사업", "marketer", "FN-MKT!", "FN-PROCESS", "SK-MKT<FN-MKT", "SK-BIZPLAN"),
                ("fn-health", "헬스케어 컨설턴트", "영양 상담으로 건강을 관리한다", "food", "FN-ASSESS!", "FN-CLINIC!", "SK-DIET<FN-CLINIC"),
                ("fn-public", "식품·보건 공무원", "식품 안전과 보건 행정", "public-sector", "FN-PROCESS!", "SK-DIET", "FN-C-SANIT", "SK-KHIST")]),
    "biotech": dict(
        skills=[("BT-RED", "RED Bio 마이크로디그리(바이오의약품·면역학)", "교육", "r"), ("BT-GREEN", "GREEN Bio 마이크로디그리(산업미생물·발효공학)", "교육", "r"), ("BT-WHITE", "WHITE Bio 마이크로디그리(유전공학·생물공정)", "교육", "r"),
                ("BT-EXP", "Bio Experiment Expert(BT 실험)", "교육", "r"), ("BT-RESEARCH", "심화연구실습", "경험", "r"), ("BT-C-BIO", "생물공학기사", "자격증", "k"), ("BT-C-FOOD", "식품기사", "자격증", "k")],
        tracks=[("bt-pharma", "제약·바이오벤처", "신약 개발, 임상, 품질관리", "bio-researcher", "BT-EXP!", "BT-RED!<BT-EXP", "BT-RESEARCH<BT-RED", "SK-GMP", "BT-C-BIO"),
                ("bt-qc", "병원 연구소·QC", "임상 데이터 분석과 생산 품질관리", "bio-qa", "BT-EXP!", "BT-WHITE<BT-EXP", "SK-BIO-QC!<BT-EXP", "SK-GMP", "BT-C-BIO"),
                ("bt-food", "식품·기능성 화장품", "발효와 미생물로 제품을 만든다", "food", "BT-EXP!", "BT-GREEN!<BT-EXP", "BT-C-FOOD", "SK-HACCP"),
                ("bt-public", "공무원·연구기관", "식약처, 환경부, 국가 연구소", "public-sector", "BT-EXP!", "BT-RESEARCH", "BT-C-BIO", "SK-KHIST"),
                ("bt-startup", "생명공학 창업", "바이오 기술로 창업한다", "founder", "BT-WHITE!", "BT-RESEARCH<BT-WHITE", "SK-IDEA", "SK-BIZPLAN<SK-IDEA")]),
    "biomed-chem": dict(
        skills=[("BMC-PHARM", "제약공정 마이크로디그리", "교육", "r"), ("BMC-BIO", "첨단바이오의약품 마이크로디그리", "교육", "r"), ("BMC-COSME", "화장품소재 마이크로디그리", "교육", "r"), ("BMC-SEMI", "반도체 공정·BioMEMS 마이크로디그리", "교육", "r"),
                ("BMC-REACT", "화공 반응 공정 마이크로디그리", "교육", "r"), ("BMC-DIAG", "분자질병진단 마이크로디그리", "교육", "r"), ("BMC-C-CHE", "화공기사", "자격증", "k"), ("BMC-C-ANAL", "화학분석기사", "자격증", "k"), ("BMC-C-HAZ", "위험물산업기사", "자격증", "k")],
        tracks=[("bmc-pharma", "제약", "제약 공정과 의약품 생산", "pharma", "BMC-PHARM!", "SK-GMP<BMC-PHARM", "BMC-C-ANAL", "SK-BIO-QC"),
                ("bmc-bio", "바이오의약품", "바이오 기업의 생산·개발", "bio-qa", "BMC-BIO!", "SK-GMP!<BMC-BIO", "SK-BIO-LAB", "BMC-C-ANAL"),
                ("bmc-cosmetic", "화장품", "화장품 소재와 제형", "bio-qa", "BMC-COSME!", "BMC-C-ANAL<BMC-COSME", "SK-LAB-ANAL"),
                ("bmc-semi", "반도체·이차전지", "반도체 공정과 배터리 소재", "electronics", "BMC-SEMI!", "BMC-C-CHE<BMC-SEMI", "SK-LAB-ANAL"),
                ("bmc-energy", "정유·에너지·화학", "화학 공정과 에너지 산업", "env-engineer", "BMC-REACT!", "BMC-C-CHE!<BMC-REACT", "BMC-C-HAZ"),
                ("bmc-device", "의료기기·진단", "진단 기술과 의료기기", "bio-researcher", "BMC-DIAG!", "SK-BIO-LAB", "SK-RA<BMC-DIAG")]),
    "ai-biomed": dict(
        skills=[("ABE-SIGNAL", "생체신호 처리", "교육", "r"), ("ABE-IMAGE", "의료영상·생체디지털영상처리", "교육", "r"), ("ABE-MEASURE", "의용계측·의료센서", "교육", "r"), ("ABE-ML", "헬스케어 머신러닝·딥러닝", "교육", "r"),
                ("ABE-LAB", "ABME 경험랩", "경험", "r"), ("ABE-CAP", "ABME 캡스톤디자인", "프로젝트", "r"), ("ABE-C-BME", "의공기사", "자격증", "k")],
        tracks=[("abe-ai", "의료 AI", "디지털 헬스케어 기업에서 의료 AI를 만든다", "ai-engineer", "SK-PY-01!", "ABE-ML!<SK-PY-01", "ABE-IMAGE<ABE-ML", "ABE-CAP!<ABE-ML"),
                ("abe-device", "의료기기", "의료기기를 개발하고 시험한다", "electronics", "ABE-MEASURE!", "ABE-SIGNAL!", "ABE-C-BME<ABE-MEASURE", "ABE-LAB", "SK-RA"),
                ("abe-hospital", "대학병원·정부출연기관", "병원과 식약처 등 공공 연구기관", "bio-researcher", "ABE-SIGNAL!", "ABE-IMAGE", "ABE-LAB!", "SK-SCI-PAPER<ABE-LAB"),
                ("abe-startup", "디지털 헬스케어 창업", "헬스케어 스타트업을 만든다", "founder", "ABE-ML!", "ABE-CAP<ABE-ML", "SK-IDEA", "SK-MVP<ABE-CAP")]),
    "biomed-science": dict(
        skills=[("MBS-DIAG", "의학분자진단학", "교육", "r"), ("MBS-OMICS", "유전체학·전사체학", "교육", "r"), ("MBS-STEM", "줄기세포연구 종합설계", "프로젝트", "r"), ("MBS-DRUG", "분자모델링 기반 신약개발", "교육", "r"),
                ("MBS-LAB", "의생명과학실험", "교육", "r"), ("MBS-C-BIO", "생물공학기사", "자격증", "k")],
        tracks=[("mbs-pharma", "제약회사", "QC·QA, 임상설계, 개발부서", "bio-qa", "MBS-LAB!", "MBS-DRUG<MBS-LAB", "SK-GMP!", "SK-BIO-QC<MBS-LAB", "MBS-C-BIO"),
                ("mbs-diag", "진단·바이오벤처", "분자진단과 바이오 기업", "bio-researcher", "MBS-LAB!", "MBS-DIAG!<MBS-LAB", "MBS-OMICS", "SK-BIOINFO<MBS-OMICS"),
                ("mbs-institute", "국가 연구소", "질병관리청, 식약처, 국과수 등", "bio-researcher", "MBS-LAB!", "MBS-OMICS", "SK-SCI-PAPER<MBS-LAB", "SK-KHIST"),
                ("mbs-grad", "대학원(학석사연계)", "줄기세포·신약 연구를 이어간다", "bio-researcher", "MBS-LAB!", "MBS-STEM!<MBS-LAB", "SK-SCI-PAPER<MBS-STEM")]),
    "biomed-sw": dict(
        skills=[("BSW-SIGNAL", "생체신호·의료영상 처리", "교육", "r"), ("BSW-ML", "헬스케어 머신러닝·딥러닝·생성형 AI", "교육", "r"), ("BSW-DATA", "의료 빅데이터 분석", "교육", "r"), ("BSW-BIOINFO", "AI 바이오인포매틱스", "교육", "r"),
                ("BSW-CAP", "산학·임상 의료AI 종합설계", "프로젝트", "r"), ("BSW-FIELD", "BMSW 현장실습", "경험", "r"), ("BSW-ETHIC", "의료 AI 윤리", "교육", "r")],
        tracks=[("bsw-dev", "의료 소프트웨어 개발자", "병원과 헬스케어의 소프트웨어를 만든다", "sw-developer", "SK-PY-01!", "BSW-ML!<SK-PY-01", "BSW-CAP!<BSW-ML", "BSW-ETHIC", "SK-ALGO"),
                ("bsw-device", "의료기기 개발", "의료기기의 소프트웨어와 신호 처리", "electronics", "BSW-SIGNAL!", "BSW-ML<BSW-SIGNAL", "BSW-FIELD", "SK-RA"),
                ("bsw-data", "의료 데이터·바이오인포매틱스", "병원·제약의 데이터를 분석한다", "data-analyst", "SK-PY-01!", "BSW-DATA!<SK-PY-01", "BSW-BIOINFO<BSW-DATA", "SK-SQL"),
                ("bsw-startup", "헬스케어 창업", "의료 AI로 창업한다", "founder", "BSW-ML!", "BSW-CAP<BSW-ML", "SK-IDEA", "SK-MVP<BSW-CAP")]),
    "music": dict(
        skills=[("MUS-MAJOR", "전공 실기(성악·관현악·피아노·작곡)", "교육", "r"), ("MUS-EAR", "시창·청음·화성", "교육", "r"), ("MUS-ENSEMBLE", "합창·합주", "경험", "r"), ("MUS-STAGE", "연주(무대 발표)", "경험", "r")],
        tracks=[("mus-orchestra", "오케스트라·합창단", "시립 오케스트라와 합창단", "arts-planner", "MUS-MAJOR!", "MUS-EAR!", "MUS-ENSEMBLE!<MUS-MAJOR", "MUS-STAGE<MUS-ENSEMBLE"),
                ("mus-edu", "음악 교육", "예술강사, 중·고등학교 음악 교사", "educator", "MUS-MAJOR!", "MUS-EAR", "MUS-STAGE"),
                ("mus-plan", "문화재단·예술회관", "공연을 기획하고 운영한다", "arts-planner", "MUS-ENSEMBLE!", "SK-ARTS-PLAN!", "SK-PERF"),
                ("mus-compose", "작곡·스튜디오", "게임 음악 작곡, 스튜디오·학원 창업", "founder", "MUS-MAJOR!", "MUS-EAR!", "SK-PORT", "SK-BIZPLAN")]),
    "vocal": dict(
        skills=[("VOC-MAJOR", "성악 실기·딕션", "교육", "c"), ("VOC-OPERA", "오페라·합창 무대", "경험", "c")],
        tracks=[("voc-singer", "성악가·오페라 가수", "오페라단과 무대에서 노래한다", "arts-planner", "VOC-MAJOR!", "VOC-OPERA!<VOC-MAJOR", "SK-PERF"),
                ("voc-choir", "합창단·뮤지컬", "전문 합창단원, 뮤지컬 배우", "arts-planner", "VOC-MAJOR!", "VOC-OPERA", "SK-PERF!"),
                ("voc-plan", "연출·공연기획", "음악 PD, 음악감독, 공연 기획", "arts-planner", "VOC-OPERA!", "SK-ARTS-PLAN!<VOC-OPERA", "SK-CONTENT"),
                ("voc-edu", "음악 교육·해설", "음악 교육자, 클래식 해설가", "educator", "VOC-MAJOR!", "SK-PPT")]),
    "pharmacy": dict(
        skills=[("PHM-ANAL", "약품분석·약물학·제제학", "교육", "r"), ("PHM-CLINIC", "임상약학 실무", "교육", "r"), ("PHM-INDUSTRY", "산업약학 실무", "교육", "r"), ("PHM-PRACT", "실무실습(기초·필수·심화)", "경험", "r"),
                ("PHM-C-LICENSE", "약사 면허(국가시험)", "자격증", "c")],
        tracks=[("phm-community", "개국·근무 약사", "약국에서 일하거나 약국을 연다", "pharma", "PHM-ANAL!", "PHM-PRACT!<PHM-ANAL", "PHM-C-LICENSE!<PHM-PRACT"),
                ("phm-hospital", "병원 약사", "병원에서 약과 관련된 문제를 해결한다", "pharma", "PHM-CLINIC!", "PHM-PRACT!<PHM-CLINIC", "PHM-C-LICENSE!<PHM-PRACT"),
                ("phm-industry", "제약회사", "생산관리, 개발·허가, 품질관리, 연구", "pharma", "PHM-INDUSTRY!", "PHM-PRACT<PHM-INDUSTRY", "PHM-C-LICENSE!<PHM-PRACT", "SK-GMP", "SK-RA"),
                ("phm-public", "공직 약사", "식약처, 보건소의 보건 행정", "public-sector", "PHM-ANAL!", "PHM-C-LICENSE!<PHM-ANAL", "SK-KHIST")]),
}


def url(dept: str, kind: str) -> str:
    name, seq = SRC[dept]
    if kind == "k":
        return K + str(seq)
    pages = raw.get(name, {}).get("pages", {})
    for key in (("roadmap", "career") if kind == "r" else ("career", "roadmap", "intro")):
        if pages.get(key, {}).get("url"):
            return pages[key]["url"].replace(":443", "")
    return raw.get(name, {}).get("site", "https://www.catholic.ac.kr/")


def node(spec: str) -> str:
    skill, _, pre = spec.partition("<")
    required = skill.endswith("!")
    skill = skill.rstrip("!")
    pre_ts = f', ["{pre.replace(",", chr(34) + ", " + chr(34))}"]' if pre else ""
    return f'n("{skill}", {"true" if required else "false"}{pre_ts})'


lines = [
    "// 자동 생성 파일 — 직접 고치지 말고 scripts/gen_dept_tracks.py의 명세를 고친 뒤 다시 생성한다. 학과별 테크 2차분.",
    "// 근거: 각 학과 홈페이지의 취업 및 진로·전공로드맵, 커리어넷 학과정보(2026-11-17~18 확인). 조사 내용은 docs/DEPT_TECH_TREES.md.",
    "// 선행 관계(순서)는 조사자가 정한 초안이다. 재학생 확인을 거치지 않은 학과가 대부분이다.",
    'import type { Job, Skill } from "../types";',
    "",
    'type Node = Job["nodes"][number];',
    "const n = (skill: string, required = false, prereq?: string[]): Node => ({ skill, required, prereq });",
    "",
    "export const DEPT_SKILLS_2: Skill[] = [",
]
for dept, spec in SPEC.items():
    lines.append(f"  // {SRC[dept][0]}")
    for sid, name, kind, src in spec["skills"]:
        frm = "커리어넷" if src == "k" else "학과"
        lines.append(f'  {{ id: "{sid}", name: {json.dumps(name, ensure_ascii=False)}, kind: "{kind}", verifiable: {"true" if kind in ("자격증", "어학") else "false"}, from: "{frm}", srcUrl: "{url(dept, src)}" }},')
lines += ["];", "", "export const DEPT_JOBS_2: Job[] = ["]
for dept, spec in SPEC.items():
    lines.append(f"  // {SRC[dept][0]}")
    for tid, name, summary, base, *nodes in spec["tracks"]:
        lines.append(
            f'  {{ id: "{tid}", name: {json.dumps(name, ensure_ascii=False)}, summary: {json.dumps(summary, ensure_ascii=False)}, fields: [], departments: ["{dept}"], base: "{base}", srcUrl: "{url(dept, "c")}", nodes: [{", ".join(node(x) for x in nodes)}] }},'
        )
lines += ["];", ""]
out_path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
print("학과", len(SPEC), "스킬", sum(len(s["skills"]) for s in SPEC.values()), "테크", sum(len(s["tracks"]) for s in SPEC.values()))
