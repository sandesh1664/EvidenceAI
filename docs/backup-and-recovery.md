# Backup and recovery

A complete EvidenceAI recovery point includes the application PostgreSQL database **and
private original files**. Database-only backup is insufficient. Milestone 11 implements
quiesced encrypted bundles and a disposable restore verifier. It does not provide managed
PITR, multi-host failover or an achieved production recovery SLO.

## Backup and retention

The deployment wrapper stops the proxy/API/worker before copying a recovery point. This
prevents document metadata, cleanup and physical originals from changing between pg_dump
and storage copy. Existing HTTP idempotency and worker leases remain authoritative after
forced termination. Schedule and announce the maintenance window; a large job can exceed
its grace period and recover later by lease expiration.

```sh
python3 infra/scripts/deploy.py --env-file /private/operator/staging.env backup
python3 infra/scripts/deploy.py --env-file /private/operator/staging.env list-backups
```

Use the production environment/ack flags only after acceptance. The backup tool refuses
without the wrapper's quiescence flag. It runs pg_dump custom-format with no owner/ACL/
object-comment payload, copies flat private objects into tmpfs, verifies every document's
original checksum, records a versioned manifest, then encrypts the entire archive using
age. File digests, storage keys and the DB dump remain inside encrypted contents. Output
contains only opaque archive filename, counts and duration. Ciphertext publication is
atomic and fsynced. Handled failures clean partial ciphertext; a forced kill can leave
an ignored `.partial` file for deliberate operator inspection.

App/database clients are PostgreSQL 17; pgvector must exist and schema revision must equal
`6f22cc4c46ad`. Legacy/missing/corrupt originals cause failure rather than a misleading
successful backup. Staged `.part` and cleanup-orphan objects are included; all restored
live document keys must still match the database checksum. Backups include private
conversation/citation contents, so restrict decryption and retention accordingly.

After a successful backup, only tool-owned filename patterns older than configured
retention are pruned (default 14 days). No database or document records are deleted by
retention. PostgreSQL roles/admin/provider secrets are regenerated or recovered from
your separate secret-management process; they are not bundled into the application dump.
Proxy/Grafana/Prometheus state is separately reproducible or retained by deployment policy.

Encrypted archives persist in the selected project's backup volume, on the same host.
**That alone does not survive host loss.** Export an exact archive to a new private file:

```sh
python3 infra/scripts/deploy.py --env-file /private/operator/staging.env \
  --backup-file evidenceai-TIMESTAMP-UUID.tar.age \
  --export-path /absolute/private/offsite-transfer/recovery.tar.age export-backup
```

Replace the filename with an exact value returned by list-backups. Export refuses an
existing output file. Transfer encrypted copies to an independently secured/offline or
remote location through your accepted process. No external cloud account, bucket, transfer
credential or purchase is configured here. Keep at least one offline recovery identity;
losing the identity makes these backups unrecoverable. Replacing an encryption recipient
does not make old archives decryptable with the new key.

`infra/deploy/evidenceai-backup.service` and `.timer` are uninstalled examples for a daily
03:00 UTC maintenance-window backup with catch-up. Configure the deployment account,
accepted current-release path, private registry access and writable runtime lock directory
before enabling them. The Docker account is a trusted host administrator. Monitor timer
failure and backup freshness and copy successful archives off-host. No scheduler was
installed or enabled during this milestone.

## Isolated verification

Temporarily place the offline identity in the explicitly granted recovery secret file.
Then select one exact archive:

```sh
python3 infra/scripts/deploy.py --env-file /private/operator/staging.env \
  --backup-file evidenceai-TIMESTAMP-UUID.tar.age restore-verify
```

The verifier can target only `restore-db` / `restorecheck`, on its own internal network,
with an empty public schema. It refuses path traversal, overwrite, archive links,
unexpected archive paths, excessive archive size, manifest mismatch and digest mismatch.
Age authenticates ciphertext before pg_restore. The tool restores the DB with
--exit-on-error and checks migration revision, pgvector, document count and every live
original's bytes against its checksum. Plaintext is tmpfs only and is removed afterward.
The disposable DB container is stopped/removed, with no Docker volume deletion. It is
not a production database and is not promoted into the live topology.

Both backup and restore currently use a 2GiB tmpfs spool containing copies plus the tar
bundle; this limits practical dataset size below 2GiB. Size this explicitly before real
workloads. No plaintext spool is silently moved onto permanent disk. The age implementation
is installed from Debian packages in a pinned base plus current security updates; retain
the exact tested image digest and package/scanner evidence.

## Real incident recovery

1. Declare the incident, restrict writers and preserve existing volumes. Record the
   accepted application/schema version and exact encrypted archive and image digests.
2. Verify age decryption and run the isolated drill first. Ensure the recovery identity
   and provider/database credentials are available through the secret-management process.
3. Provision a **new** deployment project/volumes; initialize its DB/role/pgvector only.
   Do not run migrations into an already-restored schema and do not overwrite the current
   development or incident database.
4. In a private, bounded RAM working directory, decrypt the bundle with `age --decrypt
   --identity ...`, inspect/verify the manifest and safe entries as in the verifier,
   and restore `database.dump` with PostgreSQL 17 `pg_restore --exit-on-error --no-owner
   --no-acl --dbname ...` into the new empty application DB. The app role owns its schema;
   preinstalled pgvector avoids superuser extension creation. The dump omits object comments
   so extension-owner comments do not require application superuser privileges.
5. Copy verified original files to the new private document volume as UID/GID 10001,
   directory mode 0700/files 0600, with no symlinks/hardlinks. Recheck all live document
   keys/checksums and schema/extension/foreign-key integrity before starting API/worker.
6. Start accepted images without a downgrade, verify protected readiness, login/CSRF,
   private download, retrieval/conversation history and cleanup/lease recovery. Revoke
   restored sessions and rotate compromised secrets if the incident requires it.
7. Perform an explicitly approved DNS/proxy cutover and keep the old volumes until the
   recovery has been accepted. Re-establish monitoring, offsite backups and retention.

These manual import/cutover steps must be rehearsed against the actual target in Milestone
12. This milestone automates verification, not an irreversible production overwrite or
DNS switch. Never run pg_restore --clean against the development database.

## Targets and observed evidence

Proposed initial RPO: **24 hours**, conditional on daily successful/offsite verified backups.
Proposed initial RTO: **60 minutes** for a small single-host deployment, pending representative
rehearsal. Neither is an achieved guarantee. A one-document local drill verified an encrypted
application dump and original file, revision `6f22cc4c46ad` and pgvector 0.8.7. Reported tool
durations exclude host provisioning, transfer, DNS, approval and full application acceptance;
see the committed Milestone 11 verification evidence for the final measured run.
