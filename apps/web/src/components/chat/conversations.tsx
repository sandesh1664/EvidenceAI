"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { api, wsPath } from "@/lib/api/client";
import { useResource } from "@/hooks/use-resource";
import { useWorkspace } from "@/components/workspaces/context";
import { DocumentFilter } from "@/components/documents/filter";
import { AnswerView } from "@/components/citations/answer";
import type {
  Conversation,
  ConversationPage,
  Message,
  MessagePage,
  Question,
  Turn,
} from "@/types/api";
import {
  Badge,
  Confirm,
  Empty,
  ErrorBox,
  Loading,
  PageHeading,
  date,
  validQuestion,
} from "@/components/ui";
export function Conversations() {
  const { workspace, account } = useWorkspace();
  const router = useRouter();
  const [cursors, setCursors] = useState<(string | null)[]>([null]);
  const [archived, setArchived] = useState(false);
  const cursor = cursors.at(-1);
  const resource = useResource<ConversationPage>(
    wsPath(workspace.id) +
      `/conversations?limit=12&include_archived=${archived}${cursor ? "&cursor=" + cursor : ""}`,
    account,
  );
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  const root = "/workspaces/" + workspace.id + "/conversations";
  async function create(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const data = new FormData(event.currentTarget);
    setBusy(true);
    setError(undefined);
    try {
      const conversation = await api.createConversation(
        workspace.id,
        String(data.get("title")).trim(),
      );
      router.push(root + "/" + conversation.id);
    } catch (error) {
      setError(error);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeading
        eyebrow={workspace.name}
        title="Your research history"
        description="Questions, answers and the sources behind them. Private to your account within this workspace."
      />
      <section className="panel">
        <form className="inline-form" onSubmit={create}>
          <label>
            Conversation title
            <input
              name="title"
              required
              maxLength={200}
              placeholder="A new line of inquiry"
              pattern=".*\S.*"
            />
          </label>
          <button className="button primary" disabled={busy}>
            {busy ? "Creating…" : "+ New conversation"}
          </button>
        </form>
        {!!error && <ErrorBox error={error} />}
      </section>
      <div className="section-heading">
        <h2>Saved conversations</h2>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={archived}
            onChange={(event) => {
              setArchived(event.target.checked);
              setCursors([null]);
            }}
          />
          Include archived
        </label>
      </div>
      {resource.loading ? (
        <Loading />
      ) : resource.error ? (
        <ErrorBox error={resource.error} retry={resource.refresh} />
      ) : !resource.data?.items.length ? (
        <Empty title="A research trail starts with one question">
          Create a conversation to save your inquiry and revisit its supporting
          sources.
        </Empty>
      ) : (
        <section className="panel">
          {resource.data.items.map((conversation) => (
            <Link
              className="conversation-preview"
              key={conversation.id}
              href={root + "/" + conversation.id}
            >
              <span className="conversation-symbol" aria-hidden="true">
                ☷
              </span>
              <div>
                <strong>{conversation.title}</strong>
                <small>
                  Created {date(conversation.created_at)} · Last activity{" "}
                  {date(conversation.last_activity_at)}
                </small>
              </div>
              {conversation.archived_at && <Badge>Archived</Badge>}
              <span aria-hidden="true">↗</span>
            </Link>
          ))}
        </section>
      )}
      <nav className="pager" aria-label="Conversation pagination">
        <button
          className="button small"
          disabled={cursors.length === 1}
          onClick={() => setCursors(cursors.slice(0, -1))}
        >
          Previous
        </button>
        <span>Page {cursors.length} · newest created first</span>
        <button
          className="button small"
          disabled={!resource.data?.next_cursor}
          onClick={() => setCursors([...cursors, resource.data!.next_cursor])}
        >
          Next
        </button>
      </nav>
    </>
  );
}
export type Submission = Question & { idempotency_key: string };
export function submission(
  question: string,
  filters: string[] | null,
  limit: number,
): Submission {
  return {
    question: question.trim(),
    document_ids: filters,
    retrieval_limit: limit,
    idempotency_key: crypto.randomUUID(),
  };
}
export function ConversationThread() {
  const { workspace, account } = useWorkspace();
  const { conversationId } = useParams<{ conversationId: string }>();
  const router = useRouter();
  const base =
    wsPath(workspace.id) +
    "/conversations/" +
    encodeURIComponent(conversationId);
  const conversation = useResource<Conversation>(base, account);
  const [pages, setPages] = useState([0]);
  const after = pages.at(-1) || 0;
  const history = useResource<MessagePage>(
    base + `/messages?limit=50&after_sequence=${after}`,
    account,
    5000,
  );
  const [latest, setLatest] = useState<Turn | null>(null);
  const latestHistory = useResource<MessagePage>(
    latest
      ? base +
          `/messages?limit=2&after_sequence=${latest.user_message.sequence - 1}`
      : null,
    account,
    5000,
  );
  const [question, setQuestion] = useState("");
  const [filters, setFilters] = useState<string[] | null>(null);
  const [limit, setLimit] = useState(6);
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const pendingSubmission = useRef<Submission | null>(null);
  const lock = useRef(false);
  const latestMessages =
    latestHistory.data?.items ||
    (latest ? [latest.user_message, latest.assistant_message] : []);
  const mapped = new Map<string, Message>();
  for (const message of [...(history.data?.items || []), ...latestMessages])
    mapped.set(message.id, message);
  const messages = [...mapped.values()].sort((a, b) => a.sequence - b.sequence);
  const pending = messages.some(
    (message) => message.generation_status === "pending",
  );
  async function send(event?: React.FormEvent) {
    event?.preventDefault();
    if (lock.current || pending) return;
    if (!pendingSubmission.current && !validQuestion(question)) return;
    lock.current = true;
    setBusy(true);
    setError(undefined);
    pendingSubmission.current ??= submission(question, filters, limit);
    try {
      const turn = await api.send(
        workspace.id,
        conversationId,
        pendingSubmission.current,
      );
      setLatest(turn);
      pendingSubmission.current = null;
      setUncertain(false);
      setQuestion("");
      history.refresh();
      latestHistory.refresh();
    } catch (error) {
      setError(error);
      setUncertain(true);
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  async function rename(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(undefined);
    try {
      await api.updateConversation(workspace.id, conversationId, {
        title: String(new FormData(event.currentTarget).get("title")).trim(),
      });
    } catch (error) {
      setError(error);
    }
  }
  if (conversation.error)
    return <ErrorBox error={conversation.error} retry={conversation.refresh} />;
  if (!conversation.data) return <Loading />;
  const current = conversation.data;
  return (
    <>
      <PageHeading
        eyebrow="SAVED RESEARCH"
        title={current.title}
        description="Follow up with fresh evidence. Historical citations are saved snapshots, not renewed source validation."
        action={current.archived_at ? <Badge>Archived</Badge> : undefined}
      />
      <details className="panel conversation-settings">
        <summary>Conversation settings</summary>
        <form
          className="inline-form"
          onSubmit={rename}
          key={current.updated_at}
        >
          <label>
            Conversation title
            <input
              name="title"
              defaultValue={current.title}
              required
              maxLength={200}
              pattern=".*\S.*"
            />
          </label>
          <button className="button">Rename</button>
        </form>
        <div className="actions">
          <button
            className="button small"
            onClick={() =>
              void api
                .updateConversation(workspace.id, conversationId, {
                  archived: !current.archived_at,
                })
                .catch(setError)
            }
          >
            {current.archived_at
              ? "Restore conversation"
              : "Archive conversation"}
          </button>
          <Confirm
            title="Delete conversation"
            description="Permanently delete all questions, answers, saved quotations and idempotency records in this conversation? Original documents remain. This cannot be undone in the app."
            onConfirm={async () => {
              await api.deleteConversation(workspace.id, conversationId);
              router.replace("/workspaces/" + workspace.id + "/conversations");
            }}
          />
        </div>
      </details>
      {!!error && <ErrorBox error={error} />}
      {history.error ? (
        <ErrorBox error={history.error} retry={history.refresh} />
      ) : history.loading && !history.data ? (
        <Loading />
      ) : messages.length === 0 ? (
        <Empty title="A fresh line of inquiry">
          Ask your first question. Your source-backed research trail will appear
          here.
        </Empty>
      ) : (
        <section className="thread" aria-label="Conversation messages">
          {messages.map((message) => (
            <article
              className={
                message.role === "user"
                  ? "user-message"
                  : "panel assistant-message"
              }
              key={message.id}
            >
              <div className="message-sequence">
                #{message.sequence} · {date(message.created_at)}
              </div>
              {message.role === "user" ? (
                <>
                  <strong>You</strong>
                  <p>{message.content}</p>
                </>
              ) : (
                <AnswerView
                  content={message.content}
                  pending={message.generation_status === "pending"}
                  status={message.answer_status}
                  reason={message.reason}
                  model={message.model_identifier}
                  claims={message.claims}
                  citations={message.citations}
                  workspace={workspace.id}
                />
              )}
            </article>
          ))}
        </section>
      )}
      {latestHistory.error && latest && (
        <ErrorBox error={latestHistory.error} retry={latestHistory.refresh} />
      )}
      <nav className="pager" aria-label="Message pagination">
        <button
          className="button small"
          disabled={pages.length === 1}
          onClick={() => {
            setPages(pages.slice(0, -1));
            setLatest(null);
          }}
        >
          Previous messages
        </button>
        <span>Ordered by sequence · page {pages.length}</span>
        <button
          className="button small"
          disabled={!history.data?.next_after_sequence}
          onClick={() => {
            setPages([...pages, history.data!.next_after_sequence!]);
            setLatest(null);
          }}
        >
          Next messages
        </button>
      </nav>
      {latest && history.data?.next_after_sequence && (
        <p className="hint">
          Your latest submitted turn is also shown below this page of history.
        </p>
      )}
      {current.archived_at ? (
        <p className="notice">
          Archived conversations accept no new questions. Restore it to
          continue.
        </p>
      ) : (
        <form
          className="panel question-form"
          onSubmit={(event) => void send(event)}
        >
          <label>
            {uncertain ? "Unconfirmed submission" : "Ask a follow-up question"}
            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              required
              maxLength={2000}
              rows={3}
              disabled={busy || uncertain || pending}
              placeholder="What does the evidence say about…?"
            />
          </label>
          <DocumentFilter value={filters} onChange={setFilters} />
          <div className="question-footer">
            <label>
              Maximum passages
              <input
                type="number"
                min={1}
                max={12}
                value={limit}
                disabled={busy || uncertain || pending}
                onChange={(event) =>
                  setLimit(
                    Math.max(1, Math.min(12, Number(event.target.value) || 1)),
                  )
                }
              />
            </label>
            <button
              className="button primary"
              disabled={
                busy || pending || (!uncertain && !validQuestion(question))
              }
            >
              {busy
                ? "Reviewing evidence…"
                : pending
                  ? "Turn still pending"
                  : uncertain
                    ? "Retry same submission"
                    : "Send question ↗"}
            </button>
          </div>
          {uncertain && (
            <p className="notice">
              The request may already have been saved. Retry reuses the exact
              question, source filters and idempotency key. Do not create
              another copy while its outcome is uncertain.
            </p>
          )}
          {pending && (
            <p className="hint" role="status">
              One turn is generating. History refreshes every five seconds while
              visible; interrupted turns recover after the server lease expires.
            </p>
          )}
        </form>
      )}
    </>
  );
}
