"use client";
import { useRef, useState } from "react";
import { Paperclip, Printer, Trash2 } from "lucide-react";
import { MAX_PROOF_BYTES, PROOF_TYPES, deleteProof, openProof, putProof, type ProofMeta } from "@/lib/files";

// 완료한 노드에 자격증·수료증 파일을 붙인다. 파일은 이 브라우저에만 저장된다.
export function ProofField({ owner, skill, proof, onChange }: { owner: string; skill: string; proof?: ProofMeta; onChange: () => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [error, setError] = useState("");

  const pick = async (file?: File) => {
    if (!file) return;
    if (!PROOF_TYPES.includes(file.type)) return setError("PDF 또는 이미지(PNG, JPG) 파일만 붙일 수 있어요.");
    if (file.size > MAX_PROOF_BYTES) return setError("10MB 이하 파일만 붙일 수 있어요.");
    setError("");
    try {
      await putProof(owner, skill, file);
      onChange();
    } catch {
      setError("이 브라우저에서는 파일을 저장하지 못했어요.");
    }
  };

  return (
    <div className="mt-3 space-y-1 text-xs">
      <p className="font-bold text-slate-600">증빙 파일</p>
      {proof ? (
        <>
          <p className="flex items-center gap-1 break-all">
            <Paperclip size={12} className="shrink-0" /> {proof.name}
          </p>
          <div className="flex flex-wrap gap-1.5">
            <button className="btn-ghost !px-2 !py-1 text-xs" onClick={() => openProof(owner, skill)}>
              열기
            </button>
            <button className="btn-ghost !px-2 !py-1 text-xs" onClick={() => openProof(owner, skill, true)}>
              <Printer size={12} /> 인쇄
            </button>
            <button className="btn-ghost !px-2 !py-1 text-xs text-danger" onClick={() => deleteProof(owner, skill).then(onChange)}>
              <Trash2 size={12} /> 삭제
            </button>
          </div>
        </>
      ) : (
        <button className="btn-ghost w-full !py-1.5 text-xs" onClick={() => input.current?.click()}>
          <Paperclip size={12} /> 자격증·수료증 붙이기 (PDF·이미지)
        </button>
      )}
      <input
        ref={input}
        type="file"
        accept=".pdf,image/png,image/jpeg,image/webp"
        className="hidden"
        onChange={(e) => (pick(e.target.files?.[0]), (e.target.value = ""))}
      />
      {error && <p className="text-danger">{error}</p>}
      <p className="text-[11px] text-slate-400">파일은 이 기기의 브라우저에만 저장되고 서버로 보내지 않아요.</p>
    </div>
  );
}
