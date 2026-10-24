"use client";
import { DocumentPreview } from "@/components/documents/preview";
import { ProviderStatus } from "@/components/chat/provider-status";
import { useState } from "react";
import { readinessMessage } from "@/lib/research-readiness";
import { useResource } from "@/hooks/use-resource";
import {
  api,
  ApiError,
  downloadDocument,
  errorMessage,
  wsPath,
} from "@/lib/api/client";
import { useWorkspace } from "@/components/workspaces/context";
import type { Document, IndexStatus } from "@/types/api";
import {
  Badge,
  Confirm,
  Empty,
  ErrorBox,
  Loading,
  PageHeading,
  Pager,
  date,
} from "@/components/ui";
export const MAX_UPLOAD_BYTES =
  Number(process.env.NEXT_PUBLIC_UPLOAD_MAX_BYTES) || 20 * 1024 * 1024;
export function fileError(file: File) {
  if (!/\.(pdf|txt|md)$/i.test(file.name))
    return "Choose a PDF, TXT or Markdown file.";
  if (file.size === 0) return "The file is empty.";
  if (file.size > MAX_UPLOAD_BYTES)
    return `File exceeds the ${Math.round(MAX_UPLOAD_BYTES / 1024 / 1024)} MB client upload limit.`;
  return null;
}
export function extractionLabel(document: Pick<Document, "processing_status">) {
  return {
    pending: "Pending extraction",
    processing: "Processing",
    completed: "Extraction complete",
    failed: "Extraction failed",
  }[document.processing_status];
}
export function indexingLabel(index: IndexStatus) {
  if (index.indexing_blocker && !index.indexing_complete)
    return "Indexing blocked";
  if (index.state === "done")
    return index.total_chunks === index.indexed_chunks
      ? "Indexed"
      : "Index job finished";
  if (index.state === "running") return "Indexing";
  if (index.state === "queued") return "Pending indexing";
  if (index.state === "failed") return "Indexing failed";
  return "Not indexed";
}
export function Upload({ onDone }: { onDone: () => void }) {
  const { workspace } = useWorkspace();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [status, setStatus] = useState("");
  const [drag, setDrag] = useState(false);
  const [progress, setProgress] = useState({ complete: 0, total: 0 });
  async function upload(files: FileList | File[] | null) {
    if (!files || busy) return;
    const list = Array.from(files);
    setError(undefined);
    setStatus("");
    for (const file of list) {
      const invalid = fileError(file);
      if (invalid) {
        setError(new ApiError(422, file.name + ": " + invalid));
        return;
      }
    }
    setBusy(true);
    setProgress({ complete: 0, total: list.length });
    try {
      for (const file of list) {
        setStatus("Uploading " + file.name + "…");
        await api.upload(workspace.id, file);
        setProgress((value) => ({ ...value, complete: value.complete + 1 }));
      }
      setStatus(
        `${list.length} file${list.length === 1 ? "" : "s"} uploaded. Extraction is queued; the background worker must be running.`,
      );
      onDone();
    } catch (error) {
      setError(error);
      setStatus(
        "Upload stopped. Refresh the library before retrying; earlier files may have succeeded.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div
        className={"upload-zone " + (drag ? "dragging" : "")}
        onDragOver={(event) => {
          event.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDrag(false);
          void upload(event.dataTransfer.files);
        }}
      >
        <span className="upload-icon" aria-hidden="true">
          ↑
        </span>
        <h2>Bring your sources together</h2>
        <p>Drop files here, or choose from your computer.</p>
        <label className="button primary upload-label">
          {busy ? "Uploading…" : "Choose files"}
          <input
            aria-label="Upload documents"
            type="file"
            multiple
            accept=".pdf,.txt,.md"
            disabled={busy}
            onChange={(event) => {
              void upload(event.target.files);
              event.target.value = "";
            }}
          />
        </label>
        <small>
          PDF, TXT, Markdown · up to{" "}
          {Math.round(MAX_UPLOAD_BYTES / 1024 / 1024)} MB per file · server
          validation applies
        </small>
      </div>
      {busy && (
        <label>
          Files uploaded: {progress.complete} / {progress.total}
          <progress max={progress.total || 1} value={progress.complete} />
        </label>
      )}
      <p className="hint" role="status">
        {status}
      </p>
      {!!error && <ErrorBox error={error} />}
    </>
  );
}
function DocumentRow({ document }: { document: Document }) {
  const { workspace, role, account } = useWorkspace();
  const index = useResource<IndexStatus>(
    document.processing_status === "completed"
      ? wsPath(workspace.id) + "/documents/" + document.id + "/index"
      : null,
    account,
    12000,
  );
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState(false);
  const manager = role === "owner" || role === "admin";
  const canDelete = manager;
  async function perform(action: () => Promise<unknown>) {
    setError(undefined);
    setBusy(true);
    try {
      await action();
    } catch (error) {
      setError(error);
    } finally {
      setBusy(false);
    }
  }
  return (
    <article className="document-row">
      <div className="document-main">
        <span className="file-icon" aria-hidden="true">
          ▤
        </span>
        <div>
          <h3>{document.original_filename}</h3>
          <p>
            {document.file_size !== null
              ? `${(document.file_size / 1024).toFixed(1)} KB · `
              : ""}
            {date(document.created_at)}
          </p>
        </div>
        <Badge
          tone={
            document.processing_status === "completed"
              ? "green"
              : document.processing_status === "failed"
                ? "red"
                : ""
          }
        >
          {extractionLabel(document)}
        </Badge>
      </div>
      {document.processing_error && (
        <p className="notice danger">
          {document.processing_error}.{" "}
          {document.processing_attempts >= 3
            ? "The default retry budget may be exhausted; an operator may need to review this document."
            : "Review the file or retry processing."}
        </p>
      )}
      {document.processing_status === "completed" && (
        <div className="index-line">
          {index.loading && !index.data ? (
            <span>Checking index…</span>
          ) : index.error ? (
            <span className="hint">
              {index.error instanceof ApiError && index.error.status === 503
                ? "Index unavailable. Embeddings may be disabled; ask your deployment operator."
                : errorMessage(index.error)}
            </span>
          ) : (
            index.data && (
              <>
                <Badge
                  tone={
                    index.data.indexing_blocker && !index.data.indexing_complete
                      ? "red"
                      : index.data.state === "done"
                        ? "green"
                        : index.data.state === "failed"
                          ? "red"
                          : ""
                  }
                >
                  {indexingLabel(index.data)}
                </Badge>
                {index.data.ready_for_research && (
                  <Badge tone="green">Ready for research</Badge>
                )}
                {index.data.embedding_model.startsWith("fake:") && (
                  <Badge>Offline index only</Badge>
                )}
                {(index.data.indexing_blocker ||
                  index.data.research_blocker) && (
                  <small
                    role={index.data.indexing_blocker ? "status" : undefined}
                  >
                    {readinessMessage(
                      index.data.indexing_blocker ||
                        index.data.research_blocker!,
                    )}
                  </small>
                )}
                <span>
                  {index.data.indexed_chunks} / {index.data.total_chunks} chunks
                  indexed
                </span>
                <small>
                  {index.data.embedding_model.startsWith("fake:")
                    ? "Offline test embedding profile"
                    : index.data.embedding_model}
                </small>
                {index.data.error && (
                  <span className="notice danger">{index.data.error}</span>
                )}
              </>
            )
          )}
        </div>
      )}
      {document.processing_status === "completed" && (
        <>
          <button
            className="button small"
            aria-expanded={preview}
            onClick={() => setPreview(!preview)}
          >
            {preview ? "Hide extracted preview" : "Preview extracted text"}
          </button>
          {preview && <DocumentPreview documentId={document.id} />}
        </>
      )}
      <div className="actions">
        <button
          className="button small"
          disabled={busy}
          onClick={() =>
            void perform(() =>
              downloadDocument(
                workspace.id,
                document.id,
                document.original_filename,
              ),
            )
          }
        >
          Download original
        </button>
        {manager && document.processing_status === "failed" && (
          <button
            className="button small"
            disabled={busy}
            onClick={() =>
              void perform(() => api.retryDocument(workspace.id, document.id))
            }
          >
            Retry extraction
          </button>
        )}
        {manager && index.data?.state === "not_indexed" && (
          <button
            className="button small"
            disabled={busy || !!index.data.indexing_blocker}
            onClick={() =>
              void perform(() => api.index(workspace.id, document.id))
            }
          >
            Index document
          </button>
        )}
        {manager && index.data?.state === "failed" && (
          <button
            className="button small"
            disabled={busy || !!index.data.indexing_blocker}
            onClick={() =>
              void perform(() => api.retryIndex(workspace.id, document.id))
            }
          >
            Retry indexing
          </button>
        )}
        {manager &&
          index.data &&
          !index.data.indexing_blocker &&
          (index.data.state === "failed" || index.data.state === "done") && (
            <Confirm
              title="Rebuild index"
              description="Start a new indexing generation? This may send document text to your configured provider and incur costs when hosted indexing is enabled."
              onConfirm={() =>
                api.index(workspace.id, document.id, true).then(() => undefined)
              }
            />
          )}
        {canDelete && (
          <Confirm
            title="Delete document"
            description={`Delete ${document.original_filename} and its extracted/indexed data? Historical quotations in saved conversations remain until those conversations are deleted.`}
            onConfirm={() => api.removeDocument(workspace.id, document.id)}
          />
        )}
      </div>
      {!!error && <ErrorBox error={error} />}
    </article>
  );
}
export function Library() {
  const { workspace, role, account } = useWorkspace();
  const [offset, setOffset] = useState(0);
  const [query, setQuery] = useState("");
  const resource = useResource<Document[]>(
    wsPath(workspace.id) + `/documents/?limit=20&offset=${offset}`,
    account,
    10000,
  );
  const rows =
    resource.data?.filter((document) =>
      document.original_filename.toLowerCase().includes(query.toLowerCase()),
    ) || [];
  return (
    <>
      <PageHeading
        eyebrow={workspace.name}
        title="Document library"
        description="Original sources, extraction and indexing. A clear view of what is ready for research."
      />
      <ProviderStatus />
      {role === "owner" || role === "admin" ? (
        <Upload
          onDone={() => {
            setOffset(0);
            resource.refresh();
          }}
        />
      ) : (
        <p className="notice">
          Workspace owners and admins can upload and manage documents.
        </p>
      )}
      <section className="panel">
        <div className="section-heading">
          <h2>Your sources</h2>
          <button className="button small" onClick={resource.refresh}>
            Refresh status
          </button>
        </div>
        <label className="search-field">
          Filter this page by filename
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Find a document…"
          />
        </label>
        <p className="hint">
          Filename filtering applies to this loaded page. Use semantic search
          for passage retrieval. Status checks pause when this page is hidden.
        </p>
        {resource.loading && !resource.data ? (
          <Loading />
        ) : resource.error ? (
          <ErrorBox error={resource.error} retry={resource.refresh} />
        ) : !rows.length ? (
          <Empty title={query ? "No matching filenames" : "No sources yet"}>
            {query
              ? "Try another filename or page."
              : "Upload your first document to start building an evidence library."}
          </Empty>
        ) : (
          rows.map((document) => (
            <DocumentRow key={document.id} document={document} />
          ))
        )}
        <Pager
          offset={offset}
          count={resource.data?.length || 0}
          size={20}
          onChange={(value) => {
            setOffset(value);
            setQuery("");
          }}
        />
      </section>
    </>
  );
}
