# GitHub security hardening — Milestone 12.8

**Production: FAIL / BLOCKED. Local hardening implemented; hosted enforcement NOT
VERIFIED.** Date: 2026-10-20, Asia/Dubai. Inspected baseline `c0103321e041` with a
clean working tree. HEAD is unchanged; proposed work is uncommitted/unpushed.
No settings change, deployment, database/private-document operation, history
rewrite, credential validation or credential disclosure occurred.

## Independent secret triage and exact handling

The restricted 12.7 reports remain outside Git. Their conclusions were checked
against a fresh Gitleaks 8.30.1 scan, matching all 66 findings by rule, commit,
file and columns. Two occurrences share a scanner fingerprint; columns preserve
them independently. The report's redaction marker was never treated as a secret.

| Independently established content | Detections | Distinct values |
| --- | --- | --- |
| Public Go dependency checksums, exact public module/version records | 52 | 27 |
| Target Git-file bytes recomputed against recorded SHA256s | 7 | 7 |
| Official public Grafana tag identities used as build/source metadata | 5 | 2 |
| Complete Markdown narrative context without credential use | 2 | 2 |
| Total confirmed false positives | 66 | 38 |

There are 28 repeat detections, zero synthetic-credential findings, zero genuine
credentials and zero unresolved cases **among the original 66**. Public checksum
response bytes were independently integrity-checked and their contents compared
locally; all seven target-file hashes were recomputed. Public source-tag proof
and prose use were checked. Filename, formatting and location were not sufficient
classification evidence. No detected credential was sent to a validation endpoint.
No rotation or history removal is required for these non-credential values.

`infra/security/gitleaks.toml` extends all built-in rules and contains **no
allowlists**. The separate `adjudications.json` is a narrowly scoped policy, not
a copy of the restricted triage report. Each entry binds scope, exact path/member,
historical revision when applicable, complete enclosing-file/archive digest,
matched-value digest, rule and line/column span. Only four reviewed proof classes
are permitted. It contains public metadata/digests, no raw credential values.

`scan_secrets.py` runs the scanner without ignores or inline exemptions, then
compares each occurrence with those exact records. Any new value, changed file,
new location, different revision, scanner error or invalid policy fails closed.
Changing a reviewed file does not grandfather credentials in that file. Ambiguous
or missing abbreviated historical revisions fail. A genuine credential introduced
inside a previously reviewed evidence file is rejected by regression testing.

The unsuppressed scanner is preserved independently: 134 history occurrences,
134 current-tree occurrences and 52 historical-archive occurrences, all the same
38 non-credential values. These 320 exact occurrences include archive copies of
the original 66; they are not 320 new secrets. All raw scanner invocations still
exit 1. The adjudicated gate exits 0 only when every occurrence is exactly
reviewed. No original evidence/archive was edited to make scanning pass.

Current scanning uses tracked and nonignored working files; history scans all
reachable refs and separately scans historical archive bytes to depth 3. The
scanner is pinned to 8.30.1. A version change requires review/rescan, not automatic
policy expansion. Synthetic regression values are generated in private temporary
fixtures, never committed as credential literals. A secondary existing-history
clone tests rejection; no test creates commits or rewrites history.

Raw reports/logs stay under a mode 0700 directory outside the checkout, with final
report/log files mode 0600. Gitleaks writes its JSON with broader file mode during
execution, so the private parent protects that write and the wrapper restores
0600 immediately afterward. Scanner diagnostics and values never reach stdout.
`--audit-only` rejects every finding and retains an unsuppressed forensic view.

## CI and artifact changes

A new `secrets` job runs on existing main-push, pull-request and manual triggers.
It fetches complete history with credential persistence disabled, installs the
checksum-pinned official Linux scanner, runs regressions and executes the gate.
Application, container and dependency jobs all require this job to succeed.
No automatic hosting/production rollout was added.

All raw `always()` artifact uploads were removed: offline evaluation reports,
diagnostic JSON/CSV/logs, dependency reports and `release/` no longer upload on
success **or failure**. Local image/source packaging and all strict vulnerability
checks still execute in their existing jobs; their outputs remain runner-local.
No automatic distribution of release images/source is provided by this patch.
A future approved distribution mechanism must be reviewed separately.

The sole remaining artifact is `safe-ci-summary/status.json`, generated in a
separate job from fixed job names and conclusion enums only. Extra job outputs
are discarded; arbitrary job names/status text are rejected. It records that no
release authorization was granted. Only this exact file is uploaded, with seven-day
retention. It contains no paths, logs, scanner findings, raw errors, source or
images. The safe summary job can run after failures without exposing those payloads.

Raw forensic CI evidence is produced outside the workspace and deliberately not
uploaded. Hosted runners are ephemeral: durable hosted raw-evidence retention is
**NOT VERIFIED** until an approved encrypted destination and custody policy exist.
Local unsuppressed reports are retained privately for this review. Public or
ordinary artifact storage is not substituted for restricted incident custody.

CI database isolation was reviewed: the application job retains its own ephemeral
pgvector service, explicit synthetic test database name, both test/application URL
overrides and APP_ENV=test. Backend and browser guards therefore cannot inherit
the development URL from dotenv. The fixed synthetic database name is scoped to
that job-owned service, not a shared development service. Browser fixtures use
temporary private storage and scoped schemas; the container smoke retains its
separately owned synthetic project/tmpfs fixture. These configurations and shared
guards were not weakened. The new secret and summary jobs require no database.

Automatic pip/npm cache use and saving are disabled in the proposed workflow.
Existing remote caches remain untouched. Third-party action SHAs and existing
scanner/actionlint container digests are retained. Workflow permissions remain
read-only; deployment adds only its existing read scopes. Deployment SSH credentials
were narrowed from job-wide environment to the SSH step after review/exact-SHA
guards. Target environment is explicitly checked, and the remote accepted report
must now pass the existing formal release gate before rollout. Manual dispatch,
main-only ancestry, exact successful CI SHA, reviewer/no-self-approval requirement,
pinned SSH host and unconditional key cleanup remain intact.

## Live GitHub review and proposed settings

Read-only review of private `sandesh1664/EvidenceAI` found the original main-push
run **39435975032 completed with failure**. Two existing artifacts (dependency
and evaluation reports) were downloaded privately and archive-aware scanned:
**zero detections**. No container release/source/diagnostic artifact was listed.
This is a bounded content review, not a proof that heuristic scanning detects all
possible secrets. Two existing caches were listed; contents remain NOT VERIFIED.
No artifact/cache deletion, workflow rerun/dispatch or cancellation was performed.

One owner/admin collaborator, zero pending invitations, webhooks, deploy keys,
repository Actions-secret names and deployment environments were observed. These
counts do not enumerate all GitHub App, OAuth or PAT grants, historical downloads
or private clones. Comprehensive integration access remains NOT VERIFIED; an
owner-side grant/installation review is required.

Main metadata is unprotected. Branch-protection and ruleset GETs return HTTP 403
with a private-repository plan restriction. Repository Actions allow all actions
and do not enforce SHA pinning; the existing workflow uses are pinned. Default
token permissions are read; workflow PR-approval permission is disabled. None of
these settings was changed. Do not make this repository public or purchase a plan
as an implicit workaround.

Prepare the following for **explicit owner approval and supported plan review**:

- Main: require pull requests and at least one independent approval; require code
  owner review for security/workflows; dismiss stale reviews, approve the last
  push independently and resolve conversations. The current sole owner cannot
  independently approve their own change; establish an authorized reviewer first.
- Require up-to-date successful checks named `secrets`, `application`, `containers`,
  `dependency-report` and `safe-summary`. A successful summary alone is insufficient.
- Prevent force pushes and branch deletion; apply rules to administrators and
  tightly review bypass rights. Restrict direct writes and preserve audit access.
- Retain read-only default tokens and no PR-review approval. Restrict third-party
  actions and enforce reviewed full-SHA pins where the plan permits.
- Review collaborators, App installations/OAuth/PAT grants and environment-scoped
  permissions with the owner. Configure actual staging/production reviewers,
  no self-approval and main restrictions before any deployment consideration.
- Inventory caches/artifacts/logs by exact run/ref; preserve forensic hashes before
  separately approved deletion if actual sensitive contents are identified.

`.github/CODEOWNERS` records the current owner's review responsibility for workflow,
secret-policy, deployment/release/security and isolation paths. It **does not
activate server enforcement**. Policy/workflow edits must receive trusted review;
a malicious contributor able to alter the gate and merge without review can defeat
repository-local CI code. Current plan/protection limitations are a release blocker,
not an assurance this file alone solves that trust boundary. Proposed workflow
changes have not run on GitHub because no commit/push/dispatch is authorized.

## Temporary clone metadata and custody

The restricted 12.7 API response contains a provider-returned temporary clone-token
field. It was not displayed, reused, validated or copied into Git. It is absent
from reachable repository history. API caller permissions do not establish the
temporary token's scope. Expiry, scope and access remain NOT VERIFIED; do not infer
expiration merely from elapsed time or the field name.

**Recommend owner-assisted revocation/invalidation and rotation where scope,
expiry or access cannot be established.** The owner should identify the associated
grant through approved administrative records. If targeted invalidation is not
available and GitHub cannot establish that the temporary credential is expired
and safely scoped, revoke/rotate the associated issuing credential/grant after
reviewing consumer impact and reauthorize with least privilege. This is precautionary,
not evidence that unrelated account credentials were compromised. Never redeem
the value to test it or paste it into chat. No revocation/rotation was executed.

## Encrypted offline original-history instructions

12.7's original all-ref bundle and complete Git-admin archive remain unchanged and
hash verified. The existing isolated bare-mirror restore/fsck passed. `/tmp` is
not durable offline custody. The custodian must approve media, encryption recipient,
independent private-key escrow and retention before any transfer. No purchase,
transfer, key generation or custody change was performed here.

On the approved workstation, set the following variables to **approved absolute
paths/public recipient**, without disclosing a private key. Apply separately to
the original bundle, Git-admin archive and any necessary restricted incident data:

```sh
umask 077
# ORIGINAL_FILE: original verified bundle/archive, never the live .git directory.
# NEW_CIPHERTEXT: unused path in an approved restricted directory.
# APPROVED_AGE_RECIPIENT: custodian-verified public encryption recipient.
test -f "$ORIGINAL_FILE"
test ! -e "$NEW_CIPHERTEXT"
set -C
age --encrypt --recipient "$APPROVED_AGE_RECIPIENT" "$ORIGINAL_FILE" > "$NEW_CIPHERTEXT"
sha256sum "$ORIGINAL_FILE" "$NEW_CIPHERTEXT"
```

Verify hashes against the original custody manifest before transfer; copy only
ciphertext to approved offline/read-only media and verify it again there. Escrow
private keys independently, outside Git, CI artifacts, shell arguments and chat.
On an isolated recovery machine decrypt to a new mode 0700 recovery directory,
verify original plaintext hashes, clone the bundle into a new bare mirror and run
`git fsck --full`; compare all original refs/objects. Recover the administrative
archive only into a new isolated location, never over the live `.git` directory.
Mac operators may use `shasum -a 256` in place of `sha256sum`.

Keep original historical evidence and manifests byte-for-byte; sanitized derivatives
need new labels/hashes and a restricted mapping. No history rewrite is justified
by the 66 false positives, and none was prepared or performed. Offline encryption,
independent media/key custody and owner credential action remain NOT VERIFIED.

## Verification and release decision

Local secret/workflow/summary regressions, pinned actionlint, backend health with
engine construction forbidden, unsafe-DB-target refusal checks, frontend tests,
Git integrity and diff checks pass. The existing formal release gate still rejects
with exit 1. Exact commands/results and initial harness corrections are in the
[verification record](github-security-hardening-12-8-verification.md).

Retained release blockers remain: selected Grafana last verified 61 HIGH, custom
candidate 2 HIGH, development dependency findings and required hosted acceptance.
These images were not rebuilt/rescanned in this workflow-only task; those counts
are retained evidence, not a fresh image-security claim. Historical database writer
attribution remains NOT VERIFIED. **Production release stays FAIL / BLOCKED.**

References: [Gitleaks release](https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1),
[GitHub workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax),
[setup-node cache controls](https://github.com/actions/setup-node), and
[GitHub sensitive-history guidance](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository).
