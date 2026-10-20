# Local full-system audit

Audit: 2026-10-20, Asia/Dubai. Discovery branch `main`, commit
`c0103321e041f31605a0ffd4c43e065bc0116381`, plus the pre-existing uncommitted
GitHub-hardening and local-mail work at discovery. During the audit HEAD advanced to
`a12b93d5a6802572a21089abb99de154d9056313` (`a12b93d`, prior local-mail/security checkpoint).
This audit executed no commit/push or repository-setting mutation; attribution of
the concurrent commit is NOT VERIFIED. Prior source/evidence byte comparisons remain valid.

## Executive assessment

The implemented offline research pipeline works in the isolated current-source stack:
real signup, verified TLS SMTP receipt, browser-bound verification, login, workspace
management, synthetic upload, durable workers, pgvector retrieval, deterministic
answers, citations and conversation persistence. Fresh final runs passed **676 backend,
55 frontend and 21 three-engine browser tests**, plus 11 security regressions and a
68-sample offline evaluation. Lint, TypeScript, build and Git integrity passed.

**This is not an unqualified all-clear. Data preservation FAILED.** The final comparison
found a changed `auth_sessions` table hash with **zero row-count change**. All 16 table
counts stayed equal; the other 15 table hashes, migration revision and private storage
content/metadata stayed equal. Testing stopped when this was found. No records were
reset, restored, deleted or edited to make the check pass. There is no evidence of
new test-user/document/intent rows in development, but full byte equality is not met.

The baseline stores table hashes/counts, not before-images for individual session
columns. It cannot identify the changed column, row or writer. The source's normal
authenticated-request path commits `last_used_at`; an existing user's active browser
and development reloads are plausible causes, **not established attribution**. The
unauthenticated audit probe of `/auth/me` returned 401 and supplied no user cookies.
All automated mutations used owned disposable databases. Do not label this mismatch
harmless or repair it automatically. Historical attribution also remains NOT VERIFIED.

| Decision | Result | Scope |
|---|---|---|
| Local development functionality | **PARTIAL** | Offline implemented flows pass; preservation gate fails and live configuration/provider limits remain |
| Real integrated end-to-end verification | **PASS** | Current-source browser/API/worker/DB/real TLS mail; deterministic AI only |
| Database/data preservation | **FAIL** | auth_sessions hash differs, row count unchanged |
| Production readiness | **BLOCKED** | Existing container, AI, CI/CD and hosted gates remain unmet |

## Environment and isolation

macOS 26.5.1 arm64, Python 3.14.6, Node v26.0.0. Development PostgreSQL is
17.11 (Debian) with pgvector 0.8.7 at 127.0.0.1:5433, revision `91e2b6d8c410`.
Private documents remain under the configured `storage/documents`; only the
preservation tool hashed them. No document bodies were inspected for this audit.

At discovery, `infra-db-1`, API PID 30486 on 127.0.0.1:8000, mail PID 30285 on
127.0.0.1:1465 and Next.js on port 3000 were running. The development frontend listens
on wildcard addresses; it was not stopped or rebound. Use `npm --prefix apps/web run
dev -- --hostname 127.0.0.1` at the owner's next restart. LAN/firewall exposure was not
probed. No separate existing document-worker process was identified in the inventory.

The `.env` settings disable embeddings, LLM and email delivery by default. The mail
launcher uses process overrides, so `.env` alone does not describe the live API's
SMTP settings. No provider secrets or process environment dumps were printed. No
real external AI requests were made. Real semantic/trained embedding and live LLM
quality remain NOT VERIFIED. A disabled provider/absent worker is a prerequisite for
normal local AI workflows, not evidence of a product parsing defect.

Every mutating test command used `run_isolated.py`: owned image
`sha256:633cb956dc3fa6e5930312667aec5e02264c56a59556d783de19236e8df0d6b5`,
unique loopback database, ownership labels and tmpfs, with no development volume or
private-storage mounts. Browser tests used a generated `e2e_web_*` schema and private
temporary document/mail directories. API :18000, frontend :3100 and ephemeral SMTP
ports did not replace the user's services. Runtime probes used :18001 and another
owned database. Runner receipts show empty public baselines, zero scratch schemas
and owned-container removal. Final Docker/listener inventory found no audit containers
or :18000/:18001/:3100 listeners; an empty `lsof` result exits 1 by convention.

The successful browser journey uses real API requests and worker ticks. Only deliberate
network/provider failure scenarios inject abort/503 responses. Embeddings/answers are
fake/mock, never paid services. The E2E helper consumes proof decoded from a real TLS
receipt and enters it on the separate :3100 verification page. Its test-only approved
HTTPS email origin is not deployed; it does not claim clicking the unmodified emailed
URL to :3100. The exact local :3000 HTTP email origin is independently covered by the
backend mail tests. Browser email-link privacy/binding controls remain in force.

## Defect register

| ID / severity | Reproduction and root cause | Correction and regression | Current result |
|---|---|---|---|
| AUD-01 / high | Run Playwright while normal Next.js dev is active. Both use `.next`; a development compile removes production chunks. Captured WebKit `Loading chunk 177 failed`; first run 12 passed / 6 failed. | Conditional `.next-e2e` for build/start, Git/ESLint generated-output exclusions and generated TypeScript include paths; two config regressions. The same active dev server stayed running during the corrected three-engine run. | FIXED: all original 18 flows and final 21 cases passed |
| AUD-02 / high | Auth/verification forms omit method. With hydration unavailable the browser defaults to GET. Intercepted synthetic reproduction confirmed a password query key without sending it to a real server. | Explicit POST on both forms. Browser tests disable JavaScript and verify POST, empty query and no password echo on register/login/verify pages. Hydrated logic unchanged. | FIXED: regression passes on all three engines; Next.js renders the POST page with 200 and does not authenticate |
| AUD-03 / medium | Authenticated failure traces can retain cookies/proofs; explicit screenshots wrote fixed shared `/tmp` files. | Disable trace/automatic screenshot capture and remove fixed screenshot writes. Keep real mail in owned private fixture directories. | CORRECTED by configuration/source inspection; no claim of general third-party runner artifact sanitization |
| AUD-04 / preservation gate | Compare development baseline after tests: auth_sessions hash changed with count delta 0. | STOPPED testing; preserved mismatch, no application-data cleanup. Column/writer cannot be reconstructed from aggregate baseline. | OPEN: preservation FAIL, attribution NOT VERIFIED |
| ENV-01 / local exposure | Existing development Next.js process listens on wildcard port 3000. | Preserve running process; recommend explicit loopback on next owner-controlled restart. | OPEN: external reachability NOT VERIFIED; API/SMTP/DB are loopback |

Two harness mistakes were corrected without application changes: a temporary helper
named `inspect.py` shadowed Python's stdlib module; its filename was changed. Runtime
storage needed canonicalization through macOS symlinks; the storage guard correctly
refused the noncanonical path. Uvicorn re-raises SIGTERM after graceful shutdown, so
that expected signal status was accepted. An intermediate new no-JS regression
incorrectly expected 405; this Next.js version returns a safe rendered 200 instead.
Generated E2E output also needed an ESLint exclusion. Final static checks passed after
that correction. Initial failures remain recorded; no thresholds were reduced.

## Monitoring and evaluation limits

A fresh disposable Compose drill verified Grafana 13.2.4 authentication, disabled
anonymous/signup access, dashboards, Prometheus datasource, two live targets, 13 bundled
signed plugins and private monitoring routes. Encrypted synthetic backup restoration,
nonempty-target rejection and ciphertext-tamper rejection passed. It used existing
m121 API/web/worker images; those results do not certify a build of the changed checkout.
No candidate was promoted. Selected Grafana digest is recorded in the evidence summary.

Offline evaluation passed its configured thresholds: recall/precision 0.9375 for both
128/256 dimensions, MRR 1.0, NDCG 0.9516433991, workspace/document filter correctness
1.0; answer correctness 0.9444444444, citation validity/gold support 1.0, unsupported
claims 0.0. These are not perfect benchmark accuracy or proof of semantic entailment.
No human semantic judgment, real hosted provider or production capacity was validated.

Correctness races/lease recovery were executed by the backend suite. A 30-request,
concurrency-3 health probe measured median 0.578 ms, maximum 1.876 ms, zero errors.
A single API resource sample was RSS 111872 KiB and CPU 56.7%; startup-biased, not
memory-growth/CPU-soak evidence. Full current-source application throughput, queue-drain
latency, real DB-server restart and sustained memory/CPU behavior are NOT VERIFIED.

## Next actions and approval boundaries

1. Owner review of the session-hash mismatch; retain the private snapshot and current
   records. Any user-data repair/cleanup requires separate approval. A future controlled
   preservation run needs a quiescent owner-approved window; do not silently ignore
   session timestamps or weaken the equality check.
2. Run the normal local worker and explicitly select fake/mock providers if offline AI
   is desired. Do not activate paid providers without privacy/cost authorization.
3. Bind the existing frontend to loopback at the next owner-controlled restart.
4. Complete bounded workload/soak and consented semantic evaluation separately.
5. Close existing container vulnerabilities, GitHub protection/CI exact-SHA acceptance,
   and hosted DNS/TLS/SMTP/offsite recovery gates before production. No fresh image scan
   or external GitHub settings change was performed here.

See [verification](local-full-system-audit-verification.md), the
[87-row matrix and complete route inventory](local-functional-test-matrix.md), and
[sanitized summary](evidence/local-full-audit-20261020/summary.json). Raw private
logs/snapshots live outside Git at `/tmp/evidenceai-full-audit/`; this is not durable
offline incident-evidence custody. Historical evidence under `docs/evidence` was not
modified; the new evidence directory is separate.
