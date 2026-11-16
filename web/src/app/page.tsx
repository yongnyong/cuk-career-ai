"use client";
import Link from "next/link";
import { ArrowRight, Bell, GitBranch, MessageSquareText, ShieldCheck } from "lucide-react";
import { useStore } from "@/lib/store";
import { DEPARTMENTS, COLLEGES } from "@/lib/data/departments";

const FEATURES = [
  { icon: GitBranch, title: "진로 스킬트리", text: "목표 직무까지 어학·자격·프로젝트를 노드로 보여주고, 실제 공고가 들어오면 해당 노드에서 기회가 열려요." },
  { icon: ShieldCheck, title: "자격 3단계 판정", text: "학년·학적·전공 같은 명시 조건은 코드가 판정하고, 애매한 조건은 '확인 필요'로 남겨요." },
  { icon: Bell, title: "마감·정정 알림", text: "D-7·3·1 알림, 마감이 바뀌면 이전 알림을 무효로 하고 새 일정으로 다시 알려요." },
  { icon: MessageSquareText, title: "근거 기반 챗봇", text: "공고 원문 문단을 인용해서만 답하고, 근거가 없으면 답을 보류해요." },
];

export default function Home() {
  const { profile, session } = useStore();
  return (
    <div className="space-y-10">
      <section className="rounded-2xl bg-navy px-6 py-10 text-white sm:px-10">
        <p className="text-sm text-accent">나 혼자만 레벨업 — 나만의 속도로 취·창업까지</p>
        <h1 className="mt-2 text-3xl font-bold leading-snug sm:text-4xl">
          흩어진 공지를 <br className="sm:hidden" />
          &ldquo;지금 할 수 있는 행동&rdquo;으로
        </h1>
        <p className="mt-3 max-w-2xl text-white/80">
          가톨릭대학교 {COLLEGES.length}개 대학·계열, {DEPARTMENTS.length}개 학과 누구나 목표 직무를 고르면 AI가 준비 경로를 만들고, 현장실습·창업지원
          공고를 내 스킬트리에 연결해 드려요.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link href={profile ? "/tree" : session ? "/onboarding" : "/signup"} className="btn bg-accent text-white hover:brightness-110">
            {profile ? "내 스킬트리로" : "1분 만에 시작하기"} <ArrowRight size={16} />
          </Link>
          <Link href="/sources" className="btn border border-white/30 text-white hover:bg-white/10">
            데이터 원칙 보기
          </Link>
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-2">
        {FEATURES.map((f) => (
          <div key={f.title} className="card p-5">
            <f.icon className="text-accent" size={22} />
            <h2 className="mt-2 font-bold">{f.title}</h2>
            <p className="mt-1 text-sm text-slate-600">{f.text}</p>
          </div>
        ))}
      </section>

      <section className="card p-5 text-sm text-slate-600">
        <h2 className="mb-2 font-bold text-slate-800">이런 학생을 위해 만들었어요</h2>
        <p>
          인공지능학과 3학년 민지는 AI 현장실습 공고를 마감 다음 날에야 발견했어요. 공고는 게시판에 분명히 있었지만 민지에게 닿지 않았죠.
          문제는 정보가 없는 게 아니라 전달 방식이에요. <span className="text-slate-400">(문제 상황을 보여주는 가상 사례)</span>
        </p>
      </section>
    </div>
  );
}
