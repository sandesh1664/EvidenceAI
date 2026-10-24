"use client";
import { ProviderStatus } from "@/components/chat/provider-status";
import { exportResearch } from "@/lib/research-report";
import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api/client";
import { useWorkspace } from "@/components/workspaces/context";
import { DocumentFilter } from "@/components/documents/filter";
import { AnswerView } from "@/components/citations/answer";
import type { Answer } from "@/types/api";
import { Empty, ErrorBox, PageHeading, validQuestion } from "@/components/ui";
export function Research() {
  const { workspace } = useWorkspace();
  const [mode, setMode] = useState<"question" | "summary" | "comparison">(
    "question",
  );
  const [answerMode, setAnswerMode] = useState(mode);
  const [question, setQuestion] = useState("");
  const [filters, setFilters] = useState<string[] | null>(null);
  const [limit, setLimit] = useState(6);
  const comparisonValid =
    mode !== "comparison" || (filters?.length === 2 && limit >= 2);
  const [busy, setBusy] = useState(false);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [asked, setAsked] = useState("");
  const [error, setError] = useState<unknown>();
  const abort = useRef<AbortController | null>(null);
  useEffect(() => () => abort.current?.abort(), []);
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (busy || !validQuestion(question) || !comparisonValid) return;
    setBusy(true);
    setError(undefined);
    setAnswer(null);
    setAsked(question.trim());
    setAnswerMode(mode);
    abort.current = new AbortController();
    try {
      setAnswer(
        await api.ask(
          workspace.id,
          {
            question: question.trim(),
            mode,
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
      <ProviderStatus />
      <div className="research-layout">
        <section>
          <form className="panel question-form" onSubmit={submit}>
            <label>
              Research format
              <select
                value={mode}
                disabled={busy}
                onChange={(event) => setMode(event.target.value as typeof mode)}
              >
                <option value="question">Question and evidence</option>
                <option value="summary">Cited topic brief</option>
                <option value="comparison">Compare two sources</option>
              </select>
            </label>
            <p className="hint">
              {mode === "question"
                ? "Ask in the language of your evidence. English and Nepali exact-source examples are covered offline; translation quality is not verified."
                : mode === "summary"
                  ? "Enter a topic found in your documents. The brief selects supporting quotations, not a complete-document or interpretive summary."
                  : "Select exactly two documents and enter a shared topic. Quotations are shown side by side; unsupported comparisons and conflicting evidence abstain."}
            </p>
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
                disabled={busy || !validQuestion(question) || !comparisonValid}
              >
                {busy
                  ? "Reviewing evidence…"
                  : mode === "question"
                    ? "Ask question ↗"
                    : mode === "summary"
                      ? "Build cited brief"
                      : "Compare sources"}
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
              {answerMode === "comparison" && answer.status === "answered" && (
                <section
                  className="comparison-grid"
                  aria-label="Evidence comparison"
                >
                  {Array.from(
                    new Set(
                      answer.citations.map((citation) => citation.document_id),
                    ),
                  ).map((id) => {
                    const sources = answer.citations.filter(
                      (citation) => citation.document_id === id,
                    );
                    return (
                      <article key={id || "historical"}>
                        <h3>{sources[0].filename}</h3>
                        {sources.map((source) => (
                          <blockquote key={source.citation_id}>
                            [{source.citation_id}] {source.supporting_excerpt}
                          </blockquote>
                        ))}
                        <p className="hint">Source credibility not assessed.</p>
                      </article>
                    );
                  })}
                </section>
              )}
              <button
                type="button"
                className="button small"
                onClick={() => exportResearch(asked, answer)}
              >
                Export cited evidence (.txt)
              </button>
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
            {!comparisonValid && (
              <p className="notice">
                Comparison needs exactly two selected documents and at least two
                passages.
              </p>
            )}
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
