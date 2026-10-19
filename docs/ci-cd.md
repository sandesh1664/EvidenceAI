# CI/CD

Milestone 11 adds workflow definitions, not a running GitHub deployment. No commit, push,
registry publication, repository environment change or remote SSH action was performed.
GitHub-hosted execution, environment permissions and release approval remain to be accepted
in Milestone 12.

## Verify and package

`.github/workflows/ci.yml` runs on main pushes, pull requests and manual dispatch. Official
checkout/setup/artifact actions are pinned to resolved commit SHAs. Jobs have explicit
read-only repository permissions, timeouts and cancellation/concurrency policy.

The application job configures Python 3.14.6, Node 26.12.0 and isolated PostgreSQL 17/pgvector.
It installs locked dependencies, upgrades the empty CI database once, runs Alembic
current/check, pip check, all backend tests, offline versioned evaluation, frontend lint,
TypeScript, unit tests, Webpack production build and Chromium E2E. Test transport guards
prevent paid provider calls. The CI superuser is a synthetic service-container fixture;
production uses a restricted application role.

The container job builds API/worker, web, backup and proxy candidates, then runs the local
TLS/storage/worker/monitoring/backup/restore drill. Candidates get full `sha-FULL_COMMIT`
tags. `release_manifest.py` requires committed source and records image IDs/provenance;
registry manifest digests are recorded separately after operator publication. Packaging
preserves image tar files, source archive, smoke evidence and scanner reports. No CI step
pushes images or deploys them automatically.

Trivy 0.76.0 is pinned by image digest. It scans candidate image tar files for vulnerabilities
and secrets without mounting the Docker socket. High/critical findings fail the scan job;
all candidates are still scanned and reports uploaded for review. There is no blanket
ignore list. Base/monitoring images also require release security review. Local reports
already contain findings, so this candidate must not be treated as production accepted.
Security updates are applied during release builds, and exact tested images must be
promoted rather than rebuilt after acceptance.

The separate dependency job uses pip-audit 2.10.1 and npm audit. Full frontend development
findings are preserved; high/critical production npm findings and Python audit failures
fail the job. An audit database/resolution error must not be reported as a clean scan.
Review advisories and reachability, then update supported dependencies/images or record a
narrowly justified, expiring exception through the Milestone 12 acceptance process.

Artifacts retain evaluation/dependency evidence for 30 days and release candidates for
14 days. Apply repository/organization access controls and storage quotas. Never upload
.env files, private keys, real source documents or customer evaluation corpora.

## Approval-gated rollout

`.github/workflows/deploy.yml` has **workflow_dispatch only**. It requires a full accepted
commit SHA, the main branch and an explicitly selected staging/production environment.
The job uses GitHub environment protection and also checks the environment API for a
required-reviewer rule with no self-approval. Missing/unreadable protection fails closed.
It then uses strict pinned SSH host verification to invoke the already installed matching
release and `/etc/evidenceai/ENV.env` / `ENV.previous.env`. An operator acceptance marker
`/etc/evidenceai/accepted/FULL_SHA.json` must exist on the target. The workflow never edits
DNS, creates hosts, purchases services or silently replaces secrets.

Before enabling deployment, configure both GitHub environments:

- Required independent reviewers and prevent self-review; restrict deployment to protected
  main, with repository branch protection and required successful CI/security checks.
- Environment variables `DEPLOY_HOST` and `DEPLOY_USER`.
- Environment secrets `DEPLOY_SSH_KEY` and `DEPLOY_KNOWN_HOSTS`, populated from verified
  operator material. Do not use ssh-keyscan output as unverified trust-on-first-use.
- A trusted deployment account, dedicated host paths and read access to accepted image
  registry credentials. Docker access is host-administrator authority; limit the key,
  host network and account accordingly.
- A matching clean release checkout installed under `/opt/evidenceai/releases/FULL_SHA`,
  accepted registry digests in the new env file, a preserved previous env file, successful
  recovery evidence and an acceptance marker reviewed outside the rollout job.

No cloud/provider key, database password, operator bearer, backup identity or runtime
secret belongs in the workflow's build arguments. Runtime Compose secrets are supplied
on the host. The runner SSH key exists only in its private temporary SSH directory and is
removed even on failure. Protect source/release checkouts against modification by untrusted
application processes.

Rollout is serialized and creates a quiesced recovery point, migrates once while writers
stay stopped, recreates the app and checks readiness. Failure stops for inspection;
application rollback is explicit and schema-checked. There is no automatic database
downgrade or destructive restore. See the deployment guide and backup runbook.

Action pins were resolved from the official repositories:
[checkout](https://github.com/actions/checkout), [setup-python](https://github.com/actions/setup-python),
[setup-node](https://github.com/actions/setup-node), [upload-artifact](https://github.com/actions/upload-artifact).
Keep these pins and scanner databases under normal dependency maintenance.
