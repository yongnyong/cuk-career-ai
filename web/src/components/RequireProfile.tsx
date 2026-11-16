"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useStore } from "@/lib/store";
import { useMounted } from "@/lib/useMounted";

export function RequireProfile({ children }: { children: React.ReactNode }) {
  const { profile, ready } = useStore();
  const router = useRouter();
  const mounted = useMounted();
  useEffect(() => {
    if (ready && !profile) router.replace("/onboarding");
  }, [ready, profile, router]);
  if (!mounted || !profile) return null;
  return <>{children}</>;
}
