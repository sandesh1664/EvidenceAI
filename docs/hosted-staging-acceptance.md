# Hosted staging and real-provider acceptance

Status: **NOT VERIFIED**. No host, DNS changes, public deployment, real-provider
email delivery or exception is authorized by this document. An operator must
obtain explicit infrastructure/deployment and recipient authorization first.
Local private-CA fixtures do not establish these hosted results. Record UTC time,
operator, exact source SHA, immutable image digests, commands, redacted outputs,
expected result and actual PASS / FAIL / NOT VERIFIED for every item below.

## Hosted staging checklist

| Requirement | Acceptance evidence | Current status |
| --- | --- | --- |
| Host and DNS | Approved host, intended architecture, A/AAAA resolve to reviewed addresses; provider account and firewall ownership recorded; only 80/443 public, SSH restricted | NOT VERIFIED |
| HTTPS issuance and renewal | Publicly trusted chain, matching hostname, expiry/renewal rehearsal, HTTP redirect, HSTS; no `curl -k` or private-CA substitution | NOT VERIFIED |
| Reverse proxy | `/api/v1/ready` reaches FastAPI, `/login` reaches Next.js, private ops/metrics/storage/monitoring paths denied, forwarded header forgery rejected | NOT VERIFIED |
| FastAPI | Exact Alembic head, database ready, Secure HttpOnly cookies and trusted-origin CSRF; production secrets read from operator-owned files | NOT VERIFIED |
| Next.js | Intended API connectivity, register/verify/login/workspace flows, HTTPS browser console/network inspection without exporting tokens | NOT VERIFIED |
| PostgreSQL / pgvector | Intended PostgreSQL image, pgvector extension/version and vector search; restricted app role; no public DB port; never swap glibc/musl on existing PGDATA | NOT VERIFIED |
| Background workers | Synthetic upload extraction, embeddings/retrieval and pending-job recovery; bounded retries, metrics and queue drain | NOT VERIFIED |
| Private document storage | Nonpublic paths and permissions, tenant authorization, byte-exact authorized download, cross-tenant denial; synthetic files only | NOT VERIFIED |
| Email verification | Execute real-provider procedure below and retain redacted receipts; generic enrollment and replay/expiry/CSRF/rate-limit checks | NOT VERIFIED |
| Monitoring isolation | No public ports/routes, admin secret, anonymous/signup disabled; provisioned dashboard; datasource health and actual Prometheus query; alert delivered to approved operator | NOT VERIFIED |
| Encrypted backup / restore | Quiesced backup, off-host encrypted copy, independently escrowed key, checksums and pgvector restore into fresh isolated target; byte-exact files, sessions and queued work; measured RTO/RPO | NOT VERIFIED |
| Controlled rollback | Previous *accepted* digest env and schema compatibility checked before writers stop; compatibility failure refuses change; successful prior/current transition plus readiness/auth/download/queue | NOT VERIFIED |
| Hosted CI/CD | Passing exact-SHA CI, intended architecture, required branch checks, environment reviewers/no self-approval, approved SSH fingerprint and acceptance marker; evidence reviewed before manual release | NOT VERIFIED |

For rollback, use `infra/scripts/deploy.py ... rollback` only after a separately
approved compatible previous environment has been reviewed. Its readiness check
must succeed against the present schema before switching applications. Preserve
DB and originals; never auto-downgrade Alembic or overwrite live volumes. An
incompatible predecessor requires separately approved isolated recovery/cutover.
The old M11 image does not expect schema `91e2b6d8c410`, so its historical M12
rollback result is not evidence of present compatibility. No accepted predecessor
or hosted rollback was verified in 12.2.

## Safe real-provider SMTP acceptance procedure

1. Obtain authorization for one staging host, sender domain and controlled test
   mailboxes. Use synthetic names/passwords and an approved low message budget;
   never register customers or send to unapproved recipients. Record provider
   region, retention and sender-domain requirements. Confirm SPF, DKIM and DMARC
   with the provider and domain owner without modifying DNS in this task.
2. Have the operator place an app-specific, least-privilege SMTP credential in
   `SECRETS_DIR/smtp_password` outside Git (parent mode 0700, host file restricted,
   runtime-readable via Compose secret). Do not put it in `.env`, shell arguments,
   tickets, screenshots or evidence. Set `SMTP_USERNAME`, `SMTP_HOST`,
   `SMTP_PORT=465`, `SMTP_SENDER`, `REGISTRATION_EMAIL_ENABLED=true` and exact HTTPS
   `PUBLIC_ORIGIN` in the private operator configuration. `REGISTRATION_PUBLIC_ORIGIN`
   is supplied from `PUBLIC_ORIGIN`; trusted frontend origin must match. Empty
   SMTP credentials are permitted only when provider policy explicitly allows
   authenticated sending by another approved mechanism. No fake successful delivery.
3. Run `python3 infra/scripts/deploy.py --env-file /absolute/private/staging.env
   validate` (one line). Validate provider availability and certificate chain with
   `openssl s_client -connect APPROVED_SMTP_HOST:465 -servername APPROVED_SMTP_HOST
   -verify_return_error -verify_hostname APPROVED_SMTP_HOST </dev/null`. Substitute
   only an approved hostname. Verify system trust; never disable TLS validation.
   SMTP uses implicit TLS, not STARTTLS; a provider supporting only STARTTLS/587 is
   incompatible with current delivery and remains NOT VERIFIED until reviewed.
4. Under separate hosted deployment authorization, start the reviewed staging
   configuration. In one HTTPS browser submit a new controlled email. Record only
   status 202 and generic message. Login before verification must return 401.
   Confirm provider acceptance and actual controlled-inbox arrival (UTC receipt,
   redacted Message-ID and delivery latency). SMTP 250/provider acceptance alone
   is not proof of inbox delivery. Inspect SPF/DKIM/DMARC result headers without
   saving the verification URL or recipient's identifying data.
5. Open the link in the requesting browser; verify once and explicitly log in.
   Link alone in a different browser must fail. Replay must fail. A fresh proof
   allowed to expire beyond the configured TTL (default 1800s) must fail without
   changing clocks or production records. Browser proof and email tokens must not
   be exported to logs, HAR files, evidence or screenshots. The fragment must be
   removed from the address bar before the verification POST.
6. Repeat enrollment for an existing controlled account and case variation;
   compare generic responses. Verify the existing password, display name, enabled
   state and session were preserved. Reject missing/foreign-origin CSRF and
   exercise configured per-IP and per-recipient limits within the approved budget.
   Do not disable limits to make acceptance pass. Retain only aggregate results.
7. Exercise an isolated provider rejection/unreachable fixture (not a live customer
   configuration) and verify the same generic response, no usable unverified
   account and no token/password/provider diagnostic leakage. Inspect redacted
   application and provider logs. Check permitted alerting separately: current
   delivery errors are intentionally hidden publicly and this alone provides no
   operator delivery-success signal.
8. Have the authorized operator rotate/revoke the test credential and decide
   staging retention after the drill. Record owner and PASS/FAIL for TLS,
   authentication, provider acceptance, inbox receipt, identity controls and
   credential handling separately. Without these receipts, real delivery remains
   NOT VERIFIED and does not become a release pass.

The deterministic unit suite and local TLS SMTP sink exercise application behavior
without sending external mail. They do not verify provider credentials, quotas,
sender reputation, DNS authentication, inbox delivery or real abuse resistance.

## 12.3 pending hosted execution procedures

All items here remain **NOT VERIFIED** on 2026-10-20 (Dubai). Source templates and
local fixtures have been reviewed, but no production credentials or host were
accessed. These are operator steps after separate authorization, not commands
executed during remediation.

- **TLS/ingress:** after approved DNS and firewall provisioning, verify intended
  A/AAAA with `dig APPROVED_HOST A` / `dig APPROVED_HOST AAAA`, HTTPS chain/hostname
  with `openssl s_client -connect APPROVED_HOST:443 -servername APPROVED_HOST
  -verify_return_error -verify_hostname APPROVED_HOST </dev/null`, and routing
  with `curl --fail --silent --show-error https://APPROVED_HOST/api/v1/ready`.
  Check HTTP redirect and HSTS with `curl -I` and denial of `/metrics`,
  `/grafana/api/health`, and `/api/v1/ops/metrics`. Never disable TLS verification.
  Record certificate renewal rehearsal, access rules and redacted results.
- **Hosted staging:** select approved digest-only environment outside Git, run
  `python3 infra/scripts/deploy.py --env-file /absolute/private/staging.env validate`,
  then (only under deployment authorization) `... start` and `... monitoring`.
  Verify readiness, controlled registration/verification/login, private synthetic
  upload/search/download, worker queues and the monitoring checklist. Local
  fixtures cannot replace host hardening, public certificate and delivery evidence.
- **Hosted CI/CD:** repository owner records branch protection/required checks,
  required environment reviewers/no self-approval and the pinned SSH identity.
  After deliberately reviewing/committing the final source in a separate step,
  verify successful `ci.yml` for that exact main-push SHA and inspect all scan,
  dependency and acceptance artifacts. Any security gate failure stops here.
  Only release authority can approve an accepted manifest and dispatch the
  protected manual host rollout. Do not dispatch workflows or modify protections
  as part of this remediation.
- **Hosted encrypted recovery:** under an approved maintenance window, run
  `... backup` using the private staging environment, export the selected encrypted
  backup with an explicit unused path via `... --backup-file BASENAME
  --export-path /absolute/private/UNUSED.age export-backup`, and transfer it by
  an approved authenticated method to an independent recovery host. The basename
  must come from operator backup listing; never invent a receipt. Verify ciphertext
  checksum, independently escrowed key access, `... --backup-file BASENAME
  restore-verify` against fresh disposable recovery storage, restored revision/
  pgvector/files, authenticated downloads and pending work. Record actual timestamps,
  last acknowledged writes and measured loss/RTO; same-host local timings are not
  production objectives. Preserve original volumes and prohibit in-place overwrite.
- **SMTP:** execute the controlled-recipient, verified implicit-TLS and actual-inbox
  procedure above; retain redacted receipts and provider rejection/limit outcomes.
  No internet message was sent during 12.3.

For each abbreviated `...` above use the full `python3 infra/scripts/deploy.py
--env-file /absolute/private/staging.env` prefix; supply action options before the
action, as shown by `--help`. Add production flags only in a separately approved
production procedure. None of these pending steps grants infrastructure purchase,
DNS mutation, public deployment, email recipient access or security exceptions.
