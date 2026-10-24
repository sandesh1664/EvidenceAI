# Document QA repair verification — 2026-10-21

Real Gemini end-to-end operation: **NOT VERIFIED / BLOCKED**. No Google request was made or authorized. Actual local configuration selects fake embeddings and mock generation; the backend key is absent. Existing development services remain running. Production release remains **FAIL / BLOCKED**.

## Implemented repair

Gemini previously encountered a literal question-word veto before generation and again during citation validation. RAG also admitted only the first 1000 characters of a search preview. It now admits bounded full chunks and permits Gemini paraphrase relevance only after a separate structured relevance review. Exact source quotations, admitted citation IDs, numeric qualifiers, injection guards, workspace/source authorization and post-generation rechecks remain enforced. An invented quote stops before review; negative, incomplete or conflicting review abstains. Review failure has no mock fallback.

Answered Gemini turns can use two generation requests, sharing the configured output cap and total timeout. This changes future live approval and pricing scope. Missing configuration, denied access, model availability, invalid keys and quota failures have fixed safe messages. Blocked workers leave jobs queued without consuming attempts. Offline indexing is labelled explicitly. The synthetic probe now uses actual upload and extraction before indexing, retrieval and citation validation.

## Verification results

| Check | Actual result |
| --- | --- |
| Complete isolated backend suite | PASS: 762 passed in 32.07s; one existing Starlette/httpx deprecation warning |
| Frontend | PASS: 64 tests, 6 files, 2.17s |
| Integrated browser/TLS mail | PASS: 24 tests, Chromium/Firefox/WebKit, 1.8m; fake/mock AI |
| Production-mode browser build | PASS, as part of the isolated browser pipeline |
| ESLint / TypeScript | PASS |
| Security regression suite | PASS: 11 tests in 8.979s |
| Offline evaluation | PASS: 36 samples; zero threshold failures; fake/mock only |
| Synthetic upload → extraction → embedding → retrieval → answer → citation | PASS with mocked Gemini HTTP responses, not a real Google result |
| Configuration doctor | PASS, configuration-only; no HTTP or database connection |
| Real Gemini embeddings, answer quality and project quota | NOT VERIFIED; explicit live approval absent |
| Development preservation | FAIL: one existing auth_sessions row changed only last_used_at; writer NOT VERIFIED |
| Production release validator | FAIL / BLOCKED: container_security, ai_security, ci_cd, production_environment unmet |

The preservation window was 2026-10-20 21:43:53–21:52:17 UTC. Session row counts were unchanged, with no additions or removals. The other 15 tables, other session columns, revision and transaction context matched. Private storage content and recorded metadata matched. Private snapshots and comparison keys remain outside Git in restricted local custody. Normal background activity is plausible but is not proven attribution. The owner explicitly declined pausing services and requested retaining FAIL / NOT VERIFIED. No session was altered to reconcile the result. Accordingly, complete development database preservation cannot be claimed.

## Exact commands

From the repository root, without manual PYTHONPATH:

```sh
apps/api/.venv/bin/python infra/testing/run_isolated.py --evidence-directory /tmp/evidenceai-qa-verified-backend -- apps/api/.venv/bin/python -m pytest apps/api/tests -q --tb=short --show-capture=no
npm --prefix apps/web test
npm --prefix apps/web run lint
(cd apps/web && ./node_modules/.bin/tsc --noEmit)
python3 -m unittest discover -s infra/security/tests -v
apps/api/.venv/bin/python infra/testing/run_isolated.py --evidence-directory /tmp/evidenceai-qa-evaluation -- apps/api/.venv/bin/python -m app.evaluate --output-dir /tmp/evidenceai-qa-evaluation-results --thresholds apps/api/evaluation/thresholds.json --repeat 1
python3 infra/scripts/verify_release.py docs/evidence/m126/release-result.json
```

Browser command used the same isolated runner with a new restricted evidence directory and `EVIDENCEAI_E2E_TLS_MAIL=1 PLAYWRIGHT_BROWSERS_PATH=/tmp/evidenceai-m126-browsers`, running `npm --prefix apps/web run test:e2e`. Its owned disposable services and databases did not use development targets. No existing development document was reindexed, no development migration ran, and no private document was sent externally.

Final secret-gate, cleanup and static-integrity results are recorded below after execution. Existing staged work, ignored backend environment and historical evidence are preserved separately from this repair. No commits, pushes, deployments or release-gate changes were made.

## Files changed by this repair

- `README.md`
- `apps/api/app/core/config.py`
- `apps/api/app/gemini_probe.py`
- `apps/api/app/gemini_setup.py`
- `apps/api/app/services/citation_validation.py`
- `apps/api/app/services/embedding_jobs.py`
- `apps/api/app/services/gemini_configuration.py`
- `apps/api/app/services/gemini_providers.py`
- `apps/api/app/services/llm_providers.py`
- `apps/api/app/services/provider_errors.py`
- `apps/api/app/services/rag_service.py`
- `apps/api/app/services/research_readiness.py`
- `apps/api/app/services/search_service.py`
- `apps/api/tests/test_document_qa.py`
- `apps/api/tests/test_gemini.py`
- `apps/web/src/components/chat/provider-status.tsx`
- `apps/web/src/components/documents/library.tsx`
- `apps/web/src/lib/api/client.ts`
- `apps/web/src/test/application.test.tsx`
- `docs/document-qa-setup.md`
- `docs/document-qa-verification.md`
- `docs/gemini-integration.md`
- `docs/gemini-provider-integration.md`
- `docs/local-gemini-setup.md`
- `docs/research-and-citation-validation.md`

See [document-qa-setup.md](document-qa-setup.md) for exact environment, startup and authorized reindex instructions and the separate future live-test approval requirements.

## Final static and cleanup checks

- Exact `python3 infra/security/scan_secrets.py --private-directory <restricted-case>/secret-gate-final`: PASS, zero unreviewed findings; 320 existing adjudicated findings. Unsuppressed history/current/archive scans retained 134/134/52 detections respectively; these were not hidden or broadly suppressed. Raw scanner output remains outside Git.
- Six owned disposable isolation receipts: clean, zero remaining schemas, container removal recorded.
- 415 protected historical evidence/policy/verification files unchanged; original staged patch, HEAD and ignored backend environment unchanged.
- `git diff --check`: PASS.

These results do not override the preservation FAIL, real-Gemini NOT VERIFIED or production FAIL / BLOCKED decisions.
