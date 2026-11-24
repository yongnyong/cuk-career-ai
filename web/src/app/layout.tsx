import type { Metadata } from "next";
import { Suspense } from "react";
import { Black_Han_Sans } from "next/font/google";
import "./globals.css";
import { StoreProvider } from "@/lib/store";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { AssistantDock, AssistantProvider } from "@/components/Assistant";
import { HayangRail } from "@/components/Hayang";

const display = Black_Han_Sans({ variable: "--font-display-kr", subsets: ["latin"], weight: "400" });

export const metadata: Metadata = {
  title: "CUK Career AI",
  description: "현장실습과 창업 기회를 연결하는 AI 진로 스킬트리 — 2026 가톨릭대학교 생성형 AI 경진대회 출품작",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="ko" className={`${display.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col font-sans">
        <StoreProvider>
          <AssistantProvider>
            <Suspense fallback={<div className="h-14 border-b-2 border-edge bg-panel" />}>
              <Header />
            </Suspense>
            {/* 넓은 화면(2xl)은 왼쪽 하양이, 가운데 본문, 오른쪽 챗봇 세 칸으로 양옆 여백까지 쓴다 */}
            <div className="mx-auto w-full max-w-6xl flex-1 px-4 pb-24 pt-6 sm:pb-8 2xl:grid 2xl:max-w-[1880px] 2xl:grid-cols-[240px_minmax(0,1fr)_380px] 2xl:gap-6">
              <aside className="hidden 2xl:block">
                <Suspense fallback={null}><HayangRail /></Suspense>
              </aside>
              <main className="min-w-0">{children}</main>
              <aside className="hidden 2xl:block">
                <Suspense fallback={null}><AssistantDock variant="rail" /></Suspense>
              </aside>
            </div>
            <Footer />
            <div className="2xl:hidden">
              <Suspense fallback={null}>
                <AssistantDock />
              </Suspense>
            </div>
          </AssistantProvider>
        </StoreProvider>
      </body>
    </html>
  );
}
