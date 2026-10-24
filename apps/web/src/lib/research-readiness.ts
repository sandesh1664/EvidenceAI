const messages: Record<string, string> = {
  live_requests_blocked:
    "Gemini requests are disabled in the server configuration.",
  api_key_missing:
    "The server needs a Gemini API key before indexing can begin.",
  free_tier_not_confirmed:
    "Gemini free-tier access and quota must be confirmed before requests can begin.",
  data_transfer_not_authorized:
    "Sending document text and questions to Gemini has not been authorized.",
  private_document_transfer_not_authorized:
    "Sending private document text to Gemini has not been authorized.",
  hosted_provider_not_authorized: "The hosted provider has not been enabled.",
  external_requests_not_authorized:
    "External provider requests have not been enabled.",
  environment_not_allowed:
    "This Gemini integration is available only in local development and tests.",
  provider_disabled: "This provider is disabled in the server configuration.",
  active_profile_not_indexed:
    "This document needs indexing with the active embedding profile.",
  no_extracted_chunks: "This document has no extracted text to index.",
};

export function readinessMessage(code: string): string {
  return (
    messages[code] || "Check the provider configuration and document index."
  );
}
