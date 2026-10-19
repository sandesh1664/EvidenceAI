# Milestone 12 disaster recovery verification

**PASS for the isolated local drill. Production/offsite recovery: NOT VERIFIED.**
2026-10-19 UTC; starting Git revision
`02462040fec9eea53c596618c32b09cb694d60ee` plus the uncommitted
[source manifest](evidence/m12/source-manifest.json).
[Machine-readable evidence](evidence/m12/staging-recovery.json) records the final
staging, load, restore and rollback run. Project: `evidenceai-staging-smokec9c94e41db`.

## Actual recovery results

| Requirement | Classification | Observed result |
| --- | --- | --- |
| Encrypted database and private-original backup | PASS | age-encrypted bundle, pg_dump custom format; 27 DB document rows and 27 private originals. |
| Integrity | PASS | Authenticated age decryption, SHA-256 manifest for database dump and every original; all document references checked against stored checksums. |
| Database and document restore | PASS | Disposable empty `restore-db/restorecheck` target; originals copied only to a separately mounted empty `/restored-documents`. |
| pgvector extension | PASS | Version 0.8.7. |
| Alembic integrity | PASS | Revision `6f22cc4c46ad`, matching the backup and current source; no downgrade or new migration. |
| Existing session and fresh password login | PASS | Restored session used before logging in anew, then normal restored login succeeded over verified private-CA HTTPS. |
| Restored downloads | PASS | Existing original and a queued document returned exact expected bytes through authenticated APIs. |
| Queue and worker recovery | PASS | Worker stopped first, unique upload acknowledged/queued, writers quiesced, backup made. Restored worker completed that pending job. |
| Nonempty-target protection | PASS | Second restore refused the populated database; it did not overwrite data. |
| Tamper protection | PASS | Deliberately changed authenticated ciphertext rejected in a new empty target. |
| Runtime shutdown | PASS | API exit 143, worker 0, proxy 0; no OOM kill or SIGKILL/137. No in-flight hosted-request drain was tested. |
| Local rollback compatibility | PASS | Prior M11 backend/worker compatibility check, restart, existing session and download; return to M12 verified. No schema downgrade. |
| Existing development records/volumes | PASS | Fifteen public table hashes and migration revision matched before/after. All generated staging containers removed; development Compose unchanged. |

The recovery helper validates the only permitted destination before database
restoration and rejects application storage/traversal destinations. Four added
backend cases exercise this restriction. No production importer or overwrite flag
was added; the recovery DB promotion exists only inside the disposable smoke
harness and retains the restore helper's fixed-target guard.

## Measured duration and data-loss window

- Encryption/backup helper: **0.051 seconds**, excluding writer shutdown/container startup.
- Restore/integrity helper: **0.075 seconds**, excluding DB startup/application readiness.
- Local recovery after the pending-job fixture setup, from API/proxy writer-stop initiation through restored authenticated downloads and pending job completion: **45.908 seconds**. This passed the proposed **120-second local-fixture** threshold recorded before testing.
- Last acknowledged fixture write to encrypted backup completion: **1.128 seconds**.
- Observed loss: **zero acknowledged synthetic writes**. The deliberately queued upload was present and usable after recovery. Writers were stopped for a consistent DB/filesystem recovery point.
- Rollback to the baseline candidate readiness: **39.726 seconds**, separate from recovery measurement. Return to the current candidate also passed.

These are measured local rehearsal intervals, not an achieved production RTO or
RPO. No host provisioning, offsite transfer, key retrieval, incident approval,
public certificate issuance, DNS change or customer-scale dataset was included.
The last-write interval is not a claim that a production system has a 1-second
RPO. The existing proposed 24-hour backup RPO / 60-minute host RTO remain
**NOT VERIFIED** until a realistic independent-host rehearsal measures them.

## Isolation, consistency and key handling

The fixture uses unique project names, bounded tmpfs PostgreSQL databases and
private temporary host document/backup directories. It generates a fresh age
identity and synthetic credentials, never prints their values, and mounts the
private identity only in restore verification. API/worker use file secrets and a
dedicated nonsuperuser role. Backup happens after stopping writers; the filesystem
and relational references are verified together. PostgreSQL 17.11 / pgvector 0.8.7
and the original Alembic head were used. Restore uses fresh data storage, not the
user's development volume. The encrypted backup and its temporary keys are
removed with the fixture, so this is evidence of a drill rather than a retained
customer recovery point.

After checksum verification, only the fixture's restore DB is renamed for normal
application use, its dedicated application role receives permissions, and the
API/worker switch to that DB and the recovered directory on private networks.
Existing sessions and original downloads are then tested through the real proxy.
The original fixture DB remains separate. All temporary services/networks are
cleaned without `down --volumes` or development-volume operations.

Rollback used the preserved local `evidenceai-api:m11` candidate because there is
no accepted production predecessor. M11 also had vulnerabilities: this was a
local compatibility exercise, not approval to deploy that image. The proxy stayed
on its patched candidate. The database was retained and never downgraded.

## Reproduce

Build the four `:m12` images as listed in [release acceptance](release-acceptance.md),
install the pinned Locust runner, and run:

```sh
EVIDENCEAI_ACCEPTANCE=1 EVIDENCEAI_ROLLBACK_IMAGE=evidenceai-api:m11 python3 infra/scripts/smoke.py
```

Omit `EVIDENCEAI_ROLLBACK_IMAGE` if that preserved local image is unavailable;
the rest of the drill still runs and rollback becomes NOT VERIFIED explicitly.
The output is `/tmp/evidenceai-m12-smoke-result.json`; detailed private logs and
load counters are under ignored `infra/runtime/m12/`. Reported PASS values require
successful process exit as well as the evidence fields. Final drill exit was 0.

## Remaining production dependencies

SRE/security owners must escrow the identity offline, verify access under incident
conditions, send authenticated ciphertext to independent offsite storage, test
retention and alert receipt, and rehearse representative restoration/cutover on a
separate intended host. Host loss, regional loss, PITR, compromised credentials,
production session revocation, stale backup detection, deletion/lost key recovery,
long-running requests and real storage exhaustion remain NOT VERIFIED. There is
no configured/verified offsite backup delivery or production incident RTO/RPO in
this report. Production remains BLOCKED by container findings regardless of this
successful local recovery.
