"use client";
import { useState } from "react";
import type { AnswerStatus, Citation, Claim } from "@/types/api";
import { Badge, ErrorBox } from "@/components/ui";
import { downloadDocument } from "@/lib/api/client";
export function SourcePanel({
  citation,
  workspace,
  onClose,
}: {
  citation: Pick<
    Citation,
    | "citation_id"
    | "document_id"
    | "chunk_id"
    | "filename"
    | "page_number"
    | "section"
    | "supporting_excerpt"
  >;
  workspace: string;
  onClose: () => void;
}) {
  const [error, setError] = useState<unknown>();
  return (
    <section className="source-panel" aria-label="Source details">
      <div className="section-heading">
        <div>
          <span className="eyebrow">
            SUPPORTING SOURCE [{citation.citation_id}]
          </span>
          <h3>{citation.filename}</h3>
        </div>
        <button
          className="button small"
          aria-label="Close source"
          onClick={onClose}
        >
          ×
        </button>
      </div>
      <div className="source-meta">
        {citation.page_number !== null && (
          <Badge>Page {citation.page_number}</Badge>
        )}
        {citation.section && <Badge>{citation.section}</Badge>}
        {!citation.document_id && (
          <Badge tone="red">Original document deleted</Badge>
        )}
        {citation.document_id && !citation.chunk_id && (
          <Badge>Historical excerpt · chunk unavailable</Badge>
        )}
      </div>
      <blockquote>{citation.supporting_excerpt}</blockquote>
      <p className="hint">
        A source quotation. Lexical validation does not establish semantic
        correctness or that the source is true.
      </p>
      {citation.document_id ? (
        <button
          className="button small"
          onClick={() =>
            void downloadDocument(
              workspace,
              citation.document_id!,
              citation.filename,
            ).catch(setError)
          }
        >
          Download original
        </button>
      ) : (
        <p className="notice">
          This is a saved citation snapshot. The quotation remains available
          even though its original was deleted.
        </p>
      )}
      {!!error && <ErrorBox error={error} />}
    </section>
  );
}
export function AnswerView({
  content,
  status,
  reason,
  model,
  claims,
  citations,
  workspace,
  pending = false,
}: {
  content: string;
  status: AnswerStatus | null;
  reason: string | null;
  model: string | null;
  claims: Claim[];
  citations: Citation[];
  workspace: string;
  pending?: boolean;
}) {
  const [selected, setSelected] = useState<string | null>(null);
  const selectedSource = citations.find((c) => c.citation_id === selected);
  const offline = model?.startsWith("mock:");
  return (
    <div className="answer-view">
      <div className="answer-meta">
        <span className="answer-avatar" aria-hidden="true">
          ✧
        </span>
        <strong>EvidenceAI</strong>
        <Badge
          tone={
            status === "answered"
              ? "green"
              : status === "provider_error" ||
                  status === "retrieval_unavailable"
                ? "red"
                : ""
          }
        >
          {pending
            ? "Generation pending"
            : status?.replaceAll("_", " ") || "Pending"}
        </Badge>
        {offline && <Badge>Offline mock · source selection</Badge>}
        {model?.startsWith("gemini:") &&
          status === "answered" &&
          claims.length > 0 && (
            <Badge>Gemini · validated source extracts</Badge>
          )}
      </div>
      {claims.length ? (
        <div className="claims">
          {claims.map((claim) => (
            <p key={claim.claim_id}>
              {claim.text}{" "}
              <span className="citation-links">
                {claim.citation_ids.map((id) => (
                  <button
                    key={id}
                    className="citation-link"
                    aria-label={`Open source ${id}`}
                    onClick={() => setSelected(id)}
                  >
                    [{id}]
                  </button>
                ))}
              </span>
            </p>
          ))}
        </div>
      ) : (
        <p className="answer-content">
          {pending
            ? "This turn is still being processed. History refreshes while this page is active."
            : content}
        </p>
      )}
      {reason === "provider_quota" && (
        <p className="notice">
          The provider quota is exhausted. Automatic retries have stopped; ask
          the operator to verify free quota before retrying.
        </p>
      )}
      {reason?.includes("disabled") && (
        <p className="notice">
          The configured provider is disabled. Ask your deployment operator to
          configure and enable it; model settings are not editable here.
        </p>
      )}
      {status === "insufficient_evidence" && (
        <p className="hint">
          Try a more specific question, check your source selection, or confirm
          that documents are indexed.
        </p>
      )}
      {citations.length > 0 && (
        <div className="source-chips">
          {citations.map((citation) => (
            <button
              className="source-chip"
              key={citation.citation_id}
              onClick={() => setSelected(citation.citation_id)}
            >
              <span>[{citation.citation_id}]</span>
              {citation.filename}
              {citation.page_number !== null && (
                <small>p. {citation.page_number}</small>
              )}
            </button>
          ))}
        </div>
      )}
      {selectedSource && (
        <SourcePanel
          key={selectedSource.citation_id}
          citation={selectedSource}
          workspace={workspace}
          onClose={() => setSelected(null)}
        />
      )}
      <p className="hint model-info">
        {model || "Provider not reported"}
        {reason && " · " + reason.replaceAll("_", " ")}
      </p>
    </div>
  );
}
