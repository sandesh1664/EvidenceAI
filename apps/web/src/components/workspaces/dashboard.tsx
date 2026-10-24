"use client";
import { ProviderStatus } from "@/components/chat/provider-status";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useResource } from "@/hooks/use-resource";
import { api, wsPath } from "@/lib/api/client";
import type { ConversationPage, Document } from "@/types/api";
import {
  Badge,
  Confirm,
  Empty,
  ErrorBox,
  Loading,
  PageHeading,
  date,
} from "@/components/ui";
import { useWorkspace } from "./context";
export function Dashboard() {
  const { workspace, role, account } = useWorkspace();
  const router = useRouter();
  const root = "/workspaces/" + workspace.id;
  const documents = useResource<Document[]>(
    wsPath(workspace.id) + "/documents/?limit=100",
    account,
    15000,
  );
  const conversations = useResource<ConversationPage>(
    wsPath(workspace.id) + "/conversations?limit=4",
    account,
  );
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState(workspace.name);
  async function rename(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(undefined);
    try {
      await api.renameWorkspace(workspace.id, name.trim());
    } catch (error) {
      setError(error);
    } finally {
      setBusy(false);
    }
  }
  const complete =
    documents.data?.filter((d) => d.processing_status === "completed").length ||
    0;
  const pending =
    documents.data?.filter(
      (d) =>
        d.processing_status === "pending" ||
        d.processing_status === "processing",
    ).length || 0;
  const failed =
    documents.data?.filter((d) => d.processing_status === "failed").length || 0;
  return (
    <>
      <PageHeading
        eyebrow="WORKSPACE OVERVIEW"
        title={workspace.name}
        description={
          workspace.description ||
          "Your next insight is waiting in the evidence."
        }
        action={<Badge tone="green">{role || "Checking access"}</Badge>}
      />
      <ProviderStatus />
      <section className="research-hero">
        <div>
          <div className="eyebrow">A CLEARER PATH THROUGH YOUR EVIDENCE</div>
          <h2>
            Good questions.
            <br />
            Grounded answers.
          </h2>
          <p>
            Bring your documents together. Follow an idea.
            <br />
            Find the source behind every answer.
          </p>
          <Link className="button ink" href={root + "/research"}>
            Start researching <span aria-hidden="true">↗</span>
          </Link>
        </div>
        <div className="hero-graphic" aria-hidden="true">
          <div className="orbit orbit-one" />
          <div className="orbit orbit-two" />
          <div className="evidence-sheet">
            <span>YOUR EVIDENCE</span>
            <i />
            <i />
            <i />
            <b>↗</b>
            <small>From question to source.</small>
          </div>
          <span className="graphic-chip">[ source connected ]</span>
        </div>
      </section>
      {documents.error ? (
        <ErrorBox error={documents.error} retry={documents.refresh} />
      ) : documents.loading && !documents.data ? (
        <Loading />
      ) : (
        <>
          <div className="stats-grid">
            <div className="stat">
              <span>Documents loaded</span>
              <strong>{documents.data?.length || 0}</strong>
              <small>First 100 documents</small>
            </div>
            <div className="stat">
              <span>Extraction complete</span>
              <strong>{complete}</strong>
              <small>Indexing is tracked separately</small>
            </div>
            <div className="stat">
              <span>Awaiting extraction</span>
              <strong>{pending}</strong>
              <small>Pending or processing</small>
            </div>
            <div className="stat">
              <span>Need attention</span>
              <strong>{failed}</strong>
              <small>Failed extraction</small>
            </div>
          </div>
          <div className="dashboard-columns">
            <section className="panel">
              <div className="section-heading">
                <h2>Document library</h2>
                <Link href={root + "/documents"}>View library ↗</Link>
              </div>
              {!documents.data?.length ? (
                <Empty title="Add your first source">
                  Upload a PDF, TXT or Markdown document to begin.
                </Empty>
              ) : (
                documents.data.slice(0, 4).map((document) => (
                  <div className="document-preview" key={document.id}>
                    <span className="file-icon" aria-hidden="true">
                      ▤
                    </span>
                    <div>
                      <strong>{document.original_filename}</strong>
                      <small>{date(document.created_at)}</small>
                    </div>
                    <Badge
                      tone={
                        document.processing_status === "completed"
                          ? "green"
                          : ""
                      }
                    >
                      {document.processing_status === "completed"
                        ? "Extracted"
                        : document.processing_status}
                    </Badge>
                  </div>
                ))
              )}
              <Link className="button full" href={root + "/documents"}>
                + Upload documents
              </Link>
            </section>
            <section className="panel">
              <div className="section-heading">
                <h2>Latest saved conversations</h2>
                <Link href={root + "/conversations"}>View history ↗</Link>
              </div>
              {conversations.error ? (
                <ErrorBox
                  error={conversations.error}
                  retry={conversations.refresh}
                />
              ) : conversations.loading ? (
                <Loading />
              ) : !conversations.data?.items.length ? (
                <Empty title="Follow a line of inquiry">
                  Save a conversation to revisit questions and cited evidence.
                </Empty>
              ) : (
                conversations.data.items.map((conversation) => (
                  <Link
                    className="conversation-preview"
                    key={conversation.id}
                    href={root + "/conversations/" + conversation.id}
                  >
                    <span aria-hidden="true">☷</span>
                    <div>
                      <strong>{conversation.title}</strong>
                      <small>
                        Last activity {date(conversation.last_activity_at)}
                      </small>
                    </div>
                    <span aria-hidden="true">↗</span>
                  </Link>
                ))
              )}
            </section>
          </div>
        </>
      )}
      {(role === "owner" || role === "admin") && (
        <section className="panel management">
          <h2>Workspace settings</h2>
          <form className="inline-form" onSubmit={rename}>
            <label>
              Workspace name
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                required
                maxLength={200}
                pattern=".*\S.*"
              />
            </label>
            <button className="button" disabled={busy}>
              Save name
            </button>
          </form>
          {!!error && <ErrorBox error={error} />}
          <Link href={root + "/members"}>Manage members and ownership ↗</Link>
          {role === "owner" && (
            <div className="danger-zone">
              <div>
                <strong>Delete workspace</strong>
                <p>
                  Only eligible empty workspaces can be deleted. Remove other
                  members, documents and conversations first.
                </p>
              </div>
              <Confirm
                title="Delete workspace"
                description={`Permanently delete ${workspace.name}? The server will reject deletion while dependent research or members remain.`}
                onConfirm={async () => {
                  await api.deleteWorkspace(workspace.id);
                  router.replace("/workspaces");
                }}
              />
            </div>
          )}
        </section>
      )}
    </>
  );
}
