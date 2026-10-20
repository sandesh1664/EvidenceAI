> Sanitized publication derivative. Original evidence remains unchanged.
> Set PROJECT_ROOT to your local checkout before using command examples.
> Only workstation-specific paths were anonymized; original results and limitations are retained.

# Local audit preservation verification — 12.9

Date: 2026-10-20 (Asia/Dubai). HEAD/main:
`a12b93d5a6802572a21089abb99de154d9056313` throughout. Existing audit changes were
preserved. Original audit findings and evidence were not edited or replaced.

## Private evidence location

`/tmp/evidenceai-129-location.txt` (mode 0600) identifies the new owned mode-0700 case
directory. The current case is under macOS TMPDIR. No raw row images or session values
are published. Keyed fingerprints and private keys never enter Git.

The case directory contains `custody.json`, original-evidence assessment, database
context, current-initial and controlled before/after snapshots, the comparison key,
`controlled-result.json`, backend/frontend/browser logs, runner receipts and final
custody verification. Existing snapshots are not overwritten. The old full-audit
before file and its failure summary remain at their original paths.

## Scope and commands

Commands below show the actual command forms; `E129_DIR` denotes the private case
path from the pointer. Reusing an existing output path intentionally fails rather
than overwriting evidence. For a future case create a new owned mode-0700 directory
and key, and get a new consented quiescent window.

```sh
cd "${PROJECT_ROOT}"
E129_DIR="$(cat /tmp/evidenceai-129-location.txt)"
# These creation commands already ran; do not rerun over their existing paths.
PYTHONPATH=apps/api apps/api/.venv/bin/python infra/testing/session_preservation.py --key "$E129_DIR/comparison.key" --init-key
PYTHONPATH=apps/api apps/api/.venv/bin/python infra/testing/session_preservation.py --key "$E129_DIR/comparison.key" --snapshot "$E129_DIR/current-initial.json"
PYTHONPATH=apps/api apps/api/.venv/bin/python infra/testing/session_preservation.py --key "$E129_DIR/comparison.key" --snapshot "$E129_DIR/controlled-before.json"
```

Snapshots use read-only/repeatable-read transactions; no private document files were
opened. Strict server-side table serialization matched the 15 unchanged historical
aggregate hashes. Original-to-current comparison still showed only `auth_sessions`
hash different, count delta 0. No historical column/writer recovery was possible from
the retained aggregate baseline.

Read-only PostgreSQL metadata established current logging/transaction settings,
zero custom auth-session triggers/rules, zero pg_cron/pgagent extensions and zero
matching test schemas. It did not enable logging or inspect raw WAL/private files.

## Safe defect reproduction and fix

```sh
npm --prefix apps/web test -- --run src/test/network-isolation.test.ts
```

Before adding the shared fetch guard: **exit 1**, one failed/one passed. A newly
created synthetic loopback HTTP server received one unmocked request (expected zero).
This did not contact the development API or require a real cookie. Log:
`frontend-network-before.log`. The later full frontend run proves receiver count zero
with the guard and permits explicitly mocked responses.

Changed source: `apps/web/src/test/setup.ts` only for the test-network fix. No normal
authentication code or production client default was changed.

## Fresh regression and integration results

```sh
apps/api/.venv/bin/python infra/testing/run_isolated.py --evidence-directory "$E129_DIR/backend-isolation" -- apps/api/.venv/bin/python -m pytest apps/api/tests -q
npm --prefix apps/web test -- --run
npm --prefix apps/web run lint
apps/web/node_modules/.bin/tsc --noEmit --project apps/web/tsconfig.json
EVIDENCEAI_E2E_TLS_MAIL=1 PLAYWRIGHT_BROWSERS_PATH=/tmp/evidenceai-m126-browsers apps/api/.venv/bin/python infra/testing/run_isolated.py --evidence-directory "$E129_DIR/browser-isolation" -- npm --prefix apps/web run test:e2e
PYTHONPATH=infra/testing apps/api/.venv/bin/python -m unittest test_run_isolated -v
```

| Check | Actual result |
|---|---|
| Full backend | **682 passed**, 0 failed, one existing Starlette/httpx deprecation warning, **32.96s**, exit 0 |
| New backend regressions | Six cases: real authenticated touch changes only last_used_at; unauthenticated GET does not touch; revocation/add/delete detection; fingerprint privacy/key separation; mismatched-context refusal; exclusive/private/symlink-safe evidence |
| Frontend | **57 passed**, 6 files, **2.03s**, exit 0 |
| New frontend regression | Synthetic receiver receives zero unmocked requests after fix; explicit mock accepted |
| Lint | Exit 0, 2.461s wrapper |
| TypeScript | Exit 0, 0.744s wrapper |
| Integrated browsers + build | **21 passed (1.2m)**, Chromium/Firefox/WebKit, exit 0; separate production build succeeds |
| Runner import/fail-closed regressions | **3 passed**, 0.322s, exit 0 |

The real-auth reproduction uses only synthetic users/cookies in the disposable schema.
The comparison correctly returns FAIL for last_used_at; no ignore rule was introduced.
All session columns remain fingerprinted and all table hashes remain strict.

Browser tests use the existing isolated API/worker/schema, `.next-e2e`, fresh browser
contexts and real TLS SMTP receipt adapter. The normal local API is not a browser test
target. Deliberate network-failure cases still inject abort/503; deterministic embeddings
and mock answers are not live external AI verification. TLS/hostname checks stay enabled.
No development cookie jar or private document was used. Component tests now default to
denying unmocked fetch. Other network transports are outside this specific guard.

The runner resolved local image
`sha256:633cb956dc3fa6e5930312667aec5e02264c56a59556d783de19236e8df0d6b5`.
Both new runner receipts record `isolation_clean=true`, zero remaining scratch schemas,
zero public users/intents/limiter rows and `owned_container_removed=true`. Labels,
tmpfs, loopback ports, URL guards and cleanup protections were unchanged.

## Controlled development comparison

The owner explicitly confirmed: tabs closed/no activity during verification. No session
was deleted/revoked, auth behavior modified, database locked or user service stopped
by this investigation. A listener inventory later found only development PostgreSQL
among ports 3000/8000/1465/5433; do not infer who stopped any other process.

```sh
PYTHONPATH=apps/api apps/api/.venv/bin/python infra/testing/session_preservation.py --key "$E129_DIR/comparison.key" --compare "$E129_DIR/controlled-before.json" --after "$E129_DIR/controlled-after.json" --report "$E129_DIR/controlled-result.json"
```

**Exit 0 / PASS**, client capture window 16:28:40.732151–16:30:45.594168 UTC
(20:28:40–20:30:45 Asia/Dubai):

- All **16** database table counts and hashes equal.
- `changed_tables={}`, `changed_sessions=[]`.
- Zero sessions added, removed or changed; no column exemptions.
- Migration revision `91e2b6d8c410` and transaction context equal.
- Development test-schema count zero before and after.
- Private storage **NOT VERIFIED this run** because private files were not opened.
- Original full-audit preservation result still **FAIL**; its writer/changed column
  remain **NOT VERIFIED**. A new PASS cannot establish historical causality.

After cleanup, label-filtered Docker inventory found no disposable-test containers;
no :18000/:3100 listeners remained. Empty lsof inventory exits 1 by convention, not
because cleanup failed. The consented quiet window ended after this comparison.

## Custody, static review and release protections

Final byte comparisons: **379** pre-existing repository evidence/report files and the
original private preservation inputs unchanged. HEAD unchanged. New files are outside
the historical evidence directory; no prior report was amended. Snapshots/reports
and the comparison key use exclusive mode-0600 creation under an owned mode-0700
case directory. The private temporary location is not a durable encrypted archive.

`git diff --check` and new-file whitespace checks passed. The existing release input
was revalidated:

```sh
apps/api/.venv/bin/python infra/scripts/verify_release.py docs/evidence/m126/release-result.json
```

**Exit 1 / BLOCKED** as required: unmet `container_security`, `ai_security`, `ci_cd`,
`production_environment`. No severity suppression, gate waiver, image promotion,
GitHub setting mutation, paid provider call or deployment occurred. The prior 68-case
AI evaluation and 11 security regressions were not represented as fresh 12.9 runs.

## Exact files changed in this investigation

- `infra/testing/session_preservation.py` — new DB-only, keyed row/column evidence tool.
- `apps/api/tests/test_session_preservation.py` — six disposable/privacy regressions.
- `apps/web/src/test/setup.ts` — default deny unmocked fetch.
- `apps/web/src/test/network-isolation.test.ts` — receiver-based denial regression.
- `docs/local-audit-preservation-investigation.md`.
- `docs/local-audit-preservation-verification.md`.

Pre-existing full-audit changes remain in the working tree and are not new 12.9 edits.

Final verdict: **tested offline local functionality PASS; new controlled database
preservation PASS; historical changed column/writer NOT VERIFIED; production BLOCKED**.
No claim of historical data restoration or fresh private-storage verification.
