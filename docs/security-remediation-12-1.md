# Security remediation 12.1

**Production release: BLOCKED.** Starting revision:
`4107cb379185f55956c37efdfc7aa4d48714f913`, clean at inspection. Changes remain
uncommitted. See the [verification report](security-remediation-verification.md)
and [complete inventory](security-remediation-inventory.json).

## Actual before/after result

Fresh Trivy 0.76.0 scans reproduced 302 high/critical occurrences across 55 advisory
IDs. Final scans report **61 high, zero critical**, across 12 advisory IDs.
**241 occurrences were removed (239 high and both critical)**. Forty-three original
advisory IDs are absent from all severities in the final reports; none was merely
reclassified to a lower severity. These are scanner observations, not an assertion
of universal exploitability or absence of unknown vulnerabilities.

| Image | Before high | Before critical | After high | After critical |
| --- | ---: | ---: | ---: | ---: |
| API / worker | 44 | 0 | 0 | 0 |
| Web | 43 | 0 | 0 | 0 |
| Backup | 44 | 0 | 0 | 0 |
| Proxy | 0 | 0 | 0 | 0 |
| Database | 86 | 2 | 0 | 0 |
| Prometheus | 8 | 0 | 0 | 0 |
| Exporter | 14 | 0 | 0 | 0 |
| Grafana | 61 | 0 | 61 | 0 |

All eight final images have zero scanner secret findings. Every scan was matched
to the live local image filesystem layers. The inventory includes advisory IDs,
packages, installed/fixed versions, distributions, image/config IDs and affected
layers for both refreshed baseline and final findings. Local OCI IDs are not
claimed to be published registry digests. All builds/tests here were Linux ARM64;
AMD64 hosted acceptance remains NOT VERIFIED.

## Critical fixes

**CVE-2026-6653 — database libxml2.** The old Debian package version
`2.12.7+dfsg+really2.9.14-2.1+deb13u3` was based on vulnerable 2.9.14 code, despite
its apparent 2.12 prefix. The supported PostgreSQL 17.11 Alpine runtime contains
actual `libxml2 2.13.9-r2`. pgvector 0.8.7 is compiled from a checksum-pinned official
source archive. The new linked/runtime component and fresh scan remove the finding.
[Debian's vendor record](https://security-tracker.debian.org/tracker/CVE-2026-6653)
explains the reverted Debian version and upstream fix history.

**CVE-2025-68121 — database gosu.** The vulnerable Go 1.24.6 libraries were embedded
in `/usr/local/bin/gosu`, not the PostgreSQL C server. The Alpine base still carried
that executable: the first candidate scan exposed it and was retained. This
unused root-only privilege-switching helper is now actually removed. The wrapper
requires the deployment's existing UID 999 and refuses root startup, so the
upstream root-only gosu branch cannot be used. Both absence and root rejection
were exercised. We did not claim that installing a new Go compiler patches an
old binary. [The Go advisory](https://pkg.go.dev/vuln/GO-2026-4337) describes the
embedded TLS issue and fixed versions.

The database major/minor and pgvector version remain 17.11 / 0.8.7. The dedicated
UID remains 999. This does not make existing glibc cluster files safe to reuse
with musl: a runtime marker guard rejects pre-existing unmarked data directories,
and app rollout now refuses any DATABASE_IMAGE change before pulling/stopping
services. The production database candidate requires a separately reviewed
**fresh-volume logical migration**, locale/collation review, index reconstruction,
checksummed restoration and application acceptance. No existing development
PostgreSQL container/image/volume was replaced or reset.

## Shared runtime and compiled-library fixes

API, web and backup moved to digest-pinned supported Alpine runtimes and were
rebuilt. Python retains its exact package pins and binary-wheel-only installation;
PostgreSQL backup clients come from supported Alpine PostgreSQL 17 packages rather
than copied glibc libraries. Tests include the full backend suite inside the actual
Alpine dependency runtime, real PostgreSQL/pgvector, parsing/security fixtures,
standalone Next.js build, and staged upload/download/recovery under production
resource/security settings. Unnecessary Debian utilities/libraries are absent;
findings were not excluded through scanner rules or package-database deletion.

Prometheus 3.15.0, promtool and node_exporter 1.12.1 were actually recompiled with
Go 1.27.2 and locked patched modules. x/net is 0.60.0; its compatible transitive
crypto/text versions were resolved and locked instead of forcing an incompatible
crypto version. The Prometheus web UI was rebuilt from its frozen upstream pnpm
lockfiles and retained outside its writable data mount. Prometheus health and real
API/worker scrape targets passed in staging. No Grafana plugins were removed to
hide findings or change dashboard capabilities.

## Registration privacy fix

The old endpoint exposed new `201` identity objects versus existing-email `409`
responses. A generic status alone would still permit chosen-password probing via
login. The new workflow is:

1. Every valid registration returns the same **202 and generic body**, regardless
   of new, existing, inactive or differently cased email. It performs Argon2id and
   the same expiring-intent insert, without first looking up the user.
2. No usable identity or session is created before verification. Login with the
   submitted password fails for an unverified new request, closing the follow-up
   enumeration probe.
3. A random 256-bit email token and separate random browser proof are stored only
   as hashes. The browser proof is an HttpOnly, SameSite cookie, Secure/Host-prefixed
   under HTTPS. Expiration uses PostgreSQL time, default 30 minutes.
4. Verification requires both the emailed token and the initiating browser cookie.
   This prevents an attacker from initiating registration for a victim address
   and later using a password known to the attacker after the victim clicks a link
   in another browser. Links use fragments, cleared before submission, to keep
   tokens out of server URLs/referrers. GET does not activate an account.
5. Verification locks/consumes the intent once and inserts the identity only if
   its case-insensitive unique email is absent. It never overwrites an existing
   password, display name, disabled status or session, and does not log the user in.
6. Existing IP rate limits and CSRF controls remain; a shared per-recipient request
   budget additionally limits enrollment-mail flooding. Expired intents are cleaned
   in bounded batches.

The frontend now shows generic acceptance, verification and explicit sign-in;
it no longer automatically logs in after registration. API consumers must adapt
from the old 201/UserResponse contract to 202/acceptance and verification.

SMTP uses implicit TLS, hostname/certificate verification, optional explicitly
trusted private CA, and file-backed production credentials. The staging fixture
used a private TLS SMTP sink and real smtplib delivery; it sent nothing to external
mailboxes. Browser tests use a strictly isolated synthetic delivery fixture, not a
production verification bypass. Production delivery defaults to disabled and
SMTP failures remain generic publicly. **No UI/API text claims an email was sent.**
Real SMTP credentials, sender policy, delivery monitoring and external delivery
acceptance must be configured/verified before public self-service enrollment.

Backend tests cover identical status/content, pre-verification login, one-use
proof, expiration, wrong browser, disabled identities, password/session preservation,
CSRF, Secure cookies and verified SMTP TLS. Twenty paired loopback timing samples
per class measured medians 32.71 ms existing versus 30.07 ms new (2.65 ms difference),
within the predefined 20 ms practical bound. Raw samples are preserved. These
measurements use synthetic delivery and do not prove resistance to every timing
attack or production SMTP/network variability.

The additive `registration_intents` migration was first tested in a disposable
PostgreSQL instance, then applied to the verified loopback development database.
Head is now `91e2b6d8c410`. All original rows remain byte-for-byte; an additional
localhost-login throttle bucket observed during the session was preserved and
reported separately. Existing identities/sessions/documents were not rewritten.

## Remaining Grafana blocker and risk ownership

Grafana 13.2.4 core has five kin-openapi findings; bundled datasource executables
carry the remaining Go/x/net, gRPC and Tempo findings. The exact 61 occurrences,
12 advisory IDs, paths and listed fixed versions remain in the inventory. Some
plugins are not provisioned, but the Prometheus datasource is used; dependencies
are not declared harmless simply because they are bundled or currently unused.

The [latest upstream release checked](https://github.com/grafana/grafana/releases/tag/v13.2.4)
was 13.2.4. A compatible 13.2.5 registry tag was unavailable. A core source attempt
resolved kin-openapi 0.149.0 but did not complete its large build during the local
attempt; it was stopped and never promoted or included in CI/release images.
That is **NOT VERIFIED**, not proof the update is incompatible or that no fix is
possible. A rebuilt core alone would also leave the separately compiled plugins
vulnerable. The attempted recipe/locks/log remain under ignored local evidence.

The monitoring/infrastructure maintainer must supply a patched, compatible core
**and all affected bundled plugin binaries**, validate dashboard/datasource behavior,
then rescan. Supported alternatives require the same functional/security acceptance;
no untested replacement or feature removal was made. Current mitigations are the
private monitoring network, no public Grafana port, strong file-injected admin
credentials, disabled anonymous signup, read-only runtime and resource limits.
They do not satisfy the release gate and are not an approved exception.

Python audit and runtime npm audit report zero findings. The five high affected
build-only npm lint-chain nodes remain (`GHSA-vfj7-8cjw-p6xm`); no compatible braces
patch was available in the checked registry. No framework downgrade or suppression
was applied. Named release/security owners must review all remaining risks; this
report grants no waiver. Hosted CI/approvals, intended production hardware/public
TLS, offsite recovery and real external email delivery remain NOT VERIFIED.
