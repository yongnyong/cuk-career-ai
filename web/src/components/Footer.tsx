import Link from "next/link";

export function Footer() {
  return (
    <footer className="mt-10 border-t border-line bg-panel pb-16 sm:pb-0">
      <div className="mx-auto max-w-6xl space-y-1 px-4 py-5 text-xs text-slate-500 2xl:max-w-[1880px]">
        <p>
          AI가 정리한 정보이니 원문을 확인하세요. 신청·선발은 각 공식 신청처에서 진행되며, 이 서비스의 이동 버튼은 신청 완료를 의미하지
          않습니다.
        </p>
        <p>
          화면의 &quot;가상 공고&quot;는 시연용 테스트 데이터로 실제 모집이 아닙니다. 개인정보(이름·학번·연락처)는 수집하지 않습니다.{" "}
          <Link href="/sources" className="underline">
            출처와 데이터 원칙
          </Link>{" "}
          <Link href="/admin" className="underline">
            관리자
          </Link>
        </p>
        <p>2026학년도 가톨릭대학교 생성형 AI 경진대회 출품작 · 팀 나 혼자만 레벨업 · 대회 이후 실제 서비스로 운영하지 않습니다.</p>
      </div>
    </footer>
  );
}
