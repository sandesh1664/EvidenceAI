# Local indexing and Gemini repair — 2026-10-24

The local document workflow is running with Gemini embeddings and
`gemini-3.5-flash-lite` generation. Live document transfer was explicitly authorized
by the local operator, who confirmed free-tier access and quota. The existing
backend key was preserved in the ignored, mode-0600 API environment file.

## Changes

- Started the missing document worker and restarted the API with matching settings.
- Enabled the existing Gemini privacy/provider opt-ins after authorization.
- Replaced the unavailable generation model with an explicitly configured,
  reviewed model. The former 2.5 generation models returned 404 for this project
  despite appearing in model metadata; no automatic fallback was added.
- Added support for current response signature metadata and bounded thinking-token
  accounting. Output remains capped at 1000 tokens across quotation selection and
  relevance review; provider and indexing attempts are limited to one.
- Gemini 3.5 selects immutable IDs for bounded, server-prepared source passages.
  The server assigns the original text and citation from its own mapping; the model
  never has to retype PDF quotations. Source checks, independent relevance review
  and final citation/authorization checks remain required. The review also checks
  that selected passages collectively cover every part of a compound question.
- Blocked indexing now shows its actual provider blocker. Research no longer
  reports missing evidence when provider configuration is the blocker.
- Local navigation through `127.0.0.1:3000` redirects to the trusted
  `localhost:3000` origin. Production and same-origin deployments are unaffected.

## Verification

- Backend: **834 passed**, using an owned disposable PostgreSQL database; cleanup
  and empty-baseline checks passed. No application data was used by tests.
- Frontend: **75 passed**; TypeScript, changed-file ESLint and whitespace checks passed.
- Authorized live indexing: one document, **5/5 chunks**, completed on the first attempt.
- Authorized browser question: **answered**, three retrieved evidence items, with
  a validated page-1 citation. The source-details control opened the matching excerpt.
- Follow-up compound question about technical/legal due diligence and transition
  support: **answered**, five retrieved evidence items, with validated page-3 and
  page-2 citations. This exercised answer revision **2** and the source-span ID
  contract after reproducing the former quotation/source mismatch.
- API health, trusted-origin authentication and the absolute localhost redirect
  were checked against the running services. The original document and extraction
  were retained, and generation-model changes reused the completed embedding index.

These checks establish the observed local workflow. They do not establish general
answer accuracy, future quota availability or production acceptance.

Model references: [Google pricing](https://ai.google.dev/gemini-api/docs/pricing),
[Gemini 3.5 Flash-Lite](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite),
and [Generate Content thinking](https://ai.google.dev/gemini-api/docs/generate-content/thinking).
