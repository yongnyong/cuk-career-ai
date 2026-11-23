import type { Metadata } from "next";
import { Suspense } from "react";
import { Black_Han_Sans } from "next/font/google";
import "./globals.css";
import { StoreProvider } from "@/lib/store";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { AssistantDock, AssistantProvider } from "@/components/Assistant";

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
            <main className="mx-auto w-full max-w-6xl flex-1 px-4 pb-24 pt-6 sm:pb-8">{children}</main>
            <Footer />
            <Suspense fallback={null}>
              <AssistantDock />
            </Suspense>
          </AssistantProvider>
        </StoreProvider>
      </body>
    </html>
  );
}
