import { WorkspaceScope } from "@/components/workspaces/context";
export default function Layout({ children }: { children: React.ReactNode }) {
  return <WorkspaceScope>{children}</WorkspaceScope>;
}
