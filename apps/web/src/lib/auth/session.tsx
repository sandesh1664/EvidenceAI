"use client";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { api, ApiError, invalidate } from "@/lib/api/client";
import { clearResources } from "@/hooks/use-resource";
import type { User } from "@/types/api";
interface Session {
  user: User | null;
  loading: boolean;
  error: unknown;
  refresh: () => Promise<void>;
  signOut: () => Promise<void>;
}
const Context = createContext<Session | null>(null);
export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>();
  const sessionRequest = useRef<AbortController | null>(null);
  const refresh = useCallback(async () => {
    sessionRequest.current?.abort();
    const controller = new AbortController();
    sessionRequest.current = controller;
    clearResources();
    setLoading(true);
    try {
      const current = await api.me(controller.signal);
      if (!controller.signal.aborted) {
        setUser(current);
        setError(undefined);
      }
    } catch (error) {
      if (!controller.signal.aborted) {
        setUser(null);
        setError(
          error instanceof ApiError && error.status === 401 ? undefined : error,
        );
      }
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    sessionRequest.current = controller;
    api
      .me(controller.signal)
      .then((current) => {
        if (!controller.signal.aborted) setUser(current);
      })
      .catch((error) => {
        if (
          !controller.signal.aborted &&
          !(error instanceof ApiError && error.status === 401)
        )
          setError(error);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => {
      controller.abort();
      sessionRequest.current?.abort();
    };
  }, []);
  useEffect(() => {
    const expire = () => {
      sessionRequest.current?.abort();
      clearResources();
      setError(undefined);
      setUser(null);
      setLoading(false);
    };
    window.addEventListener("evidenceai:expired", expire);
    const channel = new BroadcastChannel("evidenceai-session");
    channel.onmessage = () => {
      expire();
      void refresh();
    };
    return () => {
      window.removeEventListener("evidenceai:expired", expire);
      channel.close();
    };
  }, [refresh]);
  const signOut = async () => {
    try {
      await api.logout();
    } catch (error) {
      if (!(error instanceof ApiError && error.status === 401)) throw error;
    }
    sessionRequest.current?.abort();
    clearResources();
    setUser(null);
    setLoading(false);
    setError(undefined);
    invalidate();
    const channel = new BroadcastChannel("evidenceai-session");
    channel.postMessage("changed");
    channel.close();
  };
  return (
    <Context.Provider value={{ user, loading, error, refresh, signOut }}>
      {children}
    </Context.Provider>
  );
}
export function useSession() {
  const value = useContext(Context);
  if (!value) throw new Error("Missing session provider");
  return value;
}
