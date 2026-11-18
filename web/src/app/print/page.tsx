"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Printer } from "lucide-react";
import { RequireProfile } from "@/components/RequireProfile";
import { useStore } from "@/lib/store";
import { fmt } from "@/lib/engine";
import { formatScore, jobById } from "@/lib/data/catalog";
import { getDepartment } from "@/lib/data/departments";
import { getProof, listProofs, openProof, type ProofMeta } from "@/lib/files";

// 완료 내역과 증빙을 종이에 맞게 보여주는 화면. 화면에서도 종이처럼 흰 바탕으로 그린다.
function Sheet() {
  const s = useStore();
  const p = s.profile!;
  const owner = s.session!;
  const { tree } = s.careerPath!;
  const [proofs, setProofs] = useState<Record<string, ProofMeta>>({});
  const [images, setImages] = useState<{ skill: string; name: string; url: string }[]>([]);

  useEffect(() => {
    let urls: string[] = [];
    (async () => {
      const metas = await listProofs(owner).catch(() => ({}) as Record<string, ProofMeta>);
      setProofs(metas);
      const imgs = [];
      for (const [skill, m] of Object.entries(metas)) {
        if (!m.type.startsWith("image/")) continue;
        const row = await getProof(owner, skill);
        if (row) imgs.push({ skill, name: m.name, url: URL.createObjectURL(row.blob) });
      }
      urls = imgs.map((x) => x.url);
      setImages(imgs);
    })();
    return () => urls.forEach((u) => URL.revokeObjectURL(u));
  }, [owner]);

  const done = tree.filter((n) => n.state !== "none");
  const pdfs = Object.entries(proofs).filter(([, m]) => m.type === "application/pdf");
  const nameOf = (skill: string) => tree.find((n) => n.skill === skill)?.name ?? skill;

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="flex flex-wrap items-center gap-2 print:hidden">
        <button className="btn-gold" onClick={() => window.print()}>
          <Printer size={16} /> 이 화면 인쇄
        </button>
        <Link href="/tree" className="btn-ghost">
          스킬트리로 돌아가기
        </Link>
        <span className="text-xs text-slate-500">PDF 증빙은 아래 목록에서 하나씩 인쇄해요.</span>
      </div>

      <article className="space-y-5 rounded-lg bg-white p-8 text-black print:p-0">
        <div className="border-b-2 border-black pb-3">
          <h1 className="text-2xl font-bold">진로 준비 내역</h1>
          <p className="mt-1 text-sm">
            {getDepartment(p.departmentId)?.name} {p.grade}학년 · 목표: {jobById(p.jobId)?.name} · 아이디 {p.pseudoId}
          </p>
          <p className="text-xs text-neutral-600">출력 기준일 {fmt(s.now, false)} · CUK Career AI</p>
        </div>

        <section>
          <h2 className="mb-2 font-bold">
            완료한 항목 {done.length} / {tree.length}
          </h2>
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-black text-left">
                <th className="py-1.5">항목</th>
                <th>종류</th>
                <th>상태</th>
                <th>점수·등급</th>
                <th>증빙</th>
              </tr>
            </thead>
            <tbody>
              {tree.map((n) => (
                <tr key={n.skill} className="border-b border-neutral-300">
                  <td className="py-1.5">
                    {n.name}
                    {n.required ? " (필수)" : ""}
                  </td>
                  <td>{n.kind}</td>
                  <td>{n.state === "none" ? "미완료" : "완료"}</td>
                  <td>{formatScore(n.skill, n.score) || "-"}</td>
                  <td>{proofs[n.skill] ? "첨부" : "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-xs text-neutral-600">완료 표시와 점수·등급은 본인이 입력한 내용이며, 기관이 확인한 것이 아닙니다.</p>
        </section>

        {images.map((img) => (
          <section key={img.skill} className="break-before-page">
            <h2 className="mb-2 font-bold">증빙: {nameOf(img.skill)}</h2>
            {/* 사용자가 붙인 로컬 파일(blob)이라 next/image를 쓰지 않는다 */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={img.url} alt={`${nameOf(img.skill)} 증빙 (${img.name})`} className="max-h-[900px] w-full object-contain" />
          </section>
        ))}
      </article>

      {pdfs.length > 0 && (
        <section className="card p-4 print:hidden">
          <h2 className="mb-2 font-bold">PDF 증빙 인쇄</h2>
          <ul className="space-y-1.5 text-sm">
            {pdfs.map(([skill, m]) => (
              <li key={skill} className="flex flex-wrap items-center gap-2">
                <span className="min-w-0 flex-1 break-all">
                  {nameOf(skill)} — {m.name}
                </span>
                <button className="btn-ghost !py-1 text-xs" onClick={() => openProof(owner, skill, true)}>
                  <Printer size={12} /> 인쇄
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

export default function PrintPage() {
  return (
    <RequireProfile>
      <Sheet />
    </RequireProfile>
  );
}
