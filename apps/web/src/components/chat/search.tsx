"use client";
import { ProviderStatus } from "@/components/chat/provider-status";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api/client";
import { useWorkspace } from "@/components/workspaces/context";
import { DocumentFilter } from "@/components/documents/filter";
import { SourcePanel } from "@/components/citations/answer";
import type { SearchResult } from "@/types/api";
import {
  Badge,
  Empty,
  ErrorBox,
  PageHeading,
  validQuestion,
} from "@/components/ui";
export function Search() {
  const { workspace } = useWorkspace();
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState<string[] | null>(null);
  const [limit, setLimit] = useState(10);
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [selected, setSelected] = useState<SearchResult | null>(null);
  const [offset, setOffset] = useState(0);
  const [pageSize, setPageSize] = useState(10);
  const last = useRef({
    query: "",
    filters: null as string[] | null,
    limit: 10,
  });
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  async function run(start: number, reset = false) {
    if (busy || (reset && !validQuestion(query))) return;
    if (reset) last.current = { query: query.trim(), filters, limit };
    const params = last.current;
    setPageSize(params.limit);
    setOffset(start);
    setBusy(true);
    setError(undefined);
    setResults(null);
    setSelected(null);
    controller.current = new AbortController();
    try {
      setResults(
        await api.search(
          workspace.id,
          params.query,
          params.filters,
          params.limit,
          controller.current.signal,
          start,
        ),
      );
    } catch (error) {
      if (!(error instanceof DOMException && error.name === "AbortError"))
        setError(error);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeading
        eyebrow={workspace.name}
        title="Find the relevant passage"
        description="Search indexed documents across this workspace. Similarity is a ranking score, not proof or confidence."
      />
      <ProviderStatus />
      <form
        className="panel"
        onSubmit={(event) => {
          event.preventDefault();
          void run(0, true);
        }}
      >
        <label>
          Search query
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            required
            maxLength={2000}
            placeholder="Search the evidence…"
          />
        </label>
        <div className="inline-form">
          <div className="grow">
            <DocumentFilter value={filters} onChange={setFilters} />
          </div>
          <label>
            Results
            <input
              type="number"
              min={1}
              max={50}
              value={limit}
              onChange={(event) =>
                setLimit(
                  Math.max(1, Math.min(50, Number(event.target.value) || 1)),
                )
              }
            />
          </label>
          <button
            className="button primary"
            disabled={busy || !validQuestion(query)}
          >
            {busy ? "Searching…" : "Search passages"}
          </button>
        </div>
      </form>
      {!!error && <ErrorBox error={error} />}
      {results && (
        <p className="hint" role="status">
          {results.length} passages returned, ordered by relevance.
        </p>
      )}
      {results?.length === 0 ? (
        <Empty title="No matching indexed passages">
          Try another query, check source filters, or ensure extraction and
          indexing have completed.
        </Empty>
      ) : (
        results?.map((result, index) => (
          <article className="panel search-result" key={result.chunk_id}>
            <div className="section-heading">
              <h2>
                <span className="rank">{offset + index + 1}</span>
                {result.filename}
              </h2>
              <Badge>Similarity {result.similarity.toFixed(3)}</Badge>
            </div>
            <blockquote>{result.excerpt}</blockquote>
            <div className="actions">
              <span className="hint">
                {result.page_number !== null
                  ? "Page " + result.page_number
                  : ""}
                {result.section && " · " + result.section}
              </span>
              <button
                className="button small"
                onClick={() => setSelected(result)}
              >
                Inspect source
              </button>
              <span className="hint">
                {result.embedding_model.startsWith("fake:")
                  ? "Offline lexical test embeddings"
                  : result.embedding_model}
              </span>
            </div>
          </article>
        ))
      )}
      {results && (
        <div className="actions" aria-label="Search result pages">
          <button
            className="button small"
            disabled={busy || offset === 0}
            onClick={() => void run(Math.max(0, offset - last.current.limit))}
          >
            Previous results
          </button>
          <span className="hint">
            Results {offset + (results.length ? 1 : 0)}–
            {offset + results.length}
          </span>
          <button
            className="button small"
            disabled={
              busy || results.length < pageSize || offset + pageSize > 1000
            }
            onClick={() => void run(offset + last.current.limit)}
          >
            Next results
          </button>
        </div>
      )}
      {selected && (
        <SourcePanel
          workspace={workspace.id}
          citation={{
            citation_id: "search",
            document_id: selected.document_id,
            chunk_id: selected.chunk_id,
            filename: selected.filename,
            page_number: selected.page_number,
            section: selected.section,
            supporting_excerpt: selected.excerpt,
          }}
          onClose={() => setSelected(null)}
        />
      )}
    </>
  );
}
