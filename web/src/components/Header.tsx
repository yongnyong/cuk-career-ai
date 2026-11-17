"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Bell, Clock, GitBranch, Home, LogOut, ScrollText, UserRound } from "lucide-react";
import { DEMO_START, useStore } from "@/lib/store";
import { fmt } from "@/lib/engine";
import { useMounted } from "@/lib/useMounted";

const NAV = [
  { href: "/", label: "홈", icon: Home },
  { href: "/tree", label: "스킬트리", icon: GitBranch },
  { href: "/opportunities", label: "기회", icon: ScrollText },
  { href: "/notifications", label: "알림", icon: Bell },
];

export function Header() {
  const store = useStore();
  const path = usePathname();
  const router = useRouter();
  // 저장된 상태는 하이드레이션 이후에만 반영(서버 HTML과 일치시키기 위함)
  const mounted = useMounted();
  const profile = mounted ? store.profile : null;
  const session = mounted ? store.session : null;
  const now = mounted ? store.now : DEMO_START;
  const unread = mounted ? store.notices.filter((n) => n.status === "sent").length : 0;
  const active = (href: string) => (href === "/" ? path === "/" : path.startsWith(href));
  const badge = (href: string) =>
    href === "/notifications" && unread > 0 ? (
      <span className="rounded-sm bg-gold px-1 text-[10px] font-bold text-on-gold">{unread}</span>
    ) : null;

  return (
    <>
      <header className="sticky top-0 z-20 border-b-2 border-edge bg-panel">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-6 px-4">
          <Link href="/" className="font-display text-xl leading-none">
            CUK Career AI
          </Link>
          {profile && (
            <nav className="hidden h-full gap-1 text-sm font-semibold sm:flex">
              {NAV.map((n) => (
                <Link
                  key={n.href}
                  href={n.href}
                  aria-current={active(n.href) ? "page" : undefined}
                  className={`flex items-center gap-1.5 border-b-4 px-3 pt-1 ${
                    active(n.href) ? "border-gold" : "border-transparent text-ink/60 hover:text-ink"
                  }`}
                >
                  {n.label}
                  {badge(n.href)}
                </Link>
              ))}
            </nav>
          )}
          <div className="ml-auto flex items-center gap-3 text-xs">
            <Link
              href="/notifications"
              className="hidden items-center gap-1 text-ink/60 md:flex"
              title="시연용 가상 시계 — 알림 화면에서 변경"
            >
              <Clock size={14} /> {fmt(now)}
            </Link>
            {session ? (
              <>
                {mounted && store.isAdmin && (
                  <Link href="/admin" className="chip bg-gold text-on-gold">
                    관리자
                  </Link>
                )}
                <Link href={profile ? "/profile" : "/onboarding"} className="flex items-center gap-1 font-semibold">
                  <UserRound size={14} /> {session}
                </Link>
                <button
                  className="btn-ghost !px-2 !py-1 text-xs"
                  onClick={() => {
                    store.logout();
                    router.push("/");
                  }}
                >
                  <LogOut size={12} /> 로그아웃
                </button>
              </>
            ) : (
              <>
                <Link href="/login" className="btn-ghost !px-2.5 !py-1 text-xs">
                  로그인
                </Link>
                <Link href="/signup" className="btn-primary !px-2.5 !py-1 text-xs">
                  회원가입
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      {profile && (
        <nav className="fixed inset-x-0 bottom-0 z-20 grid grid-cols-4 border-t-2 border-edge bg-panel sm:hidden">
          {NAV.map((n) => (
            <Link
              key={n.href}
              href={n.href}
              aria-current={active(n.href) ? "page" : undefined}
              className={`flex flex-col items-center gap-0.5 border-t-4 py-2 text-[11px] font-semibold ${
                active(n.href) ? "border-gold" : "border-transparent text-ink/55"
              }`}
            >
              <span className="relative">
                <n.icon size={20} />
                <span className="absolute -right-3 -top-1">{badge(n.href)}</span>
              </span>
              {n.label}
            </Link>
          ))}
        </nav>
      )}
    </>
  );
}
