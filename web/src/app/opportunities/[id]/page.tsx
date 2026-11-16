import { Suspense } from "react";
import { Detail } from "./Detail";

export default function Page() {
  return (
    <Suspense fallback={<div className="p-10 text-center text-sm text-slate-500">불러오는 중…</div>}>
      <Detail />
    </Suspense>
  );
}
