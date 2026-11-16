"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bell, Clock } from "lucide-react";
import { DEMO_START, useStore } from "@/lib/store";
import { fmt } from "@/lib/engine";
import { useMounted } from "@/lib/useMounted";

const NAV = [
  { href: "/tree", label: "스킬트리" },
  { href: "/opportunities", label: "기회" },
  { href: "/notifications", label: "알림" },
  { href: "/profile", label: "내 정보" },
  { href: "/admin", label: "관리자" },
];

export function Header() {
  const store = useStore();
  const path = usePathname();
  // 저장된 상태는 하이드레이션 이후에만 반영(서버 HTML과 일치시키기 위함)
  const mounted = useMounted();
  const profile = mounted ? store.profile : null;
  const now = mounted ? store.now : DEMO_START;
  const unread = mounted ? store.notices.filter((n) => n.status === "sent").length : 0;
  return (
    <header className="sticky top-0 z-20 bg-navy text-white shadow">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
        <Link href="/" className="text-lg font-bold tracking-tight">
          CUK Career <span className="text-accent">AI</span>
        </Link>
        {profile && (
          <nav className="flex flex-wrap gap-1 text-sm">
            {NAV.map((n) => (
              <Link
                key={n.href}
                href={n.href}
                className={`relative rounded-md px-2.5 py-1 ${path.startsWith(n.href) ? "bg-white/15" : "hover:bg-white/10"}`}
              >
                {n.label}
                {n.href === "/notifications" && unread > 0 && (
                  <span className="absolute -right-1 -top-1 rounded-full bg-accent px-1.5 text-[10px] font-bold">{unread}</span>
                )}
              </Link>
            ))}
          </nav>
        )}
        <div className="ml-auto flex items-center gap-3 text-xs text-white/80">
          <Link href="/notifications" className="flex items-center gap-1" title="시연용 가상 시계 — 알림 화면에서 변경">
            <Clock size={14} /> {fmt(now)}
          </Link>
          {profile && (
            <Link href="/notifications" aria-label="알림" className="sm:hidden">
              <Bell size={16} />
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
