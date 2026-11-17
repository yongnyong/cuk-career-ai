"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useStore } from "@/lib/store";
import { useMounted } from "@/lib/useMounted";

export function RequireProfile({ children }: { children: React.ReactNode }) {
  const { profile, session, ready, isAdmin } = useStore();
  const router = useRouter();
  const mounted = useMounted();
  useEffect(() => {
    if (!ready) return;
    if (!session) router.replace("/login");
    else if (!profile) router.replace(isAdmin ? "/admin" : "/onboarding");
  }, [ready, session, profile, isAdmin, router]);
  if (!mounted || !ready || !profile) return null; // ready 이후에 그려야 관리자 수정본이 반영된다
  return <>{children}</>;
}
