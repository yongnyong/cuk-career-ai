"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useStore } from "@/lib/store";
import { useMounted } from "@/lib/useMounted";

export function RequireProfile({ children }: { children: React.ReactNode }) {
  const { profile, session, ready } = useStore();
  const router = useRouter();
  const mounted = useMounted();
  useEffect(() => {
    if (!ready) return;
    if (!session) router.replace("/login");
    else if (!profile) router.replace("/onboarding");
  }, [ready, session, profile, router]);
  if (!mounted || !profile) return null;
  return <>{children}</>;
}
