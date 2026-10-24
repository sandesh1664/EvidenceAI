"use client";
import { useResource } from "@/hooks/use-resource";
import { useWorkspace } from "@/components/workspaces/context";
import { wsPath } from "@/lib/api/client";
import { Badge } from "@/components/ui";
import type { ResearchStatus } from "@/types/api";
import { readinessMessage } from "@/lib/research-readiness";

export function ProviderStatus() {
  const { workspace, account } = useWorkspace();
  const status = useResource<ResearchStatus>(
    wsPath(workspace.id) + "/research-status",
    account,
    12000,
  );
  const data = status.data;
  return (
    <section className="provider-status panel" aria-label="Research readiness">
      <strong>Research readiness</strong>
      {status.error ? (
        <p className="hint">
          Readiness unavailable. Refresh before relying on a document’s status.
        </p>
      ) : !data?.providers ? (
        <p className="hint">Checking the active provider and document index…</p>
      ) : (
        <>
          {Object.values(data.providers).some(
            (provider) => provider.offline,
          ) && (
            <p className="notice">
              An offline test provider is active. Lexical source selection is
              limited; this is not a verified Gemini workflow.
            </p>
          )}
          <div className="actions">
            <Badge>
              {data.processing_complete} / {data.documents} processed
            </Badge>
            <Badge>{data.indexing_complete} indexed for this profile</Badge>
            <Badge tone={data.ready_for_research ? "green" : ""}>
              {data.ready_for_research} ready for research
            </Badge>
          </div>
          {Object.entries(data.providers).map(([kind, provider]) => (
            <p className="hint" key={kind}>
              {kind === "llm" ? "Answers" : "Embeddings"}: {provider.provider} ·{" "}
              {provider.model}
              {provider.offline
                ? " · Offline test provider"
                : " · External provider; availability checked per request"}
              {!provider.configured &&
                " · " + readinessMessage(provider.blocker || "")}
            </p>
          ))}
          <small>
            Ready means current profile and local configuration are complete. It
            does not verify remote availability or answer quality.
          </small>
        </>
      )}
    </section>
  );
}
