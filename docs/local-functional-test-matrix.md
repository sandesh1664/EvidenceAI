# Local functional test matrix

Audit date: 2026-10-20 (Asia/Dubai). PASS applies only to the method and synthetic scope stated.
Evidence names resolve under `/tmp/evidenceai-full-audit/`, except sanitized JSON copies
under `docs/evidence/local-full-audit-20261020/`. See the verification report for commands.
The Compose drill uses existing m121 application images; it verifies those images and
monitoring/backup infrastructure, not unbuilt current-source application changes.
Browser fault-injection cases deliberately mock abort/503 responses; successful journeys
use the real API, database, workers and TLS SMTP. External AI was never called.

| Area | Feature | Method | Environment | Expected | Observed | Classification | Evidence |
|---|---|---|---|---|---|---|---|
| Infrastructure | PostgreSQL connectivity and pgvector | runtime_probe + test_database | Disposable PostgreSQL + private synthetic fixtures | PostgreSQL 17.11, pgvector 0.8.7; connect and pool reconnect | PostgreSQL 17.11, pgvector 0.8.7; connect and pool reconnect | PASS | runtime-result.json; backend.log |
| Infrastructure | Migration revision and schema consistency | alembic current/heads/check | Disposable PostgreSQL + private synthetic fixtures | 91e2b6d8c410, one head, no drift | 91e2b6d8c410, one head, no drift | PASS | runtime-result.json; backend.log |
| Infrastructure | Health/readiness and API restart | runtime_probe | Disposable PostgreSQL + private synthetic fixtures | Health/ready 200 before and after own API SIGTERM/restart | Health/ready 200 before and after own API SIGTERM/restart | PASS | runtime-result.json; backend.log |
| Infrastructure | OpenAPI route inventory | app.openapi + served OpenAPI | Disposable PostgreSQL + private synthetic fixtures | 37 registered HTTP operations; see inventory below | 37 registered HTTP operations; see inventory below | PASS | runtime-result.json; backend.log |
| Infrastructure | Validation, safe errors and transactions | test_database, test_auth, test_config | Disposable PostgreSQL + private synthetic fixtures | Reject malformed input without password echo; commits/rollbacks isolated | Reject malformed input without password echo; commits/rollbacks isolated | PASS | runtime-result.json; backend.log |
| Infrastructure | Queue access and worker status | document_worker --status/--once | Disposable PostgreSQL + private synthetic fixtures | Bounded diagnostics and one empty queue tick succeed | Bounded diagnostics and one empty queue tick succeed | PASS | runtime-result.json; backend.log |
| Infrastructure | Worker CLI and graceful shutdown | document_worker process + metrics + SIGTERM | Disposable PostgreSQL + private synthetic fixtures | Heartbeat emitted; process shuts down cleanly | Heartbeat emitted; process shuts down cleanly | PASS | runtime-result.json; backend.log |
| Infrastructure | Readiness when database unavailable | test_observability::test_database_down_readiness | Disposable PostgreSQL + private synthetic fixtures | Safe not-ready response | Safe not-ready response | PASS | runtime-result.json; backend.log |
| Infrastructure | Application configuration/origin guards | test_config, test_auth, test_local_mail | Disposable PostgreSQL + private synthetic fixtures | Unsafe production/test HTTP configurations rejected | Unsafe production/test HTTP configurations rejected | PASS | runtime-result.json; backend.log |
| Authentication | Registration form and input validation | test_auth + browser keyboard journey | Disposable PostgreSQL + private synthetic fixtures | Invalid fields rejected; native keyboard submission supported | Invalid fields rejected; native keyboard submission supported | PASS | backend.log; browser-delivery.log |
| Authentication | Uniform registration acceptance | test_registration_acceptance_does_not_disclose_or_authenticate | Disposable PostgreSQL + private synthetic fixtures | 202 for new/existing identities, no premature login | 202 for new/existing identities, no premature login | PASS | backend.log; browser-delivery.log |
| Authentication | Real SMTP receipt and verified TLS | test_local_mail + E2E_TLS_MAIL fixture | Disposable PostgreSQL + private synthetic fixtures | Real implicit TLS, local CA and hostname validation, decoded proof received | Real implicit TLS, local CA and hostname validation, decoded proof received | PASS | backend.log; browser-delivery.log |
| Authentication | Local verification URL and origin | test_local_mail origin-policy cases | Disposable PostgreSQL + private synthetic fixtures | Exactly http://localhost:3000/verify-email for HTTP development link; trusted origin required | Exactly http://localhost:3000/verify-email for HTTP development link; trusted origin required | PASS | backend.log; browser-delivery.log |
| Authentication | Expiry, browser binding and replay | test_real_tls_signup + test_verification_fails_closed_and_never_reactivates_existing_users | Disposable PostgreSQL + private synthetic fixtures | Expiry/replay/missing browser rejected; requesting browser succeeds | Expiry/replay/missing browser rejected; requesting browser succeeds | PASS | backend.log; browser-delivery.log |
| Authentication | Existing/inactive account protection | test_auth | Disposable PostgreSQL + private synthetic fixtures | No existing password/name/session reset or inactive-account reactivation | No existing password/name/session reset or inactive-account reactivation | PASS | backend.log; browser-delivery.log |
| Authentication | Login and wrong-password rejection | test_auth; browser login | Disposable PostgreSQL + private synthetic fixtures | Correct password authenticates; wrong password generic failure | Correct password authenticates; wrong password generic failure | PASS | backend.log; browser-delivery.log |
| Authentication | Logout, session expiration and token rotation | test_auth; browser expired-session and signout journeys | Disposable PostgreSQL + private synthetic fixtures | Sessions expire/rotate/revoke with login redirects | Sessions expire/rotate/revoke with login redirects | PASS | backend.log; browser-delivery.log |
| Authentication | Cookie security and CSRF | test_auth; real browser context | Disposable PostgreSQL + private synthetic fixtures | HttpOnly/SameSite and production Secure flags; origin/CSRF enforcement | HttpOnly/SameSite and production Secure flags; origin/CSRF enforcement | PASS | backend.log; browser-delivery.log |
| Authentication | Rate limits and shared PostgreSQL budget | test_shared_rate_limit_and_proxy_headers; limiter tests | Disposable PostgreSQL + private synthetic fixtures | Failed login consumes shared budget; window transitions enforced | Failed login consumes shared budget; window transitions enforced | PASS | backend.log; browser-delivery.log |
| Authentication | Unauthorized endpoints and cross-tenant boundaries | test_workspaces, test_documents, test_rag, test_conversations | Disposable PostgreSQL + private synthetic fixtures | Other tenant IDs and unauthenticated requests denied | Other tenant IDs and unauthenticated requests denied | PASS | backend.log; browser-delivery.log |
| Authentication | Password and proof storage | test_auth, test_local_mail | Disposable PostgreSQL + private synthetic fixtures | Argon2id password hashes; only hashed verification/browser proofs in DB | Argon2id password hashes; only hashed verification/browser proofs in DB | PASS | backend.log; browser-delivery.log |
| Authentication | Certificate rejection | test_receiver_rejects_untrusted_ca_and_wrong_hostname | Disposable PostgreSQL + private synthetic fixtures | Untrusted CA and wrong hostname both fail | Untrusted CA and wrong hostname both fail | PASS | backend.log; browser-delivery.log |
| Authentication | Credential URL safety without JavaScript | native-form-proof + browser no-JS regression | Disposable PostgreSQL + private synthetic fixtures | POST, no credential query, response does not echo password | POST, no credential query, response does not echo password | PASS | native-form-proof.json; browser-delivery.log |
| Authentication | Authentication without JavaScript | Implementation inspection | Disposable PostgreSQL + private synthetic fixtures | Client application requires JavaScript | No server-rendered native authentication handler; POST fallback protects URL privacy | NOT APPLICABLE | apps/web/src/components/auth/auth-form.tsx |
| Workspaces | Workspace create/list/read/update | test_workspaces; real browser | Disposable PostgreSQL + private synthetic fixtures | Authorized workspace lifecycle and dashboard navigation | Authorized workspace lifecycle and dashboard navigation | PASS | backend.log; browser-delivery.log |
| Workspaces | Membership add/list/update/remove | test_workspaces; real membership browser journey | Disposable PostgreSQL + private synthetic fixtures | Existing-user membership roles enforced | Existing-user membership roles enforced | PASS | backend.log; browser-delivery.log |
| Workspaces | Owner/admin/member permissions and transfer | test_workspaces + test_workspace_concurrency | Disposable PostgreSQL + private synthetic fixtures | Exactly one matching owner membership; lock-time reauthorization | Exactly one matching owner membership; lock-time reauthorization | PASS | backend.log; browser-delivery.log |
| Workspaces | Eligible workspace deletion | test_workspaces; browser deletion | Disposable PostgreSQL + private synthetic fixtures | Empty eligible workspace removed; nonempty/member constraints return 409 | Empty eligible workspace removed; nonempty/member constraints return 409 | PASS | backend.log; browser-delivery.log |
| Workspaces | Refresh and membership boundaries | browser + independent-connection concurrency tests | Disposable PostgreSQL + private synthetic fixtures | Persistent workspace state; foreign users rejected | Persistent workspace state; foreign users rejected | PASS | backend.log; browser-delivery.log |
| Workspaces | Email invitations / arbitrary workspace archive | Source route inspection | Disposable PostgreSQL + private synthetic fixtures | No pending email-invitation or archive endpoint | Implemented membership operations target existing users; delete is constrained | NOT APPLICABLE | API route inventory |
| Documents | PDF/TXT/Markdown upload and parsing | test_successful_upload_and_background_extraction; PDF/Markdown tests | Disposable PostgreSQL + private synthetic fixtures | Generated fixtures parsed; PDF page and Markdown section provenance retained | Generated fixtures parsed; PDF page and Markdown section provenance retained | PASS | backend.log |
| Documents | File validation, size and parser limits | test_documents validation/limits/PDF tests | Disposable PostgreSQL + private synthetic fixtures | Disallowed/malformed files, traversal and oversized bodies rejected | Disallowed/malformed files, traversal and oversized bodies rejected | PASS | backend.log |
| Documents | Metadata, list pagination and original download | test_documents metadata/download tests | Disposable PostgreSQL + private synthetic fixtures | No private storage keys/text in metadata; authorized original bytes returned | No private storage keys/text in metadata; authorized original bytes returned | PASS | backend.log |
| Documents | Processing transitions and chunks | test_documents; browser worker pipeline | Disposable PostgreSQL + private synthetic fixtures | Pending -> extraction -> completed/indexed; fidelity and chunk provenance retained | Pending -> extraction -> completed/indexed; fidelity and chunk provenance retained | PASS | backend.log |
| Documents | Processing failure, retries/backoff and max attempts | test_documents interrupted/transient/retry tests | Disposable PostgreSQL + private synthetic fixtures | Durable failed/retry states, bounded attempts, idempotent chunks | Durable failed/retry states, bounded attempts, idempotent chunks | PASS | backend.log |
| Documents | Integrity and duplicate behavior | checksum/duplicate/race tests | Disposable PostgreSQL + private synthetic fixtures | Tampering detected; same-workspace duplicate conflicts; cross-workspace allowed | Tampering detected; same-workspace duplicate conflicts; cross-workspace allowed | PASS | backend.log |
| Documents | Delete and cleanup durability | test_documents cleanup/fencing tests | Disposable PostgreSQL + private synthetic fixtures | No late chunks/vectors recreated after deletion; cleanup intents recover | No late chunks/vectors recreated after deletion; cleanup intents recover | PASS | backend.log |
| Documents | Document tenant boundaries | document endpoint permission matrix | Disposable PostgreSQL + private synthetic fixtures | Membership and workspace/document association enforced on all endpoints | Membership and workspace/document association enforced on all endpoints | PASS | backend.log |
| Documents | Concurrent uploads/workers and stale fencing | test_document_concurrency | Disposable PostgreSQL + private synthetic fixtures | One document/job for duplicate race; stale publication cannot win | One document/job for duplicate race; stale publication cannot win | PASS | backend.log |
| Documents | OCR / image-only PDF text recognition | test_empty_and_image_only_pdf_fail_without_ocr | Disposable PostgreSQL + private synthetic fixtures | Image-only PDFs fail safely; OCR absent | No OCR implemented; user must provide text-bearing PDFs | NOT APPLICABLE | backend.log |
| Documents | Arbitrary metadata/file-type list filters | Source list endpoint inspection | Disposable PostgreSQL + private synthetic fixtures | Only supported pagination/UI filtering applies | No general metadata-filter API; search supports document-ID filtering | NOT APPLICABLE | API route inventory |
| Workers | Pending discovery, claim, completion and persistence | document/embedding queue tests; real browser worker | Disposable PostgreSQL + private synthetic fixtures | Durable DB jobs claimed and completed | Durable DB jobs claimed and completed | PASS | backend.log |
| Workers | Interrupted leases and retry recovery | test_interrupted_job_recovery_and_stale_fencing | Disposable PostgreSQL + private synthetic fixtures | Expired lease recovered; stale result fenced | Expired lease recovered; stale result fenced | PASS | backend.log |
| Workers | Duplicate execution and concurrent lock safety | test_document_concurrency + test_embedding_concurrency | Disposable PostgreSQL + private synthetic fixtures | Single valid claim, independent workers/transactions serialize safely | Single valid claim, independent workers/transactions serialize safely | PASS | backend.log |
| Workers | Delete/reindex while provider runs | test_embedding_concurrency | Disposable PostgreSQL + private synthetic fixtures | Stale generations and deleted documents cannot publish vectors | Stale generations and deleted documents cannot publish vectors | PASS | backend.log |
| Workers | Queue recovery after storage/DB failure | document cleanup rollback/backoff tests | Disposable PostgreSQL + private synthetic fixtures | Metadata/job/file rollback and recoverable cleanup; no live object unlinked | Metadata/job/file rollback and recoverable cleanup; no live object unlinked | PASS | backend.log |
| Embeddings/search | Provider selection, deterministic fake vectors, dimensions | test_embeddings | Disposable PostgreSQL + private synthetic fixtures | Disabled/fake/hosted contracts, dimension and nonfinite validation | Disabled/fake/hosted contracts, dimension and nonfinite validation | PASS | backend.log; evaluation-summary.json |
| Embeddings/search | pgvector insertion/profile isolation | test_embeddings; migration check | Disposable PostgreSQL + private synthetic fixtures | Vectors constrained by profile and dimension; no cross-profile mixing | Vectors constrained by profile and dimension; no cross-profile mixing | PASS | backend.log; evaluation-summary.json |
| Embeddings/search | Ranking, Top-K, filters and attribution | retrieval evaluator + test_embeddings | Disposable PostgreSQL + private synthetic fixtures | Gold-label ranking, document filters, workspace isolation | Gold-label ranking, document filters, workspace isolation | PASS | backend.log; evaluation-summary.json |
| Embeddings/search | Empty/unprocessed workspace behavior | test_embeddings/test_rag | Disposable PostgreSQL + private synthetic fixtures | Empty retrieval or insufficient evidence without fabricated answer | Empty retrieval or insufficient evidence without fabricated answer | PASS | backend.log; evaluation-summary.json |
| Embeddings/search | Provider errors and retries | test_embeddings + test_embedding_concurrency | Disposable PostgreSQL + private synthetic fixtures | Safe bounded failure/retry behavior with mock HTTP transport | Safe bounded failure/retry behavior with mock HTTP transport | PASS | backend.log; evaluation-summary.json |
| Embeddings/search | ANN index implementation | Source/migration inspection | Disposable PostgreSQL + private synthetic fixtures | Exact cosine search is intentional | No production HNSW/IVFFlat scalability claim | NOT APPLICABLE | docs/retrieval-engine.md |
| Embeddings/search | Real trained semantic quality / live hosted embeddings | Not authorized live | Disposable PostgreSQL + private synthetic fixtures | Require provider credentials/consent and qualified evaluation | Fake hashing is lexical; no paid provider calls executed | NOT VERIFIED | evaluation-summary.json |
| RAG/conversations | Upload -> chunk -> embed -> retrieve -> answer -> citations | real browser research journey + test_grounded_authenticated_postgres_answer | Disposable PostgreSQL + private synthetic fixtures | Real API, worker, pgvector, deterministic mock answer and mapped source | Real API, worker, pgvector, deterministic mock answer and mapped source | PASS | backend.log; browser-delivery.log; evaluation-summary.json |
| RAG/conversations | Context budgets, citations and evidence boundaries | test_rag context/citation/security tests | Disposable PostgreSQL + private synthetic fixtures | Bounded context; span/mapping validation and authorization rechecks | Bounded context; span/mapping validation and authorization rechecks | PASS | backend.log; browser-delivery.log; evaluation-summary.json |
| RAG/conversations | Unsupported claims and no-evidence responses | test_rag contradiction/abstention/guard tests | Disposable PostgreSQL + private synthetic fixtures | Unsupported output rejected or explicit insufficient-evidence state | Unsupported output rejected or explicit insufficient-evidence state | PASS | backend.log; browser-delivery.log; evaluation-summary.json |
| RAG/conversations | Conversation create/list/read/update/archive/delete | test_conversations; real browser | Disposable PostgreSQL + private synthetic fixtures | Supported conversation lifecycle, persistent history and deleted-source snapshots | Supported conversation lifecycle, persistent history and deleted-source snapshots | PASS | backend.log; browser-delivery.log; evaluation-summary.json |
| RAG/conversations | Multi-turn context and conversation switching | test_conversations; real browser follow-ups/reload | Disposable PostgreSQL + private synthetic fixtures | History stays scoped; follow-ups use prior context | History stays scoped; follow-ups use prior context | PASS | backend.log; browser-delivery.log; evaluation-summary.json |
| RAG/conversations | Concurrent turns and lifecycle changes | test_conversation_concurrency | Disposable PostgreSQL + private synthetic fixtures | Idempotency/pending conflicts and authorization/lifecycle revalidation | Idempotency/pending conflicts and authorization/lifecycle revalidation | PASS | backend.log; browser-delivery.log; evaluation-summary.json |
| RAG/conversations | Provider deadlines and safe errors | test_rag hosted failure/timeout tests | Disposable PostgreSQL + private synthetic fixtures | Mock HTTP contract validates timeout/cancellation/retry boundaries | Mock HTTP contract validates timeout/cancellation/retry boundaries | PASS | backend.log; browser-delivery.log; evaluation-summary.json |
| RAG/conversations | Offline retrieval and answer benchmark | app.evaluate --repeat 3 | Disposable PostgreSQL + private synthetic fixtures | 68 samples; configured thresholds pass | 68 samples; configured thresholds pass | PASS | backend.log; browser-delivery.log; evaluation-summary.json |
| RAG/conversations | Live external LLM correctness and semantic entailment | No live provider calls | Disposable PostgreSQL + private synthetic fixtures | Requires consented corpus/provider and human review | Mock/extractive only; evaluator explicitly reports semantic judgment unverified | NOT VERIFIED | evaluation-summary.json |
| Frontend | Landing/auth/dashboard/routes | Real browser + frontend unit tests | Disposable PostgreSQL + private synthetic fixtures | Public pages render and private routes authenticate | Public pages render and private routes authenticate | PASS | frontend-final.log; browser-delivery.log; final-checks.json |
| Frontend | Workspace/documents/search/research/conversations UI | Real browser journeys | Disposable PostgreSQL + private synthetic fixtures | Backend-connected navigation, uploads, retrieval and persistent cited answers | Backend-connected navigation, uploads, retrieval and persistent cited answers | PASS | frontend-final.log; browser-delivery.log; final-checks.json |
| Frontend | Settings and theme preferences | Browser mobile/theme + component tests | Disposable PostgreSQL + private synthetic fixtures | Supported profile display/theme/connection UI behaves correctly | Supported profile display/theme/connection UI behaves correctly | PASS | frontend-final.log; browser-delivery.log; final-checks.json |
| Frontend | Loading, empty and error states | Frontend component/resource tests; browser error journey | Disposable PostgreSQL + private synthetic fixtures | Recoverable UI for network abort/503; controls reenabled | Recoverable UI for network abort/503; controls reenabled | PASS | frontend-final.log; browser-delivery.log; final-checks.json |
| Frontend | Reload/session expiry and auth redirects | Browser reload and expired-session journeys | Disposable PostgreSQL + private synthetic fixtures | Persistent research then login redirect on expiry/logout | Persistent research then login redirect on expiry/logout | PASS | frontend-final.log; browser-delivery.log; final-checks.json |
| Frontend | Responsive/keyboard/accessibility | Three-engine browser journeys, axe scans | Disposable PostgreSQL + private synthetic fixtures | Representative mobile/desktop and native keyboard flows pass | Representative mobile/desktop and native keyboard flows pass | PASS | frontend-final.log; browser-delivery.log; final-checks.json |
| Frontend | Inert untrusted source/workspace text | Browser HTML payload + test_rag malicious evidence | Disposable PostgreSQL + private synthetic fixtures | Text rendered inert and evidence cannot dictate provider behavior | Text rendered inert and evidence cannot dictate provider behavior | PASS | frontend-final.log; browser-delivery.log; final-checks.json |
| Frontend | Build, lint, TypeScript and unit tests | Frontend commands | Disposable PostgreSQL + private synthetic fixtures | Production test build and static checks succeed | Production test build and static checks succeed | PASS | frontend-final.log; browser-delivery.log; final-checks.json |
| Frontend | All-route console-error audit / long disconnected reconnect soak | Only representative pageerror assertion | Disposable PostgreSQL + private synthetic fixtures | Complete console/network sweep not executed | Browser suite asserts pageerror on representative dashboard; no blanket all-route console guarantee | NOT VERIFIED | browser-delivery.log |
| Security/operations | Ops diagnostics and internal endpoint restrictions | test_observability + isolated smoke | Disposable PostgreSQL + private synthetic fixtures | Operator-only details/metrics; public health/ready bounded | Operator-only details/metrics; public health/ready bounded | PASS | checks.json; monitoring-summary.json; preservation.json; final-integrity.json |
| Security/operations | Prometheus/Grafana provisioning/auth/plugins/private routing | Disposable Compose smoke | Disposable PostgreSQL + private synthetic fixtures | Two targets up; anonymous denied; dashboard/datasource/plugin signatures pass | Two targets up; anonymous denied; dashboard/datasource/plugin signatures pass | PASS | checks.json; monitoring-summary.json; preservation.json; final-integrity.json |
| Security/operations | Encrypted backup/isolated recovery safety | Disposable Compose smoke | Disposable PostgreSQL + private synthetic fixtures | Restore succeeds; nonempty targets and tampered ciphertext rejected | Restore succeeds; nonempty targets and tampered ciphertext rejected | PASS | checks.json; monitoring-summary.json; preservation.json; final-integrity.json |
| Security/operations | CI/CD and secret-scanning fail-closed policy | 11 security regressions + verify_release | Disposable PostgreSQL + private synthetic fixtures | Credential detection retained; gated/manual rollout; release remains blocked | Credential detection retained; gated/manual rollout; release remains blocked | PASS | checks.json; monitoring-summary.json; preservation.json; final-integrity.json |
| Security/operations | Git integrity and historical preservation | git fsck + baseline hashes | Disposable PostgreSQL + private synthetic fixtures | Git integrity passes; prior evidence bytes unchanged | Git integrity passes; prior evidence bytes unchanged | PASS | checks.json; monitoring-summary.json; preservation.json; final-integrity.json |
| Security/operations | Development data/storage preservation | Read-only before/after preservation tooling | Disposable PostgreSQL + private synthetic fixtures | 16 table hashes/counts, revision and private storage content/metadata unchanged | All 16 counts equal; auth_sessions hash changed, other 15 hashes/revision/storage equal; testing stopped | FAIL | checks.json; monitoring-summary.json; preservation.json; final-integrity.json |
| Security/operations | SQL injection resistance, exhaustive penetration coverage | ORM inspection + input/tenant negative tests | Disposable PostgreSQL + private synthetic fixtures | Bounded negative tests only | Parameter binding/validation inspected; no exhaustive SQL injection or security certification claimed | NOT VERIFIED | backend.log |
| Security/operations | Fresh image vulnerability scan / hosted acceptance | Not rerun/externally provisioned | Disposable PostgreSQL + private synthetic fixtures | Existing image and hosted gates must still close | No gate suppression or promotion; release gate freshly returns BLOCKED | NOT VERIFIED | release-gate.log |
| Reliability/performance | Lock contention and concurrent mutation correctness | Workspace/document/embedding/conversation independent DB tests | Disposable PostgreSQL + private synthetic fixtures | Bounded races, rollback and fencing pass | Bounded races, rollback and fencing pass | PASS | backend.log; runtime-result.json |
| Reliability/performance | API/worker restart and connection recovery | Runtime subprocess probes | Disposable PostgreSQL + private synthetic fixtures | Own API restart, worker SIGTERM, pool dispose/reconnect succeed | Own API restart, worker SIGTERM, pool dispose/reconnect succeed | PASS | backend.log; runtime-result.json |
| Reliability/performance | Modest health request latency | 30 requests with concurrency 3 | Disposable PostgreSQL + private synthetic fixtures | No errors; measured scope only | No errors; measured scope only | PASS | backend.log; runtime-result.json |
| Reliability/performance | Concurrent signup/login throughput | Not executed | Disposable PostgreSQL + private synthetic fixtures | Requires dedicated bounded acceptance fixture | No dedicated multi-client throughput benchmark; auth correctness/rate-limit tests are distinct | NOT VERIFIED | runtime-result.json |
| Reliability/performance | Concurrent application search/RAG throughput and queue drain time | Not executed | Disposable PostgreSQL + private synthetic fixtures | Requires dedicated bounded acceptance fixture | Correctness tests run; no full application load/queue-drain benchmark on this checkout | NOT VERIFIED | runtime-result.json |
| Reliability/performance | Memory growth and sustained CPU behavior | Not executed | Disposable PostgreSQL + private synthetic fixtures | Requires dedicated bounded acceptance fixture | One RSS/CPU sample only; not a leak/soak test | NOT VERIFIED | runtime-result.json |
| Reliability/performance | Database server outage/restart and whole-stack persisted recovery | Not executed | Disposable PostgreSQL + private synthetic fixtures | Requires dedicated bounded acceptance fixture | Pool reconnect and lease recovery tested; no current-source database-server kill/restart drill | NOT VERIFIED | runtime-result.json |
| Reliability/performance | Production capacity and hosted failure recovery | Not executed | Disposable PostgreSQL + private synthetic fixtures | Requires dedicated bounded acceptance fixture | Local Mac measurements cannot establish hosted capacity or offsite recovery | NOT VERIFIED | runtime-result.json |

## Complete backend HTTP inventory

OpenAPI contains 37 operations. This inventory identifies registration; PASS coverage
is scoped to the grouped test rows above, not a claim of exhaustive path fuzzing.

| Method | Path |
|---|---|
| GET | `/api/v1/health` |
| POST | `/api/v1/auth/register` |
| POST | `/api/v1/auth/verify-registration` |
| POST | `/api/v1/auth/login` |
| POST | `/api/v1/auth/logout` |
| GET | `/api/v1/auth/me` |
| POST | `/api/v1/workspaces/{workspace_id}/documents/` |
| GET | `/api/v1/workspaces/{workspace_id}/documents/` |
| GET | `/api/v1/workspaces/{workspace_id}/documents/{document_id}` |
| DELETE | `/api/v1/workspaces/{workspace_id}/documents/{document_id}` |
| GET | `/api/v1/workspaces/{workspace_id}/documents/{document_id}/download` |
| POST | `/api/v1/workspaces/{workspace_id}/documents/{document_id}/retry` |
| POST | `/api/v1/workspaces/{workspace_id}/search` |
| GET | `/api/v1/workspaces/{workspace_id}/documents/{document_id}/index` |
| POST | `/api/v1/workspaces/{workspace_id}/documents/{document_id}/index` |
| POST | `/api/v1/workspaces/{workspace_id}/documents/{document_id}/index/retry` |
| POST | `/api/v1/workspaces/{workspace_id}/ask` |
| POST | `/api/v1/workspaces/{workspace_id}/conversations` |
| GET | `/api/v1/workspaces/{workspace_id}/conversations` |
| GET | `/api/v1/workspaces/{workspace_id}/conversations/{conversation_id}` |
| PATCH | `/api/v1/workspaces/{workspace_id}/conversations/{conversation_id}` |
| DELETE | `/api/v1/workspaces/{workspace_id}/conversations/{conversation_id}` |
| GET | `/api/v1/workspaces/{workspace_id}/conversations/{conversation_id}/messages` |
| POST | `/api/v1/workspaces/{workspace_id}/conversations/{conversation_id}/messages` |
| POST | `/api/v1/workspaces/` |
| GET | `/api/v1/workspaces/` |
| GET | `/api/v1/workspaces/{workspace_id}` |
| PATCH | `/api/v1/workspaces/{workspace_id}` |
| DELETE | `/api/v1/workspaces/{workspace_id}` |
| GET | `/api/v1/workspaces/{workspace_id}/members` |
| POST | `/api/v1/workspaces/{workspace_id}/members` |
| PATCH | `/api/v1/workspaces/{workspace_id}/members/{user_id}` |
| DELETE | `/api/v1/workspaces/{workspace_id}/members/{user_id}` |
| POST | `/api/v1/workspaces/{workspace_id}/transfer-ownership` |
| GET | `/api/v1/ready` |
| GET | `/api/v1/ops/readiness` |
| GET | `/api/v1/ops/metrics` |

OpenAPI/docs infrastructure routes also include `/openapi.json`, `/docs`,
`/docs/oauth2-redirect`, and `/redoc` (FastAPI defaults, outside the 37 business/ops operations).

## Complete frontend page inventory

- `/`
- `/verify-email`
- `/register`
- `/login`
- `/settings`
- `/workspaces`
- `/workspaces/[workspaceId]`
- `/workspaces/[workspaceId]/research`
- `/workspaces/[workspaceId]/search`
- `/workspaces/[workspaceId]/conversations`
- `/workspaces/[workspaceId]/members`
- `/workspaces/[workspaceId]/documents`
- `/workspaces/[workspaceId]/conversations/[conversationId]`

`error.tsx`, `not-found.tsx`, shared/private/workspace layouts and loading/error
components accompany these pages; there is no frontend API proxy route.

## Worker/operational entry points

- `python -m app.document_worker` (durable cleanup, document and embedding ticks).
- `python -m app.document_worker --once` / `--status` / `--metrics-file <private path>`.
- `python -m app.operations` (bounded read-only diagnostics).
- `python -m app.evaluate`, `app.evaluate_retrieval`, `app.evaluate_rag` (guarded offline evaluation).
- `infra/development/mail.py init/serve/api/view` (local-only TLS mail tooling).
- Docker entry points, backup/restore and monitoring jobs are described in deployment
  documentation; no hosted scheduler or production rollout was exercised.
