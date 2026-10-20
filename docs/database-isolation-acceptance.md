# Database isolation acceptance — 12.6

**Current controlled isolation/preservation: PASS. Historical writer attribution:
NOT VERIFIED.** HEAD `cc22799`, 2026-10-20 Asia/Dubai. Production remains FAIL /
BLOCKED for separate security and hosted requirements.

The committed [checkpoint](database-isolation-current-verification.json) is
accepted as PASS:662 backend tests,16 development tables with identical row
hashes/counts, unchanged revision and identical private-storage content/metadata.
This report does not repeat or undo the completed import-path remediation in
`b0e9782`. Its absolute runner paths are inherited by migration/test subprocesses;
no manual PYTHONPATH is needed and child commands run from the repository root.
Three runner regressions pass again. Application/guard/runner code is unchanged.

12.6 independently verifies the same current boundary after backend, browser and
local monitoring acceptance: [comparison](evidence/m126/data-preservation.json)
reports PASS for all16 tables, revision and private-storage bytes/mode/UID/GID/
mtime. The read-only repeatable-read baseline remained mode0600 under `/tmp`,
never in Git. No row values, recipient identities or private storage paths are
published. Access time is outside the comparison; end-state equality cannot prove
that an unobserved transient write was never reverted.

| Check | Actual result / scope |
| --- | --- |
| Backend on newly owned tmpfs DB |662 passed in26.32s; one dependency deprecation warning |
| Migrations |head91e2b6d8c410; `alembic check`: no new upgrade operations |
| Browser on separately owned DB |Final18/18 PASS, six per engine; initial18 launch failures due missing old /tmp binaries retained; installed pinned browsers in new directory, unchanged tests pass |
| Entry-point refusal |15/15 PASS: pytest, browser fixture, retrieval, RAG and combined evaluator each reject missing explicit URL, loopback development DB and nonloopback production target |
| Cleanup |Backend, failed browser and final browser DBs each have zero scratch schemas and zero public users/intents/limiter rows; ownership-checked containers removed; independent Docker listing confirms absence |
| Read-only development comparison |16/16 whole-table hashes/counts, schema revision and storage bytes/metadata match; zero deltas |

[Guard receipts](evidence/m126/entry-guards.json), [backend](evidence/m126/backend-commands.json),
[cleanup](evidence/m126/cleanup-verification.json), and
[commands/limitations](security-remediation-12-6-verification.md).

Pytest and browser activate the shared policy before constructing application
engines. Evaluation functions validate the explicit URL and require configured and
cached-engine URLs to match before schema creation. Missing/unsafe URLs cannot
fall back to `.env`. CI uses its job-owned explicit synthetic service database.
The runner replaces both DATABASE_URL and EVIDENCEAI_TEST_DATABASE_URL and sets
APP_ENV=test; the original development URL is never selected by that child.

The policy requires psycopg PostgreSQL, loopback, explicit port, strict generated
name and no query options. This is syntactic validation, **not proof of ownership**
for arbitrary manually provided databases. Use the runner's owned container,
immutable database image, random credentials, tmpfs and loopback port. A service
renamed to imitate a test name is not thereby safe. Preserve label verification,
empty-public/scratch checks and fail-closed behavior; none was weakened.
Local smoke uses its separately owned Compose project, generated secrets,
synthetic bind directories/tmpfs and no development mounts; its containers were
also independently confirmed removed.

The earlier [12.5 final FAIL](evidence/m125/data-preservation-final.json) and
[historical investigation](database-integrity-investigation.md) remain valid
historical observations. Eight limiter/three intent additions and the later
limiter row were not deleted or rewritten. The current controlled PASS does not
identify their writer, erase prior equality failures, authenticate missing custody
timestamps or establish production-host protection. Those claims remain NOT
VERIFIED. Existing historical evidence was preserved unchanged.
