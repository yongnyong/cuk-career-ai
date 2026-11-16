import { useSyncExternalStore } from "react";

const subscribe = () => () => {};
// 서버·하이드레이션 중에는 false, 그 이후 true. 브라우저 저장 상태를 서버 HTML과 어긋나지 않게 반영할 때 쓴다.
export const useMounted = () => useSyncExternalStore(subscribe, () => true, () => false);
