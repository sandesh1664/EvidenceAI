# Security Remediation 12.6 — verification record

2026-10-20 Asia/Dubai. HEAD `cc22799`; working tree initially clean. New work is
uncommitted. **Formal production decision FAIL / BLOCKED.** Commands run from
`/Users/redmug/EvidenceAI` unless noted. New receipts live under
`docs/evidence/m126`; large raw scans/vendor captures/logs are under ignored
`infra/runtime/m126`. Historical evidence was not overwritten.

## Executed commands and outcomes

| Command / precise scope | Actual result |
| --- | --- |
| `git status --short`; `git log -6 --oneline` |Clean baseline; HEADcc22799, precedingb0e9782 import fix |
| `env -u PYTHONPATH apps/api/.venv/bin/python infra/testing/run_isolated.py --evidence-directory docs/evidence/m126/backend-isolation -- python3 docs/evidence/m126/verify_local.py backend` |exit0;662 tests26.32s,1 Starlette/httpx deprecation warning; current revision91e2b6d8c410; no Alembic upgrade operations; pip check clean |
| `python3 docs/evidence/m126/verify_local.py runner` |exit0;3 runner tests |
| `python3 docs/evidence/m126/check_entry_guards.py` |exit0;15/15 actual subprocess refusals across pytest/browser/retrieval/RAG/combined and missing/development/production targets |
| `/tmp/evidenceai-m126-audit/bin/python -m pip_audit -r /Users/redmug/EvidenceAI/apps/api/requirements.txt --format json` |exit0; pip-audit2.10.1;44 dependencies,0 vulnerabilities; separate /tmp tool environment, project virtualenv unchanged |
| `python3 docs/evidence/m126/verify_local.py frontend` |exit1 overall because full development audit FAIL;53 frontend tests, lint, TypeScript, production build and runtime npm audit individually exit0 |
| Initial `env -u PYTHONPATH apps/api/.venv/bin/python infra/testing/run_isolated.py --evidence-directory docs/evidence/m126/browser-isolation -- python3 docs/evidence/m126/verify_local.py browser` |exit1;18 browser launch failures, binaries absent from old /tmp location; no passing assertions claimed |
| From apps/web: `PLAYWRIGHT_BROWSERS_PATH=/tmp/evidenceai-m126-browsers npx --no-install playwright install chromium firefox webkit` |exit0; pinned binaries installed in new temporary location; no lockfile/test changes |
| Final `env -u PYTHONPATH apps/api/.venv/bin/python infra/testing/run_isolated.py --evidence-directory docs/evidence/m126/browser-final-isolation -- python3 docs/evidence/m126/verify_local.py browser-final` |exit0;18/18, six per engine;85.321s wrapper, Playwright1.4m; all original assertions/timeouts retained |
| `python3 docs/evidence/m126/scan_monitoring.py` |exit1 strict policy; fresh full-image scans selected61 HIGH, upstream5 HIGH, custom2 HIGH; all0 CRITICAL/secrets |
| `python3 docs/evidence/m126/scan_monitoring.py --other-runtime` |exit0; other seven selected runtime images all0 HIGH/CRITICAL/secrets, same fresh DB; separate runtime inventory |
| `python3 docs/evidence/m126/vendor_review.py` |Official releases, fix diffs, ancestry, registry tags, support and Cloud/PDC docs fetched; 200 except expected v13.3.0 release404; no account contact/change |
| `python3 docs/evidence/m126/verify_local.py monitoring` |exit0;193.531s, local synthetic private-CA fixture; monitoring and restart/transition/rollback pass; one-document encrypted restore and negative restores pass |
| `python3 docs/evidence/m126/validate_hosted_compose.py` |exit0;7 assertions, synthetic configuration only; no startup or public issuance |
| `python3 infra/scripts/verify_release.py docs/evidence/m126/release-result.json` |exit1/BLOCKED; container_security, ai_security, ci_cd and production_environment unmet |
| `python3 infra/scripts/release_manifest.py --output infra/runtime/m126/manifest.json` |exit1; clean committed source required; no package created |
| `git diff --check` |PASS; final receipt under m126 |

Backend wrapper runs exact pytest command with new JUnit output and then Alembic
current/check and pip check **inside the owned runner**. Frontend wrapper executes
`npm test`, `npm run lint`, `npx --no-install tsc --noEmit`, `npm run build`,
`npm audit --omit=dev --json` and `npm audit --json` from apps/web. Individual
command arrays/exits/durations are in `*-commands.json`. Full npm audit still
reports five HIGH nodes: braces, micromatch, fast-glob,
@next/eslint-plugin-next and eslint-config-next. npm suggests a major downgrade
of eslint-config-next to14.2.35; this was not applied as an unreviewed fix.
No frontend remediation or security threshold change is claimed. The project
virtualenv did not contain pip-audit; a separate /tmp venv was created and the
auditor installed there. Its setup/audit command receipts and exact logs are
retained; no project dependency was changed.

The monitoring wrapper selects upstream12.4.13 only in the disposable fixture and
transitions to retained `evidenceai-grafana:kin-m125`. Default smoke omits the
already completed12.5 load/full-app recovery extension. It checks admin/anonymous
and signup controls, provisioned dashboard/datasource, all13 expected trusted
native plugins, real Prometheus2-target queries, internal monitoring/no published
Grafana port, private route denials and stable synthetic dashboard state across
restart/custom transition/rollback. It backs up/restores1 document/original,
pgvector0.8.7, revision91e2b6d8c410; tampered and nonempty restore targets reject.
These passes do not certify all external datasources, production13→12 migration,
intended-host load, long soak, full restored hosted app, offsite key custody or
production rollback. Full sanitized result: [monitoring](evidence/m126/monitoring-result.json).

## Scanning and source/binary distinction

The new empty Trivy cache downloaded published intelligence UpdatedAt
`2026-10-20T13:14:22.737606427Z`, DownloadedAt
`2026-10-20T13:34:41.153238753Z`, NextUpdate
`2026-10-21T13:14:22.737606156Z`. Scanner0.76.0 immutable pin and all three exact
image IDs/registry digests, full severity counts/findings, report/archive hashes
and rootfs identities are in [inventory](evidence/m126/monitoring-inventory.json).
The scanner receives only explicit image archives, cache/report directories,
never a Docker socket or development data. No ignores, VEX, severity reduction,
plugin deletion or dependency-version forgery. A successful JSON report is not
a security-policy PASS; aggregate scan script exits1.

No new candidate was built. The same vendor releases/fix inputs are still
available; previous actual disposable builds and failing module-path probes are
preserved under12.5. New work instead reads exact compiled metadata/graph and
binary SHA256 from the retained immutable candidate using read-only,
network-disabled `docker run --rm` commands. Fresh official fix diffs and ancestry
are in `vendor-review.json`; exact pinned source SHA256/relevant fix lines in
`pinned-tempo-source.json`. Query default262144 and secret-typed encryption key
are present in source; affected frontend/S3 server packages are absent from the
custom compile graph. This is limited source/reachability evidence, not vendor
binary equivalence or an accepted correction of two HIGH image findings.
Build provenance/graph hashes match the bytes extracted from the retained image;
original extracted streams are retained without whitespace normalization.

Supported options and the unsent vendor escalation draft are in the
[assessment](security-remediation-12-6.md). Grafana Cloud/PDC is an option to
evaluate, not an acquired service, tested replacement or image-gate waiver.
Only a changed supported artifact/fix or authoritative scanner mapping correction
justifies reopening builds. No speculative repeat probe was run.

## Development-data and evidence preservation

Executed read-only baseline before tests:

```sh
PYTHONPATH=apps/api apps/api/.venv/bin/python infra/testing/preservation.py --snapshot /tmp/evidenceai-m126-private-before.json
```

After all database/browser/monitoring execution:

```sh
PYTHONPATH=apps/api apps/api/.venv/bin/python infra/testing/preservation.py --compare /tmp/evidenceai-m126-private-before.json --report docs/evidence/m126/data-preservation.json
```

Both exit0.16 whole-table hashes/counts, revision and private-storage content/
metadata match; table deltas empty. Private snapshot mode0600 outside Git;
this explicit PYTHONPATH belongs only to the separate read-only preservation
utility, **not** isolated test commands. The committed checkpoint is accepted
independently; no prior failed comparison or historical record was replaced.
Current equality does not identify historical writers or prove complete custody.

Backend/initial-browser/final-browser isolation records each confirm no scratch
schemas/public fixture leaks and owned-container removal. Independent `docker ps
-a` checks for all three exact container names and the owned monitoring project
return no containers: [cleanup](evidence/m126/cleanup-verification.json).
No volume reset, development credentials in tests, record cleanup or historical
log overwrite was used to obtain PASS. [Database acceptance](database-isolation-acceptance.md).

The historical preservation check compares all tracked paths under docs/evidence,
excluding only new m126, against HEAD. Guard/runner/application/production
Compose/scanner/deployment/release-gate/CI paths also remain unchanged. Reports
and readable logs are new12.6 files. New gzip log archives retain exact bytes and
SHA256s; they are not historical attestation. No checksum of old evidence was
regenerated to hide a mismatch.

## Prepared hosted configuration and limitations

New `infra/compose.hosted-staging.yml` retains public ACME/80/443 from base,
APP_ENV=staging, the existing proxy trust address/private monitoring and failing
selected Grafana pin. It was **configured only**, never started. Initial ad-hoc
validation omitted optional profiles and failed a harness lookup of missing
Grafana; final explicit-profile harness passes7 assertions. Both outcomes are
recorded in the configuration receipt. `deploy.py` defaults remain unchanged;
its local staging overlay must not be mistaken for hosted public-TLS acceptance.

[Executable hosted plan](hosted-staging-execution-plan.md) includes preflight,
explicit hosted Compose selection, stop conditions, authorized bootstrap,
DNS/TLS/ingress checks, controlled SMTP, workers/private documents, private
monitoring, CI review, encrypted offsite recovery and accepted-predecessor rollback
requirements. No hosted command, DNS mutation, infrastructure purchase, mail send,
account connection or workflow dispatch was executed. Secret values stay with
the authorized operator outside chat/Git. All those real-host receipts remain
NOT VERIFIED. Formal production decision stays FAIL / BLOCKED.
