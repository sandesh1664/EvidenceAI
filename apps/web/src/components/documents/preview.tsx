"use client";
import { useState } from "react";
import { useResource } from "@/hooks/use-resource";
import { wsPath } from "@/lib/api/client";
import { useWorkspace } from "@/components/workspaces/context";
import { Badge, Empty, ErrorBox, Loading } from "@/components/ui";
import type { ChunkPage } from "@/types/api";

export function DocumentPreview({ documentId }: { documentId: string }) {
  const { workspace, account } = useWorkspace();
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("");
  const [offset, setOffset] = useState(0);
  const data = useResource<ChunkPage>(
    wsPath(workspace.id) +
      `/documents/${encodeURIComponent(documentId)}/chunks?limit=5&offset=${offset}&query=${encodeURIComponent(filter)}`,
    account,
  );
  return (
    <section className="chunk-preview" aria-label="Extracted source preview">
      <form
        onSubmit={(event) => {
          event.preventDefault();
          setOffset(0);
          setFilter(query.trim());
        }}
      >
        <label>
          Find text in extracted chunks
          <input
            type="search"
            maxLength={200}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <button className="button small">Find in document</button>
      </form>
      {data.loading ? (
        <Loading />
      ) : data.error ? (
        <ErrorBox error={data.error} retry={data.refresh} />
      ) : !data.data?.items.length ? (
        <Empty title="No extracted passages">
          Check extraction status or try another phrase.
        </Empty>
      ) : (
        data.data.items.map((item) => (
          <article key={item.chunk_id} className="preview-passage">
            <div>
              <Badge>Chunk {item.chunk_index + 1}</Badge>
              {item.page_number !== null && (
                <Badge>Page {item.page_number}</Badge>
              )}
              {item.section && <Badge>{item.section}</Badge>}
            </div>
            <pre>{item.excerpt}</pre>
            <small>
              Characters {item.char_start}–{item.char_end}
              {item.truncated ? " · preview truncated" : ""}
            </small>
          </article>
        ))
      )}
      <div className="actions">
        <button
          className="button small"
          disabled={offset === 0 || data.loading}
          onClick={() => setOffset(Math.max(0, offset - 5))}
        >
          Previous passages
        </button>
        <button
          className="button small"
          disabled={data.loading || data.data?.next_offset == null}
          onClick={() => setOffset(data.data!.next_offset!)}
        >
          Next passages
        </button>
      </div>
      <p className="hint">
        Extracted text, not an interpretation. Layout can be imperfect; check
        the original for tables and figures.
      </p>
    </section>
  );
}
