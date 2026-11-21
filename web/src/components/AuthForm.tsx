"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { LogIn, UserPlus, UserRound } from "lucide-react";
import { useStore } from "@/lib/store";
import { PERSONAS } from "@/lib/data/personas";
import { Warn } from "./ui";
import type { CareerInterest } from "@/lib/types";

export function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const s = useStore();
  const router = useRouter();
  const [id, setId] = useState("");
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [interest, setInterest] = useState<CareerInterest | "">("");
  const signup = mode === "signup";

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (signup && pw !== pw2) return setErr("비밀번호가 서로 달라요.");
    if (signup && !interest) return setErr("관심 분야를 선택해 주세요.");
    setBusy(true);
    const loginId = id.trim().toLowerCase();
    const error = signup ? await s.signup(loginId, pw, interest as CareerInterest) : await s.login(loginId, pw);
    setBusy(false);
    if (error) return setErr(error);
    // 가입 직후에는 기본 정보 입력으로, 로그인은 스킬트리로(프로필이 없으면 가드가 온보딩으로 보낸다)
    router.push(signup ? "/onboarding" : "/tree");
  };

  return (
    <div className="mx-auto max-w-md space-y-4">
      <form onSubmit={submit} className="card space-y-4 p-6">
        <h1 className="text-xl font-bold">{signup ? "회원가입" : "로그인"}</h1>
        {signup && (
          <p className="text-sm text-slate-500">
            관심 분야를 선택하면 나에게 맞는 스킬트리와 공고를 연결해요. 가입 후 학과·학년과 준비한 결과물을 설정해요.
          </p>
        )}
        <label className="block text-sm">
          아이디
          <input
            className="input mt-1"
            value={id}
            onChange={(e) => setId(e.target.value)}
            autoComplete="username"
            placeholder="영문 소문자·숫자 4~16자"
            required
          />
        </label>
        <label className="block text-sm">
          비밀번호
          <input
            type="password"
            className="input mt-1"
            value={pw}
            onChange={(e) => setPw(e.target.value)}
            autoComplete={signup ? "new-password" : "current-password"}
            placeholder={signup ? "6자 이상" : ""}
            required
          />
        </label>
        {signup && (
          <label className="block text-sm">
            비밀번호 확인
            <input type="password" className="input mt-1" value={pw2} onChange={(e) => setPw2(e.target.value)} autoComplete="new-password" required />
          </label>
        )}
        {signup && (
          <fieldset>
            <legend className="mb-2 text-sm font-semibold">관심 분야</legend>
            <div className="grid grid-cols-2 gap-2">
              {([['employment', '취업'], ['startup', '창업']] as const).map(([value, label]) => (
                <label key={value} className={`cursor-pointer rounded-lg border p-3 ${interest === value ? 'border-edge bg-navy/5' : 'border-line'}`}>
                  <input type="radio" name="careerInterest" value={value} checked={interest === value} onChange={() => setInterest(value)} required className="mr-2" />
                  {label}
                </label>
              ))}
            </div>
          </fieldset>
        )}
        {err && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-danger">{err}</p>}
        <button className="btn-primary w-full" disabled={busy}>
          {signup ? <UserPlus size={16} /> : <LogIn size={16} />} {signup ? "가입하고 기본 정보 입력하기" : "로그인"}
        </button>
        <p className="text-center text-sm text-slate-500">
          {signup ? "이미 계정이 있나요? " : "처음이신가요? "}
          <Link href={signup ? "/login" : "/signup"} className="font-medium text-ink underline">
            {signup ? "로그인" : "회원가입"}
          </Link>
        </p>
        {s.mode === "local" && (
          <Warn>
            지금은 서버에 연결되지 않아 계정이 이 브라우저에만 저장돼요. 다른 기기에서는 로그인되지 않으니, 다른 사이트에서 쓰는 비밀번호는 쓰지
            마세요.
          </Warn>
        )}
      </form>

      <div className="card p-4 text-sm">
        <p className="flex items-center gap-1.5 text-slate-600">
          <UserRound size={16} /> 시연용 계정으로 바로 시작
        </p>
        <div className="mt-2 flex flex-wrap gap-2">
          {PERSONAS.map((x) => (
            <button
              key={x.id}
              type="button"
              className="btn-ghost !py-1"
              title={x.desc}
              onClick={() => {
                s.loginDemo(x.id, x.profile);
                router.push("/tree");
              }}
            >
              {x.label} <span className="text-xs text-slate-400">{x.desc}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
