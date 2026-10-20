# GitHub security hardening 12.8 — verification

2026-10-20, Asia/Dubai. Baseline and current HEAD `c0103321e041`; initially clean.
**Production FAIL / BLOCKED.** Local proposed hardening is uncommitted/unpushed;
no hosted workflow with this patch was run. Raw reports and request receipts are
restricted under the new `/tmp/evidenceai-m128-*` incident directory; the local
pointer `/tmp/evidenceai-m128-location.txt` identifies it. No restricted 12.7
report/API response was copied into Git.

## Commands and actual results

| Check / command | Result |
| --- | --- |
| `git status --short`; `git rev-parse HEAD` |Clean start; exact requested baseline; HEAD unchanged |
| Baseline `gitleaks git --no-banner --no-color --log-opts=HEAD --report-format=json --report-path=<private>/baseline-history.json .` |Exit 1; 66 findings; exact full-coordinate/value reconciliation with retained private scan |
| Independent proof recomputation |27 public module/version checksum records match retained, hash-verified response bytes; 7 target Git-file hashes recomputed; 2 public source identities and 2 narrative contexts checked |
| `python3 -m unittest discover -s infra/security/tests -v` |11 tests PASS; final completed regression run 11.218 seconds |
| `python3 infra/security/scan_secrets.py --private-directory <new-private-directory>` |Exit 0 / PASS; 0 unreviewed, 320 exact adjudications; raw history 134/current 134/historical archives 52, each scanner exit 1 |
| `python3 infra/security/scan_secrets.py --audit-only --private-directory <different-new-private-directory>` |Exit 1 intentionally; all 320 unsuppressed occurrences retained for forensic review; no policy filtering |
| Pinned actionlint command below |Exit 0 for both workflows, including final manual deployment guard changes |
| Official action commit lookups |All four existing action SHAs resolve to the requested commit in their official GitHub repositories; no action versions changed |
| Safe-summary CLI smoke with mixed job conclusions and extra outputs |Exit 0; only fixed statuses written, extra outputs discarded |
| Backend health smoke below |HTTP 200/healthy with engine construction forbidden and dotenv disabled; no DB connection or private storage operation |
| Shared DB URL negative smoke |Missing, development and production targets all raise the required guard error |
| `npm test` from apps/web |53 tests PASS, 4 files; Vitest reports 2.20 seconds |
| `python3 infra/scripts/verify_release.py docs/evidence/m126/release-result.json` |Exit 1 / BLOCKED; container_security, ai_security, ci_cd, production_environment unmet |
| `git fsck --full` |Exit 0; existing dangling objects are preserved, not garbage-collected |
| `git diff --check` |Exit 0; new files also checked for whitespace |

The 320 occurrences are repeats/copies of the same 38 verified non-credential
values, not new secret discoveries. The policy is exact, with no path/rule-wide
exclusions. Raw Gitleaks still reports findings and returns 1; wrapper success
means all findings are independently reviewed, not that raw detection was disabled.
Archive depth is 3. Missing scanner/version, bad JSON, invalid or duplicated policy,
missing/ambiguous historical commit, input symlink and scanner errors fail closed.
Encrypted/unsupported archive contents and LFS payloads are not certified.

Regression coverage includes generated, non-issued GitHub/Sourcegraph/generic
credential shapes; inline-allow comments and repository-local blanket config do
not defeat scanning. A generated credential in a ZIP is detected. A new credential
appended to an otherwise reviewed evidence file in a temporary existing-history
clone makes the end-to-end gate fail with exit 1 and no value in stdout/stderr.
No regression test creates commits. Byte/location/value/scope changes reject exact
adjudications. Same-line fingerprint collisions remain distinct by columns.

Safe-summary tests verify that failed job conclusions survive without outputs or
diagnostics, and reject arbitrary job names/status text. Workflow guards assert
one exact safe artifact path, full action SHA pins, secrets-job dependencies,
full-history checkout, no automatic caching, manual-only deployment, credential
scope after guards, formal accepted-report validation and unconditional SSH-key
cleanup. Existing release decisions still reject missing/failed/unknown criteria.

Initial implementation checks were retained privately and corrected before final
PASS: archive member paths needed normalization to enclosing Git blobs; one test
counted nested archive copies as plain same-line matches; Gitleaks rewrites its
output mode despite a precreated file. The final scanner requires a private parent
throughout, restores final mode 0600, and both location and permission regressions
pass. No tests or assertions were removed to obtain PASS.

## Reproduction boundaries

Run from the project root with installed Gitleaks 8.30.1. Private directories must
be new, outside the checkout; the wrapper refuses reuse. A default invocation
creates a private temporary directory. Do not point the scanner at local private
storage, upload its raw reports or paste findings into chat. The standard config
is forced and inherited Gitleaks configs/ignore files/inline allows cannot replace it.

The CI Linux scanner is downloaded from its official 8.30.1 release. Archive
SHA256 is pinned to:

```text
551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb
```

It matches the official release checksum retrieved during this task. Local scanning
used installed Gitleaks 8.30.1 on macOS; Linux hosted execution of the changed
workflow remains NOT VERIFIED. Digest equality/official commit resolution is not
represented as an independent publisher-signature verification.

Actionlint runs without network or development-data mounts:

```sh
docker run --rm --network none \
  -v "$PWD/.github/workflows:/work:ro" -w /work \
  rhysd/actionlint@sha256:b1934ee5f1c509618f2508e6eb47ee0d3520686341fec936f3b79331f9315667 \
  -color ci.yml deploy.yml
```

Backend smoke used the existing virtualenv and only health/guard code:

```sh
PYTHONPATH=apps/api apps/api/.venv/bin/python - <<'PY'
from unittest.mock import patch
from app.core.config import Settings
settings = Settings(_env_file=None, app_env='test',
    database_url='postgresql+psycopg://nobody@invalid.invalid:1/never',
    auth_allow_insecure_http=True)
with patch('app.core.config.get_settings', return_value=settings), \
     patch('sqlalchemy.create_engine', side_effect=AssertionError('No DB access permitted')):
    from fastapi.testclient import TestClient
    from app.main import app
    response = TestClient(app).get('/api/v1/health')
    assert response.status_code == 200 and response.json()['status'] == 'healthy'
from app.db.disposable_database import disposable_database_url
for url in ('', 'postgresql+psycopg://localhost:5433/evidenceai',
            'postgresql+psycopg://production.invalid:5432/evidenceai'):
    try:
        disposable_database_url({'EVIDENCEAI_TEST_DATABASE_URL': url})
    except RuntimeError:
        pass
    else:
        raise AssertionError('Unsafe target accepted')
PY
```

One existing Starlette/httpx dependency deprecation warning appeared. Full backend,
browser, migration, image rebuild and load/recovery suites were not repeated:
application behavior/DB isolation code did not change, and this task forbids
application DB/private-document changes. The health and URL-policy checks perform
no engine construction, migration, test-record write or private storage access.
The frontend test command changed no source. Existing controlled full-suite
results remain historical evidence, not newly claimed 12.8 executions.

## Read-only GitHub observations

GET-only snapshots of runs/artifacts/caches, branches, collaborators/invitations,
webhooks, deploy keys, secret-name counts, environments and Actions policy were
saved privately. No repository metadata GET was repeated to obtain another clone
token. Original run 39435975032 is now completed/failure. Two available artifacts
(total compressed sizes 1814 and 2995 bytes) were downloaded and scanned with
archive depth 3: zero detections. No source/image/diagnostic release artifact was
listed. Two dependency caches have sizes 30215817 and 141037902 bytes; their
contents remain NOT VERIFIED and they were not restored/deleted.

Main is unprotected; protection/ruleset endpoints return HTTP 403 with the private
plan restriction. One owner/admin collaborator; zero pending invitations, hooks,
deploy keys, repository secret names and environments. Actions policy permits all
actions without required SHA pinning; default workflow token permissions are read
and workflow PR-review approval is disabled. App/OAuth/PAT grant coverage and
historical clone/download access are NOT VERIFIED. Counts are snapshots, not proof
that no integration can access the repository. No setting mutation was made.

The proposed CODEOWNERS/check names, required independent review and prohibited
force-push/deletion settings require owner approval and plan support; they are
recommendations rather than live protection. The current sole reviewer cannot
satisfy independent self-change approval. First-push logs/artifacts are evidence of
the old workflow only, not execution of these local changes.

## Custody, unresolved exposure and release

The prior temporary clone-token response remains restricted locally and never
enters a new Git file. Scope, expiry and access remain unknown. Recommend owner
invalidation/revocation and associated credential rotation if those properties
cannot be established, without validating the candidate or assuming unrelated
credentials are compromised. No credential action was performed.

Original reachable history, prior evidence files/archives, 12.7 private report and
original backup hashes remain unchanged. Durable encrypted offline media, separate
key escrow and long-term private CI forensic retention remain NOT VERIFIED.
The [assessment](github-security-hardening-12-8.md) contains executable encryption
instructions and explicit owner checkpoints. No destructive cleanup or history
sanitization was performed.

Formal decision: **FAIL / production BLOCKED.** Existing container vulnerabilities,
development audit findings and hosted requirements are not cleared by local
secret adjudication. New workflow/policy enforcement on GitHub and plan-supported
branch/environment protection remain NOT VERIFIED until separately approved
commit/push and hosted execution. No approval to perform those actions is implied.
