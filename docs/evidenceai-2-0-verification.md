# EvidenceAI 2.0 verification — 2026-10-21 (Asia/Dubai)

This is a local incremental upgrade at baseline
`ef91f507146e02b15eb81f50f2aa9043f350cbad`. No commit/push/history rewrite,
deployment, paid operation, live Gemini request or GitHub-setting change was made.
The backend `.env`, development records and original files were not intentionally
written. A strict first preservation window nevertheless detected a session timestamp
change, documented below; do not replace that observation with an unconditional
"development data unchanged" assertion.

## Implementation and scope

Existing authentication, workspaces, private storage, original document lifecycle,
queue fencing, default search/question behavior, exact citation validation, offline
providers and release gates remain. Additions are:

- Distinct active-profile indexing and research readiness, authenticated workspace counts
  and safe provider consent/configuration status; no hidden remote health probe.
- Authorized paged/searchable extracted chunk previews with source spans and inert rendering.
- Bounded ranked-search offset pagination and stable ordering.
- Topic-based extractive briefs and two-source comparisons, per-source retrieval,
  context interleaving and mandatory citation coverage of both comparison sources.
- Default conversation request fingerprint compatibility, saved citation history retained.
- Provider labeling, actionable quota/consent messages, file-count upload progress,
  side-by-side source quotations and explicit local plain-text evidence export.
- Optional PDF text layout and Markdown Setext headings for future extraction jobs only.
- Separate default-off Gemini live-request and private-content authorizations, rechecked
  before transport. The synthetic-only internal probe cannot bypass the live master gate.

No schema migration, OCR engine, hybrid ranking, autonomous agent, external connector,
semantic entailment judge or private-document provider transfer was added. Abstractive
synthesis, translation quality, structured table cells and source credibility are not
represented as verified features. See the architecture/design documents for boundaries.

## Offline results

| Check | Result |
|---|---|
| Final full backend suite | PASS: 746 tests, 30.51s; one existing Starlette/httpx deprecation warning |
| Full frontend suite | PASS: 63 tests / six files, 2.22s in the controlled repeat |
| Browser suite / production-mode frontend build | PASS: 24 tests, 1.8m; Chromium, Firefox, WebKit; real local validated TLS SMTP |
| Security regressions | PASS: 11 tests, 8.548s |
| Isolated-runner unit checks | PASS: 3 tests, 0.374s |
| Frontend ESLint / TypeScript | PASS after correcting render-time ref access in pagination |
| Offline evaluation | PASS: 36 samples, zero threshold failures |
| Disposable migration drift | PASS: no new upgrade operations detected |
| First development preservation window | FAIL: one last_used_at column; remaining data/storage matched |
| Second controlled preservation window | PASS: all 16 tables, all session columns, schema revision and storage matched |
| Live Gemini / free tier / real multilingual semantic quality | NOT VERIFIED; no authorization, no provider calls |
| Existing production release gate | Expected exit 1 / BLOCKED |

The full backend command is:

```sh
apps/api/.venv/bin/python infra/testing/run_isolated.py \
  --evidence-directory /tmp/evidenceai-20-final-backend -- \
  apps/api/.venv/bin/python -m pytest apps/api/tests -q --tb=short --show-capture=no
```

Frontend and security:

```sh
npm --prefix apps/web test
npm --prefix apps/web run lint
# From apps/web:
./node_modules/.bin/tsc --noEmit
# From repository root:
python3 -m unittest discover -s infra/security/tests -v
apps/api/.venv/bin/python -m unittest discover -s infra/testing -p 'test_*.py' -v
```

The browser command uses the existing installed cache, not a download:

```sh
EVIDENCEAI_E2E_TLS_MAIL=1 PLAYWRIGHT_BROWSERS_PATH=/tmp/evidenceai-m126-browsers \
  apps/api/.venv/bin/python infra/testing/run_isolated.py \
  --evidence-directory "$PRIVATE_CASE/browser-final" -- npm --prefix apps/web run test:e2e
```

`PRIVATE_CASE` is the restricted case directory referenced by
`/tmp/evidenceai-20-location.txt`; logs/snapshots/keys are not publication artifacts.
Playwright builds Next.js in production mode to the isolated `.next-e2e` directory,
starts only fixture-owned API/frontend ports 18000/3100, never reuses existing servers,
and cleans scratch schema/temp storage on shutdown. All external HTTP transports are
blocked by fixtures. The original-development frontend output is not rebuilt over.

Migration drift uses another runner-owned empty database:

```sh
apps/api/.venv/bin/python infra/testing/run_isolated.py \
  --evidence-directory "$PRIVATE_CASE/quiescent-verification/migration" -- \
  apps/api/.venv/bin/python -m alembic -c apps/api/alembic.ini check
```

Every completed database-backed runner receipt (including failed attempts) confirms
zero leftover test schemas/public users/registration intents/limiter rows and owned
container removal. The reviewed immutable local database image ID remains
`sha256:633cb956dc3fa6e5930312667aec5e02264c56a59556d783de19236e8df0d6b5`.
No development Docker volume is mounted or deleted.

## Initial failures retained and corrected

The first focused 2.0 suite registered imported fixtures incompletely: 53 pass / six
fixture errors. A rerun had 58 pass / one incorrect helper-call signature. Both were
corrected in the new tests; subsequent complete backend suites passed. No product
authentication policy was changed to satisfy tests.

The first lint run rejected reading a ref during render in the new pagination UI.
Rendered page-size state now uses React state; event-handler search snapshots still
retain the submitted query/filter scope. ESLint and TypeScript subsequently passed.

The first browser attempt used the default cache, which lacked Firefox/WebKit:
eight Chromium cases passed and 16 could not launch. The exact existing three-engine
cache was selected and the full 24 passed. The first isolated-runner unit attempt used
system Python without SQLAlchemy; rerunning the documented API virtualenv passed all
three. These environment/test-harness failures are not hidden as product passes.

## Preservation evidence and limits

The owner requested a quiet window. Before/after snapshots used read-only REPEATABLE
READ transactions, server-side aggregate hashes of all 16 development tables, HMAC
session-column fingerprints, schema revision and private-storage content/metadata
hashes. They contain no raw credentials or document text in publication output and
remain restricted outside Git. Original snapshots are not overwritten.

First window: 2026-10-20 21:24:59–21:31:25 UTC (2026-10-21 01:24:59–01:31:25 Dubai).
One existing auth_sessions row changed only last_used_at, with no added/removed row.
Other session columns, all other 15 tables, revision, transaction settings and private
storage content/recorded metadata matched. The observed value was 35.734 seconds after
the window start; the first disposable test evidence directory was created at +76.488s.
That narrows timing to before the first test environment was created; it does not
identify the writer or prove every possible cause.

Accessible process inspection showed current Chrome and VS Code connections to local
frontend port 3000, with development API/frontend listeners still running. Current
connections do not prove historical activity. No regular application log files were
available from those listeners, and a system-wide process inspection was denied by
macOS; the narrower accessible-process review succeeded. Writer attribution remains
**NOT VERIFIED**. Normal authenticated requests can update last_used_at; no session
behavior was changed, ignored or repaired to manufacture preservation equality.

The first FAIL, row/column fingerprints and activity review remain intact in restricted
custody. The owner subsequently confirmed embedded previews closed and approved a
second controlled repeat. That result is appended below; it does not retroactively
convert the first window or historical audit into a PASS.

## Evaluation and production decision

Fresh offline fake/mock metrics: recall/precision .9375, MRR 1.0, NDCG .9516433991,
citation reference/gold support 1.0, unsupported-claim frequency 0, answer correctness
.9444444444. Sequential median latency: retrieval128 3.32625ms, retrieval256 3.44545ms,
RAG 13.71015ms. Sample counts are too small for p95/p99. These are not Gemini, paid API,
production throughput or semantic truth measurements.

`python3 infra/scripts/verify_release.py docs/evidence/m126/release-result.json`
returns exit 1 with container_security, ai_security, ci_cd and production_environment
unmet. No release evidence or security threshold was changed. Production remains
**FAIL / BLOCKED**. Current model access/free tier, private transfer consent and live
acceptance remain **NOT VERIFIED / NOT AUTHORIZED**. No new approval is inferred from
successful offline fixtures. The prepared future approval request, exact synthetic
inputs/budget/endpoints and startup commands are in [local-gemini-setup.md](local-gemini-setup.md).


## Approved second controlled window

After embedded previews were closed, the owner authorized a complete repeat.
Window: **2026-10-20 21:35:40.817661–21:38:03.287815 UTC**
(**2026-10-21 01:35:40–01:38:03 Dubai**).
All 16 table hashes/counts and every session-column fingerprint matched; zero session
rows added/removed/changed. Revision, transaction context, private-storage content and
recorded metadata matched. **Controlled preservation PASS**. The original FAIL and
unverified writer attribution remain unchanged. The user was told the window ended
and normal development use could resume; no services or sessions were terminated.

The same isolated commands were repeated under `$PRIVATE_CASE/quiescent-verification/`
with separate `backend`, `browser`, `evaluation` and `migration` evidence directories.
Backend: 745 pass in 33.62s; frontend: 63 pass in 2.22s; browsers: 24 pass in 1.8m;
evaluation: 36 samples, zero threshold failures; Alembic check: no new upgrade operations.
All four database-backed receipts report clean isolation, zero leftovers and owned
container removal. The frontend test command runs without a development API.

Final code review additionally identified the configured one-passage comparison edge:
a two-source comparison must not exceed a server retrieval cap of one. It now abstains
before query/provider I/O when fewer than two passages are allowed, and avoids a second
query if the overall deadline is exhausted. This post-window guard is covered by a
separate final complete disposable backend run, recorded below. No development API,
data or storage was accessed by that additional test run, and no later development
preservation equality is inferred after the quiet window ended.


## Final static checks and publication scope

Final comparison-budget guard verification: **746 backend tests PASS in 30.51s**,
with the same one existing deprecation warning and clean/removed disposable container.
Command: the documented full backend invocation with evidence directory
`/tmp/evidenceai-20-budget-final-backend`. This was after the approved preservation
window; no later development-data comparison is claimed.

Secret gate: `python3 infra/security/scan_secrets.py --private-directory "$PRIVATE_CASE/secret-gate"`
PASS, zero unreviewed findings, 320 existing exact adjudications. Unsuppressed scans
retain history/current/archive counts 134/134/52; no blanket exclusion or policy change.
The final tree, including the sanitized aggregate artifact, is also scanned into a
fresh `secret-gate-final` private directory. Raw scanner output stays outside Git.

`git diff --check`, TypeScript and ESLint PASS. Original historical documentation,
evidence, publication-review derivatives, workflows, secret/security policy, release
validator and isolation infrastructure are hash-checked against the private pre-work
manifest. The original staged patch and HEAD remain unchanged; no staging/commit/push
operation was made. Only the current Gemini setup guide was intentionally updated to
point to the new stricter consent controls. Sanitized aggregate evidence is at
`docs/evidence/evidenceai-2-0/verification.json`; it contains no raw private row IDs,
session fingerprints, emails, document text, keys or workstation account paths.

Final local offline functionality: **PASS**. Controlled repeat preservation: **PASS**.
First-window preservation: **FAIL retained**. Historical/current-window writer
attribution: **NOT VERIFIED**. Live Gemini and free tier: **NOT AUTHORIZED / NOT VERIFIED**.
Formal production release: **FAIL / BLOCKED**.

## Exact files changed in this increment

This list compares file bytes with the captured pre-2.0 working tree, including the
prior uncommitted Gemini work. Pre-existing staged audit changes are not counted as
new work unless this increment further changed that working file.

- `README.md`
- `apps/api/.env.example`
- `apps/api/app/api/routes/documents.py`
- `apps/api/app/api/routes/search.py`
- `apps/api/app/core/config.py`
- `apps/api/app/gemini_probe.py`
- `apps/api/app/schemas/ask.py`
- `apps/api/app/schemas/document.py`
- `apps/api/app/schemas/search.py`
- `apps/api/app/services/conversation_service.py`
- `apps/api/app/services/document_chunking.py`
- `apps/api/app/services/document_parser_child.py`
- `apps/api/app/services/document_parsing.py`
- `apps/api/app/services/document_service.py`
- `apps/api/app/services/embedding_jobs.py`
- `apps/api/app/services/gemini_providers.py`
- `apps/api/app/services/llm_providers.py`
- `apps/api/app/services/rag_context.py`
- `apps/api/app/services/rag_service.py`
- `apps/api/app/services/research_readiness.py`
- `apps/api/app/services/search_service.py`
- `apps/api/tests/conftest.py`
- `apps/api/tests/test_gemini.py`
- `apps/api/tests/test_research_platform.py`
- `apps/web/e2e/research.spec.ts`
- `apps/web/e2e/server.py`
- `apps/web/src/app/globals.css`
- `apps/web/src/components/chat/provider-status.tsx`
- `apps/web/src/components/chat/research.tsx`
- `apps/web/src/components/chat/search.tsx`
- `apps/web/src/components/citations/answer.tsx`
- `apps/web/src/components/documents/library.tsx`
- `apps/web/src/components/documents/preview.tsx`
- `apps/web/src/components/workspaces/dashboard.tsx`
- `apps/web/src/lib/api/client.ts`
- `apps/web/src/lib/research-report.ts`
- `apps/web/src/test/application.test.tsx`
- `apps/web/src/types/api.ts`
- `docs/ai-evaluation-and-benchmarks.md`
- `docs/document-intelligence-design.md`
- `docs/evidence/evidenceai-2-0/verification.json`
- `docs/evidenceai-2-0-architecture.md`
- `docs/evidenceai-2-0-verification.md`
- `docs/gemini-integration.md`
- `docs/gemini-provider-integration.md`
- `docs/local-gemini-setup.md`
- `docs/research-and-citation-validation.md`
