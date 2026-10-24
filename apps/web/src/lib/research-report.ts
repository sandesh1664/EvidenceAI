import type { Answer } from "@/types/api";

// A user-initiated local text export, never an HTML document or external upload.
export function researchReport(question: string, answer: Answer): string {
  const lines = [
    "EvidenceAI research evidence",
    "",
    `Question: ${question}`,
    `Status: ${answer.status}`,
    `Provider: ${answer.model_identifier || "unreported"}`,
    `Request: ${answer.request_id}`,
    "",
    "Source quotations only. Source credibility and semantic truth are not assessed.",
    "",
  ];
  for (const claim of answer.claims)
    lines.push(
      `${claim.text} ${claim.citation_ids.map((id) => `[${id}]`).join(" ")}`,
      "",
    );
  if (!answer.claims.length) lines.push(answer.answer, "");
  lines.push("Sources");
  for (const citation of answer.citations)
    lines.push(
      `[${citation.citation_id}] ${citation.filename}${citation.page_number === null ? "" : ` · page ${citation.page_number}`}`,
      `Document: ${citation.document_id} · Chunk: ${citation.chunk_id}`,
      `Characters: ${citation.char_start}–${citation.char_end}`,
      citation.supporting_excerpt,
      "",
    );
  return lines.join("\n");
}
export function exportResearch(question: string, answer: Answer) {
  const url = URL.createObjectURL(
    new Blob([researchReport(question, answer)], {
      type: "text/plain;charset=utf-8",
    }),
  );
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "evidenceai-research.txt";
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
