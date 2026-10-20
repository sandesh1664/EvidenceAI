# Local signup email verification (macOS)

This workflow is exclusively for a trusted developer's machine. It uses the existing
PostgreSQL database and real signup endpoints, with an implicit-TLS SMTP receiver
bound to **127.0.0.1:1465**. No Docker volumes, migrations, existing accounts,
documents or historical evidence are changed by setup. Completing an actual signup
intentionally creates a new registration intent and, after verification, a new user.
Do not run automated signup tests against development; use the disposable runner below.

## Start

Prerequisites: existing API virtualenv and dependencies, PostgreSQL already running
on 127.0.0.1:5433, `openssl` on PATH (Homebrew OpenSSL 3 is suitable), and the existing
API `.env` configured for `APP_ENV=development`. Never copy production secrets into it.
Use a private terminal without session recording. All commands below start from the
repository root. The mail directory must not exist before `init`.

Terminal 1:

```sh
cd /Users/redmug/EvidenceAI
apps/api/.venv/bin/python infra/development/mail.py init --directory "$TMPDIR/evidenceai-local-mail"
apps/api/.venv/bin/python infra/development/mail.py serve --directory "$TMPDIR/evidenceai-local-mail"
```

`init` creates a private local CA (30 days) and a server certificate (7 days) with
DNS `localhost`, IP `127.0.0.1`, serverAuth EKU and explicit CA constraints. It refuses
existing directories. The CA is loaded only by the API's SMTP TLS context; it is
**not** installed in the macOS trust store. Hostname verification remains enabled.
For subsequent starts, omit `init`. After expiry, stop both processes and initialize
a different unused private directory; use that same directory in all commands.

Terminal 2: stop your existing Uvicorn process with Control-C in its own terminal
first (port 8000 must be free), then:

```sh
cd /Users/redmug/EvidenceAI
apps/api/.venv/bin/python infra/development/mail.py api --directory "$TMPDIR/evidenceai-local-mail"
```

This launches Uvicorn on **127.0.0.1:8000**, with proxy headers and access logs off.
It reads the existing database URL from `apps/api/.env`, refuses a non-development
`APP_ENV`, then sets process-only overrides:

- `APP_ENV=development`, `AUTH_ALLOW_INSECURE_HTTP=true`
- `TRUSTED_FRONTEND_ORIGINS=["http://localhost:3000"]`
- `REGISTRATION_PUBLIC_ORIGIN=http://localhost:3000`
- `REGISTRATION_EMAIL_ENABLED=true`
- `SMTP_HOST=127.0.0.1`, `SMTP_PORT=1465`, `SMTP_SENDER=noreply@evidenceai.test`
- `SMTP_CA_FILE=<private directory>/ca.pem`; SMTP username/password cleared

No environment file is rewritten. Staging/production retain HTTPS-only origins and
reject insecure HTTP. The only permitted HTTP email origin is exactly
`http://localhost:3000`, with the development environment and explicit HTTP opt-in.
The launcher does not run migrations, seed data or change accounts.

Terminal 3: if Next.js is not already running:

```sh
cd /Users/redmug/EvidenceAI
npm --prefix apps/web run dev -- --hostname 127.0.0.1
```

## Receive and complete signup

1. Visit `http://localhost:3000/register` and submit your intended new account.
   Keep that browser profile open. Requests retain their uniform public response;
   a success response does not assert mail delivery.
2. In a private interactive terminal, view the most recently received message:

   ```sh
   cd /Users/redmug/EvidenceAI
   apps/api/.venv/bin/python infra/development/mail.py view --directory "$TMPDIR/evidenceai-local-mail"
   ```

3. Open the displayed `http://localhost:3000/verify-email#token=...` link in the
   **same browser profile**. Click **Verify email**, then sign in. Alternatively,
   visit `/verify-email` in that profile and paste the token into its password field.
   No shell command containing a token is needed. Avoid clipboard synchronization,
   screenshots, shared terminals, terminal recording and copying tokens into chat.
4. A different browser cannot use the link. Default expiry is 30 minutes; links
   are single-use. Request a new registration if expired. The page clears the URL
   fragment on submission. Verification never logs in automatically, changes an
   existing password or reactivates an inactive account.

If no message appears, check that the receiver is running, certificates have not
expired, both processes use the same directory and the API was started with the
launcher. Never disable TLS checks to troubleshoot. The receiver retains at most
100 messages and rejects additional mail when full. Only the most recent message
is displayed; its recipient is shown so concurrent signups cannot be confused.

## Stop and custody

Use **Control-C** in the receiver terminal and API terminal. Restart the ordinary
API command if email delivery should be disabled again. There is no background
LaunchAgent, public inbox, HTTP token endpoint or public SMTP port. Do not use
`killall`, stop unrelated containers, or remove database volumes.

Mail and private keys stay in the owned mode-0700 directory; each generated file
is mode 0600. The viewer refuses redirected stdout. These are sensitive local
artifacts, not Git content, application logs or uploadable diagnostics. Stopping
retains them; after stopping, remove only this dedicated mail directory through
Finder when no longer needed. macOS temporary-directory cleanup is not durable
custody or guaranteed secure erasure. Do not archive it or add it to CI artifacts.

Any process running as the developer (and root) can read the mailbox, and any local
process can submit mail to the loopback receiver; there is no SMTP authentication.
TLS authenticates the receiver, not individual local senders. This is a bounded
single-connection development tool, not a hardened multiuser mail server. Do not
port-forward, tunnel, container-publish, share or deploy it. The localhost web/API
HTTP exception relies on a trusted local machine; SMTP always uses verified TLS.

## Automated verification

```sh
cd /Users/redmug/EvidenceAI
apps/api/.venv/bin/python infra/testing/run_isolated.py -- apps/api/.venv/bin/python -m pytest apps/api/tests -q
npm --prefix apps/web test -- --run
```

`test_local_mail.py` starts its own ephemeral loopback SMTP receiver and ephemeral
CA; it never reads the real mailbox. It exercises actual TLS delivery plus HTTP
signup, hashed proof storage, successful verification/login, missing browser proof
rejection, expiry, replay and untrusted-CA/wrong-hostname rejection. Existing auth
coverage retains uniform responses, CSRF, rate limits and existing-account safety.
Read-only preservation comparisons use `infra/testing/preservation.py` as documented
in [isolated testing](../infra/testing/README.md). Keep snapshots outside Git.

## Verification recorded 2026-10-20

- Full backend command above: **676 passed in 30.28s**, exit 0. This includes
  14 new cases (four real SMTP/signup flows, two certificate trust/hostname
  rejection checks in one test, seven origin-policy cases, and two launcher
  safeguards). One existing Starlette/httpx deprecation warning remains.
- Frontend command above: **53 passed**, four files, 1.74s, exit 0.
- Browser/build command:

  ```sh
  PLAYWRIGHT_BROWSERS_PATH=/tmp/evidenceai-m126-browsers apps/api/.venv/bin/python infra/testing/run_isolated.py -- npm --prefix apps/web run test:e2e
  ```

  **18 passed (1.2m)** across Chromium, Firefox and WebKit, exit 0. The configured
  Next.js production build succeeded. This existing browser suite uses its
  synthetic delivery fixture; the new backend tests independently exercise actual
  SMTP/TLS receipt. No signup was performed against the development database.
- Launcher tests confirm `.env` bytes are unchanged, overrides are development-only,
  Uvicorn binds to loopback, and staging settings are refused.
- The first backend run had four new test failures caused by reading the MIME
  wire encoding without decoding it. The test now parses MIME with the standard
  email parser, matching the viewer. The corrected run passed 674 tests; adding
  launcher coverage and validating development settings yielded the final 676.
- Read-only before/after comparison: **PASS**, all 16 development-table row hashes
  and counts equal, migration revision equal, private storage contents and metadata
  equal. No table count changes. This confirms this run's preservation, not
  historical write attribution.
- Both final backend/browser runners recorded zero remaining scratch schemas,
  public users, registration intents and limiter rows in their disposable baselines,
  `isolation_clean=true`, and `owned_container_removed=true`. A subsequent Docker
  label-filtered inventory returned no disposable test containers.
- Python compilation and `git diff --check`: **PASS**. No application databases
  were migrated or written by this verification. No commits, pushes, deployments,
  historical-evidence changes or security-gate changes were made. Existing production
  release blockers remain in force.

Private snapshot and execution logs are outside Git under
`/tmp/evidenceai-local-mail-*`; the snapshot and logs have mode 0600. They are local
verification artifacts, not durable archival evidence. The actual running
local API still needs to be restarted using the launcher above to enable mail;
existing development services were not stopped or replaced during verification.
