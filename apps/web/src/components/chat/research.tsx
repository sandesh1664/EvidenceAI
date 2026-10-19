"use client";
import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api/client";
import { useWorkspace } from "@/components/workspaces/context";
import { DocumentFilter } from "@/components/documents/filter";
import { AnswerView } from "@/components/citations/answer";
import type { Answer } from "@/types/api";
import { Empty, ErrorBox, PageHeading, validQuestion } from "@/components/ui";
export function Research() {
  const { workspace } = useWorkspace();
  const [question, setQuestion] = useState("");
  const [filters, setFilters] = useState<string[] | null>(null);
  const [limit, setLimit] = useState(6);
  const [busy, setBusy] = useState(false);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [asked, setAsked] = useState("");
  const [error, setError] = useState<unknown>();
  const abort = useRef<AbortController | null>(null);
  useEffect(() => () => abort.current?.abort(), []);
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (busy || !validQuestion(question)) return;
    setBusy(true);
    setError(undefined);
    setAnswer(null);
    setAsked(question.trim());
    abort.current = new AbortController();
    try {
      setAnswer(
        await api.ask(
          workspace.id,
          {
            question: question.trim(),
            document_ids: filters,
            retrieval_limit: limit,
          },
          abort.current.signal,
        ),
      );
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      if (
        error instanceof ApiError &&
        error.payload &&
        typeof error.payload === "object" &&
        "status" in error.payload &&
        "answer" in error.payload
      )
        setAnswer(error.payload as Answer);
      else setError(error);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeading
        eyebrow={workspace.name}
        title="Ask the evidence"
        description="A focused question. Fresh document retrieval. Source quotations you can inspect."
      />
      <div className="research-layout">
        <section>
          <form className="panel question-form" onSubmit={submit}>
            <label>
              Your research question
              <textarea
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                maxLength={2000}
                required
                rows={4}
                placeholder="What do the documents say about…?"
                disabled={busy}
              />
            </label>
            <div className="question-footer">
              <span className="hint">
                {[...question].length} / 2000 · responses are validated before
                display
              </span>
              <button
                className="button primary"
                disabled={busy || !validQuestion(question)}
              >
                {busy ? "Reviewing evidence…" : "Ask question ↗"}
              </button>
              {busy && (
                <button
                  type="button"
                  className="button"
                  onClick={() => {
                    abort.current?.abort();
                    setBusy(false);
                  }}
                >
                  Cancel
                </button>
              )}
            </div>
          </form>
          {!!error && <ErrorBox error={error} />}
          {answer ? (
            <section className="panel research-answer">
              <p className="asked-question">{asked}</p>
              <AnswerView
                content={answer.answer}
                status={answer.status}
                reason={answer.reason}
                model={answer.model_identifier}
                claims={answer.claims}
                citations={answer.citations}
                workspace={workspace.id}
              />
              <p className="hint">
                {answer.retrieved_evidence_count} evidence items · Request{" "}
                {answer.request_id}
                {answer.usage &&
                  ` · ${answer.usage.total_tokens} provider tokens`}
              </p>
            </section>
          ) : (
            !busy && (
              <Empty title="Start with a question worth following">
                Answers use current indexed documents. No evidence means no
                invented answer.
              </Empty>
            )
          )}
        </section>
        <aside className="research-controls">
          <div className="panel">
            <h2>Research scope</h2>
            <DocumentFilter value={filters} onChange={setFilters} />
            <label>
              Maximum passages
              <input
                type="number"
                min={1}
                max={12}
                value={limit}
                onChange={(event) =>
                  setLimit(
                    Math.min(12, Math.max(1, Number(event.target.value) || 1)),
                  )
                }
              />
            </label>
            <p className="hint">
              The server may apply a lower retrieval limit.
            </p>
          </div>
          <div className="guidance">
            <span aria-hidden="true">✧</span>
            <h3>Keep a clear source trail</h3>
            <p>
              These answers are exact source extracts. Inspect each quotation
              and its context before drawing conclusions.
            </p>
            <p>
              This quick question is not saved to history. Use Conversations for
              persistent research.
            </p>
          </div>
        </aside>
      </div>
    </>
  );
}
