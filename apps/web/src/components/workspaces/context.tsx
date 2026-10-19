"use client";
import { createContext, useContext, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { useSession } from "@/lib/auth/session";
import { ownRole, wsPath } from "@/lib/api/client";
import { useResource } from "@/hooks/use-resource";
import type { Role, Workspace } from "@/types/api";
import { ErrorBox, Loading } from "@/components/ui";
const Context = createContext<{
  workspace: Workspace;
  role: Role | null;
  account: string;
  refresh: () => void;
} | null>(null);
export function WorkspaceScope({ children }: { children: React.ReactNode }) {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const { user } = useSession();
  const resource = useResource<Workspace>(wsPath(workspaceId), user?.id || "");
  const [access, setAccess] = useState<{ id: string; role: Role | null }>({
    id: "",
    role: null,
  });
  useEffect(() => {
    if (!resource.data || !user) return;
    const controller = new AbortController();
    ownRole(resource.data, user.id, controller.signal)
      .then((role) => {
        if (!controller.signal.aborted) setAccess({ id: workspaceId, role });
      })
      .catch(() => {
        if (!controller.signal.aborted)
          setAccess({ id: workspaceId, role: null });
      });
    return () => controller.abort();
  }, [workspaceId, resource.data, user]);
  if (resource.error)
    return <ErrorBox error={resource.error} retry={resource.refresh} />;
  if (!resource.data || !user) return <Loading />;
  return (
    <Context.Provider
      value={{
        workspace: resource.data,
        role: access.id === workspaceId ? access.role : null,
        account: user.id,
        refresh: resource.refresh,
      }}
    >
      {children}
    </Context.Provider>
  );
}
export function useWorkspace() {
  const value = useContext(Context);
  if (!value) throw new Error("Missing workspace");
  return value;
}
