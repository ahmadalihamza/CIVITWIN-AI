"use client";

import { useEffect, useState } from "react";
import { api, errorMessage } from "@/lib/api";

export function useData<T>(path: string) {
  const [result, setResult] = useState<{ key: string; data?: T; error?: string }>();
  const [revision, setRevision] = useState(0);
  const key = path + "#" + revision;
  useEffect(() => {
    const controller = new AbortController();
    api<T>(path, { signal: controller.signal }).then((data) => {
      if (!controller.signal.aborted) setResult({ key, data });
    }).catch((failure) => {
      if (!controller.signal.aborted) setResult({ key, error: errorMessage(failure) });
    });
    return () => controller.abort();
  }, [path, key]);
  return {
    data: result?.key === key ? result.data : undefined,
    error: result?.key === key ? result.error ?? "" : "",
    retry: () => setRevision((value) => value + 1),
  };
}

export function Loading({ error, retry }: { error: string; retry: () => void }) {
  return error ? <div className="notice" role="alert"><p>{error}</p>
    <button type="button" className="button" onClick={retry}>Try again</button></div> :
    <div className="loading panel" role="status">Loading planning data…</div>;
}
