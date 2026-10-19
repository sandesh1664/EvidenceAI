# Milestone 12 security assessment

**Production release: BLOCKED.** Assessment date: 2026-10-19 UTC. Starting Git
revision: `02462040fec9eea53c596618c32b09cb694d60ee` (clean at inspection).
The tested implementation includes uncommitted Milestone 12 changes; the
[source manifest](evidence/m12/source-manifest.json) identifies them. This is an
engineering assessment using source review, deterministic adversarial fixtures,
real PostgreSQL concurrency tests and isolated staging. It is not an independent
penetration test or certification.

## Findings and remediation

| ID | Severity / result | Evidence and impact | Remediation / accountable role |
| --- | --- | --- | --- |
| SEC-01 | High/critical, **FAIL** | Runtime OS and Go libraries remain vulnerable across seven of eight images. All occurrences, installed/fixed versions and advisory IDs are linked below. | Infrastructure/security maintainers must publish patched, tested images. No exception is authorized. |
| SEC-02 | Medium, **FAIL** | Register an isolated account, then submit the same normalized email: first response `201`, duplicate `409` with `Email is already registered`. Existing `test_duplicate_email` reproduces enumeration. Login failures remain generic `401`. | Identity/product maintainers: implement a generic, verified-email enrollment flow and adjust UI/API contracts. Rate limiting limits volume but does not remove this leak. Outstanding; no risk acceptance inferred. |
| SEC-03 | High, remediated in configuration | Deployment previously depended on an operator marker and environment approval without explicitly requiring successful CI for the supplied SHA. | Workflow now requires successful `ci.yml` main push verification for the exact SHA and membership in main history before SSH. Local syntax **PASS**; real GitHub enforcement **NOT VERIFIED**. |
| SEC-04 | Medium operational defect, remediated | Local Docker rejected Grafana's nested dashboard mount below its writable data mount. Initial staging evidence retained privately. | Separate production provisioning and read-only `/etc/grafana/dashboards` mount; development provisioning preserved. Final staging health verified. |
| SEC-05 | High, remediation implemented | Original CI scanned application candidates but omitted the database and monitoring runtimes. Additional scans exposed high/critical findings. | Supporting runtimes now have an additional blocking CI gate; scanner errors also fail the job. Patched immutable upstream candidates were tested. Remaining findings still block. |
| SEC-06 | High, **NOT VERIFIED** release property | Whole-image byte reproducibility is not established: apt repositories and Python/Locust transitive artifacts are not fully snapshot/hash locked. | Release engineering: freeze OS repositories and wheel/tool artifacts, then independently reproduce every target-architecture image. Proxy binary reproducibility alone passes. |

Owners above are accountable roles proposed by this report, not evidence that a
named person accepted risk. Release/security ownership must be formally assigned.

## Image evidence

[Baseline application findings](evidence/m12/baseline-vulnerabilities.json),
[final application findings](evidence/m12/candidate-vulnerabilities.json),
[baseline supporting runtime findings](evidence/m12/support-baseline-vulnerabilities.json),
[final supporting runtime findings](evidence/m12/support-vulnerabilities.json), and
[image identifiers and scan summary](evidence/m12/container-summary.json) enumerate
**every high/critical occurrence**, rather than only selected examples. An empty
fixed version means the scanner has no fix in that distribution; it does not mean
unexploitable. Findings with fixes that remain in supporting binaries require a
vendor update or a separately maintained source rebuild and compatibility tests.
They are not described as unfixable or silently waived.

API/web/backup moved from Bookworm to digest-pinned Trixie. Caddy 2.11.7 was rebuilt
with Go 1.27.2 and a committed module graph containing `golang.org/x/net v0.60.0`.
The proxy's four original high findings disappeared, and the independently rebuilt
binary has the same SHA-256. PostgreSQL stays on major 17, now using a pinned Trixie
candidate; backup client libraries were updated with it. Prometheus, Grafana and
the textfile exporter moved to refreshed pinned upstream images. Existing
development Compose, database and volumes were not upgraded.

[Debian's util-linux advisory](https://security-tracker.debian.org/tracker/CVE-2026-53613)
corroborates a Trixie fix for one original advisory; the
[Go release history](https://go.dev/doc/devel/release) identifies Go 1.27.2 security
fixes. Scanner evidence, not these examples alone, drives the release decision.

All reported packages are present in final runtime images. OS utilities and
libraries have different execution prerequisites; this report does not infer
reachability merely from image presence. Go proxy HTTP/TLS libraries sit on the
request path. Database `gosu` is a privilege-switching utility; production specifies
UID 999, but its Go critical finding is retained. Database `libxml2`
`CVE-2026-6653` has no listed distribution fix and remains critical. Restricted DB
networks, non-root UIDs, dropped capabilities, read-only roots, private storage,
resource limits and parser isolation reduce exposure; they do not satisfy the
zero-high/critical gate.

Build-only dependency assessment: the Go compiler and Caddy module sources stay
in the build stage. Frontend lint tooling stays outside standalone runtime;
`npm audit --omit=dev` reports zero findings. Full npm audit still reports five
high affected nodes in the `eslint-config-next → fast-glob → micromatch → braces`
chain, rooted in `GHSA-vfj7-8cjw-p6xm`. Installed braces 3.0.3 is also the latest
registry release checked; npm suggests an incompatible major framework-config
downgrade. No unsafe downgrade or audit suppression was applied. Python audit
reports zero findings across 44 pinned requirements. Runtime scans report zero
secret findings; this is not proof that every possible secret is absent.

## Application assessment matrix

The final backend suite and browser results are recorded in
[test results](evidence/m12/test-results.json). Reproduction commands appear in
[release acceptance](release-acceptance.md).

| Control | Classification | Reproducible evidence / boundary |
| --- | --- | --- |
| Object authorization and cross-workspace access | PASS | Workspace/document/search/conversation permission matrices; outsider browser account cannot access the workspace. |
| Session fixation, expiry, logout revocation | PASS | `test_login_rotates_session_tokens`, `test_session_rejections`, logout replay and expiration configuration tests. Browser cookie removal tests loss of session, not elapsed server TTL; TTL is exercised by backend tests. |
| CSRF/CORS | PASS | Missing header and hostile origin rejected; allowed origins tested; TLS staging rejects both mutations. |
| Cookies, proxy trust and private-CA TLS | PASS | Secure/HttpOnly/Host-prefix cookies, HSTS, HTTP redirect, no-store; forged proxy request from worker rejected. |
| Public TLS issuance/renewal and host trust | NOT VERIFIED | No public DNS, host or ACME operation was authorized. |
| Password handling and login enumeration | PASS | Argon2 hashing, dummy verification, generic invalid identity/password failures, credential-redaction tests. |
| Registration enumeration | FAIL | SEC-02, duplicated email response differs from successful enrollment. |
| Brute-force / forwarded-address bypass | PASS | Shared PostgreSQL budgets, failed attempts persisted, independent-session limiter and spoofed proxy header tests. Tested cases do not prove resistance to distributed botnets. |
| Upload/path traversal/symlink isolation | PASS | MIME/extension/body budget, unsafe key/root rejection, symlink download escape, checksum corruption and transaction cleanup tests. |
| Unsafe parsing / resource exhaustion | PASS | Synthetic PDF fixtures, actual child timeout/memory termination, page/text limits and worker lease fencing. Corpus fuzzing beyond these fixtures is NOT VERIFIED. |
| SQL injection | PASS | Search injection string remains parameterized data; workspace boundaries and constraints tested. Scope is the implemented API test cases. |
| XSS/CSP | PASS | Inert script-like workspace name in three browser engines; nonce CSP, private HTML/no-store and source display tests. |
| Secrets / insecure errors | PASS | Image secret scans, request validation redaction, provider/parser error sanitization, telemetry privacy fixtures; no customer documents used. |
| Ownership/document/embedding races | PASS | Independent PostgreSQL connections verify lock contention, stale authorization refresh, competing ownership transfer, stale worker fencing and deletion during processing. |

## RAG and AI assessment

| Control | Classification | Evidence |
| --- | --- | --- |
| Document injection/context poisoning fixtures | PASS | `test_malicious_evidence_cannot_control_answer`, bounded context and provider-as-untrusted tests. Offline/mock or MockTransport only. |
| Fabricated IDs and misleading exact quotes | PASS | Citation claim mapping, source/quote spans, unknown reference rejection and qualifier/conflict fixtures. |
| Cross-workspace/deleted/revoked evidence | PASS | Retrieval isolation plus evidence revalidation using independent connections, document deletion and revoked membership. |
| Contradictions, provider failures/timeouts and input/context budgets | PASS | Abstention, retries, permanent errors, wall-clock cancellation, capacity and token/context limit fixtures. |
| Sensitive-data disclosure in tested paths | PASS | Private question/key redaction and authorization fixtures; deterministic mocked transports. |
| Offline gold evaluation | PASS | 68 units; thresholds passed. One known `backup-answer` false abstention is retained, 17/18 RAG cases correct. |
| Hosted model prompt-injection resistance / semantic support | NOT VERIFIED | No hosted provider was called. Exact citation validity and lexical gold checks do not establish entailment or hosted model quality. |

Evaluation reports, including the failed case and full metrics, are preserved in
[evaluation](evidence/m12/evaluation/). Gold citation reference/quote support was
1.0, measured unsupported-claim frequency was 0.0 in this synthetic fixture set,
and isolation guards passed. These are scoped observations, not universal safety
or accuracy guarantees. The similarity thresholds and release gates were not
lowered to obtain a pass.
