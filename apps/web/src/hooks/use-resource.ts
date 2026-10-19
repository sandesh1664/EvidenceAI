"use client";
import { useCallback, useEffect, useState } from "react";
import { request } from "@/lib/api/client";
const cache = new Map<string, { time: number; value: unknown }>();
export function clearResources() {
  cache.clear();
}
export function useResource<T>(
  path: string | null,
  account: string,
  interval = 0,
) {
  const key = account + ":" + (path || "");
  const [revision, setRevision] = useState(0);
  const [state, setState] = useState<{
    key: string;
    data?: T;
    error?: unknown;
    loading: boolean;
  }>({ key: "", loading: true });
  const refresh = useCallback(() => setRevision((value) => value + 1), []);
  useEffect(() => {
    const changed = () => {
      cache.clear();
      refresh();
    };
    window.addEventListener("evidenceai:invalidate", changed);
    return () => window.removeEventListener("evidenceai:invalidate", changed);
  }, [refresh]);
  useEffect(() => {
    if (!path) return;
    const controller = new AbortController();
    let running = false;
    const load = async (force = false) => {
      if (running || (!force && document.visibilityState === "hidden")) return;
      running = true;
      const cached = cache.get(key);
      setState((previous) => ({
        key,
        data:
          (cached?.value as T | undefined) ||
          (previous.key === key ? previous.data : undefined),
        loading: !cached,
      }));
      try {
        const data = await request<T>(path, { signal: controller.signal });
        if (!controller.signal.aborted) {
          cache.set(key, { value: data, time: Date.now() });
          setState({ key, data, loading: false });
        }
      } catch (error) {
        if (!controller.signal.aborted)
          setState({ key, error, loading: false });
      } finally {
        running = false;
      }
    };
    const cached = cache.get(key);
    if (cached && revision === 0 && Date.now() - cached.time < 15000)
      void Promise.resolve(cached.value as T).then((data) => {
        if (!controller.signal.aborted) setState({ key, data, loading: false });
      });
    else void load(revision > 0);
    const visible = () => {
      if (document.visibilityState === "visible") void load();
    };
    document.addEventListener("visibilitychange", visible);
    const timer = interval
      ? setInterval(() => void load(), interval)
      : undefined;
    return () => {
      controller.abort();
      clearInterval(timer);
      document.removeEventListener("visibilitychange", visible);
    };
  }, [path, key, revision, interval]);
  return {
    ...(state.key === key
      ? state
      : { loading: true, data: undefined, error: undefined }),
    refresh,
  };
}
