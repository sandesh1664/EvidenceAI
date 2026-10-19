"use client";
import { useState } from "react";
import { useResource } from "@/hooks/use-resource";
import { wsPath } from "@/lib/api/client";
import type { Document } from "@/types/api";
import { useWorkspace } from "@/components/workspaces/context";
import { ErrorBox, Loading, Pager } from "@/components/ui";
export function DocumentFilter({
  value,
  onChange,
}: {
  value: string[] | null;
  onChange: (value: string[] | null) => void;
}) {
  const { workspace, account } = useWorkspace();
  const [offset, setOffset] = useState(0);
  const documents = useResource<Document[]>(
    wsPath(workspace.id) + `/documents/?limit=20&offset=${offset}`,
    account,
  );
  return (
    <details className="filter">
      <summary>
        Sources ·{" "}
        {value === null
          ? "all workspace documents"
          : value.length + " selected"}
      </summary>
      <div className="filter-content">
        <label className="checkbox">
          <input
            type="checkbox"
            checked={value === null}
            onChange={(event) => onChange(event.target.checked ? null : [])}
          />
          Use all workspace documents
        </label>
        <p className="hint">
          Unchecked with no selections means no evidence. Only indexed documents
          can answer.
        </p>
        {documents.loading ? (
          <Loading />
        ) : documents.error ? (
          <ErrorBox error={documents.error} retry={documents.refresh} />
        ) : (
          documents.data?.map((document) => (
            <label className="checkbox" key={document.id}>
              <input
                type="checkbox"
                checked={value?.includes(document.id) || false}
                disabled={
                  value === null ||
                  (!value?.includes(document.id) &&
                    !!value &&
                    value.length >= 50)
                }
                onChange={(event) =>
                  onChange(
                    event.target.checked
                      ? [...(value || []), document.id]
                      : (value || []).filter((id) => id !== document.id),
                  )
                }
              />
              <span>
                {document.original_filename}
                <small>{document.processing_status}</small>
              </span>
            </label>
          ))
        )}
        <Pager
          offset={offset}
          count={documents.data?.length || 0}
          size={20}
          onChange={setOffset}
        />
      </div>
    </details>
  );
}
