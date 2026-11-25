// 증빙 파일(자격증 PDF·이미지) 저장소.
// 자격증에는 이름·생년월일 같은 개인정보가 들어 있으므로 서버에 올리지 않고 이 브라우저(IndexedDB)에만 둔다.
const DB = "cuk-career-ai-files";
const STORE = "proofs";
export const MAX_PROOF_BYTES = 10 * 1024 * 1024;
export const PROOF_TYPES = ["application/pdf", "image/png", "image/jpeg", "image/webp"];

export interface ProofMeta {
  name: string;
  type: string;
  size: number;
  url?: string;
}
interface Row extends ProofMeta {
  key: string;
  owner: string;
  skill: string;
  blob?: Blob;
}

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(STORE, { keyPath: "key" });
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}
async function run<T>(mode: IDBTransactionMode, fn: (s: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await open();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, mode);
    const req = fn(tx.objectStore(STORE));
    tx.oncomplete = () => { db.close(); resolve(req.result); };
    tx.onabort = () => { db.close(); reject(tx.error ?? req.error); };
  });
}
const keyOf = (owner: string, skill: string) => `${owner}::${skill}`;
// 증빙이 바뀌면 하양이(내 집 마련 인증)가 다시 세도록 알린다
export const PROOFS_CHANGED = "proofs-changed";
const changed = () => { window.dispatchEvent(new Event(PROOFS_CHANGED)); };

export async function putProof(owner: string, skill: string, file: File) {
  const row: Row = { key: keyOf(owner, skill), owner, skill, name: file.name, type: file.type, size: file.size, blob: file };
  await run("readwrite", (s) => s.put(row));
  changed();
}
export function resultUrl(value: string) {
  try {
    const url = new URL(value.trim());
    return ["https:", "http:"].includes(url.protocol) && !url.username && !url.password ? url.href : undefined;
  } catch { return undefined; }
}

export async function putProofLink(owner: string, skill: string, value: string) {
  const url = resultUrl(value);
  if (!url) throw new Error("올바른 작업물 주소를 입력하세요.");
  const row: Row = { key: keyOf(owner, skill), owner, skill, url, name: new URL(url).hostname, size: 0, type: "text/uri-list" };
  await run("readwrite", s => s.put(row));
  changed();
}
export const getProof = (owner: string, skill: string) => run<Row | undefined>("readonly", (s) => s.get(keyOf(owner, skill)));
export const deleteProof = (owner: string, skill: string) => run("readwrite", (s) => s.delete(keyOf(owner, skill))).then(changed);
export async function listProofs(owner: string): Promise<Record<string, ProofMeta>> {
  const rows = await run<Row[]>("readonly", (s) => s.getAll());
  return Object.fromEntries(rows.filter((r) => r.owner === owner).map((r) => [r.skill, { name: r.name, type: r.type, size: r.size, url: r.url && resultUrl(r.url) }]));
}

// 파일을 새 탭으로 열거나(인쇄 여부 선택) 인쇄 창을 띄운다
export async function openProof(owner: string, skill: string, print = false) {
  const row = await getProof(owner, skill);
  if (!row?.blob) return;
  const url = URL.createObjectURL(row.blob);
  if (!print) {
    window.open(url, "_blank", "noopener");
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
    return;
  }
  const frame = document.createElement("iframe");
  frame.style.cssText = "position:fixed;right:0;bottom:0;width:0;height:0;border:0";
  frame.onload = () => {
    frame.contentWindow?.focus();
    frame.contentWindow?.print();
    setTimeout(() => (frame.remove(), URL.revokeObjectURL(url)), 60_000);
  };
  frame.src = url;
  document.body.appendChild(frame);
}
