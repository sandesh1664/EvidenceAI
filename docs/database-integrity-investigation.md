# Development database integrity investigation — Milestone 12.5

**Attribution: NOT VERIFIED. Final whole-database equality: FAIL. Original-row/storage preservation: PASS.** Baseline `932f75f`,
2026-10-20 Asia/Dubai. No existing row was deleted, updated or repaired.

The historical additions reside in database **`evidenceai`**, schema **`public`**:
`auth_rate_limits` increased4→12 and `registration_intents`0→3. These are the
only schemas containing those tables in the inspected development database.
At initial 12.5 inspection, complete row hashes matched the private 12.4
after-snapshot for both tables; the later one-row delta is documented below.
All four original limiter rows still match the original whole-row hash as an
ordered subset. Every historical added record remains present. See
[read-only investigation](evidence/m125/database-investigation.json).

| Record metadata | Observed UTC timestamp / aggregate |
| --- | --- |
| Intent1 creation / expiration |2026-10-19 21:20:24.045362 /21:50:24.045793 |
| Intent2 creation / expiration |2026-10-19 21:22:41.538767 /21:52:41.539616 |
| Intent3 creation / expiration |2026-10-19 21:25:36.407172 /21:55:36.407872 |
| Added limiter time buckets |21:20:00: five rows/eight attempts;21:25:00: three rows/four attempts |
| Limiter actual creation timestamps | NOT VERIFIED: this table stores window start and attempts, not insertion time |

Ordinal labels are chronological positions, not published record IDs. Expiration
is approximately1800seconds after creation; the small fractional differences
reflect separately evaluated database times. Private recipients, token/browser
hashes, password hashes, keys, IDs and document paths are withheld.

The source hashes limiter keys as SHA256(action + ':' + client). Five added keys
match known loopback auth-route actions; three match the recipient-specific action
for the existing intents. None matches the default TestClient client label.
This corroborates the kind of application activity, **not its originating process
or person**. [Correlation](evidence/m125/database-correlation.json).
The retained12.4 pytest run ends21:14:35.296565 UTC, before all three intents;
retained browser log events span21:14:14–21:15:32 UTC. Log bounds are not complete
process-lifetime evidence. The previous investigation also found zero recipient
matches to its owned staging/browser/unit identities. None of these facts proves
that every possible test or API process was harmless or identifies the writer.

At inspection PostgreSQL showed only the investigator's active database session;
no historical API/worker connection trail was available. Host process-name and
Docker-service inspection found no running development API or worker at that
point. `log_statement=none`, connection/disconnection logging off and
`track_commit_timestamp=off` prevent recovering historical statement/actor
attribution from those facilities. Do not enable payload/statement logging on
private registration data merely to reconstruct this event. Historical request
bodies, recipient values or token material were not exported. Retained evidence
cannot establish who inserted the eleven rows. Attribution remains NOT VERIFIED;
no actor or causal link to a specific test run is asserted.

## Isolation remediation and verification

Previously pytest and browser fixtures used scratch schemas inside the development
database, with development credentials. ORM schema translation did not set the
SQL search path on concurrency and browser connections; unqualified/raw queries
could reach `public`. That is a real design weakness, not proof that it caused the
historical additions.

The shared policy in `apps/api/app/db/disposable_database.py` (re-exported by
`infra/testing/database_guard.py`) now requires explicit
`EVIDENCEAI_TEST_DATABASE_URL` before either entry point imports application code.
It accepts only PostgreSQL/psycopg, loopback host, explicit port, the strict
`evidenceai_test_<32 hex>` database name, and no URL query options. Missing or unsafe
configuration fails before constructing an application engine. The test process
activates only that URL, including indirect engine factories and worker settings.
Offline retrieval/RAG evaluation functions also require the explicit disposable
URL to match both settings and the cached engine before creating schemas.
Concurrency/browser scratch engines now set both schema translation and SQL search
path. `public` is the empty migration/pgvector baseline of the **disposable** DB.

`infra/testing/run_isolated.py` creates a uniquely owned, loopback-bound PostgreSQL
container with tmpfs, no development volume/storage mounts and an immutable local
image ID. It migrates the empty DB, passes credentials only through private
mode0600 temporary environment material/child environment, and removes only its
own label-verified container. Existing Docker volumes are never reset. Cleanup
checks require zero scratch schemas and zero public users/intents/limiter rows.
CI uses its separately owned service with an explicit synthetic test DB; only its
database configuration changed, with security/release gates retained.

Name/URL validation is a guard, not an ownership proof for arbitrarily supplied
manual URLs. Prefer the owned-container runner; independently verify any manual
fixture. No database role or permission on the real development service changed.
The scratch schemas share only disposable data and extension definitions.

Observed final verification: **662 backend tests PASS**, including nine new guard,
raw-SQL and concurrency checks; the separate final isolation run passes all nine.
Both entry points refuse missing configuration (pytest exit4; browser exit 1).
Backend/browser/isolation owned containers are removed, no scratch schemas remain,
and their public fixture tables stay empty. Initial harness failures and a browser
connection failure are retained separately, not counted as passes.

An earlier12.5 comparison passed all 16 table hashes/counts and storage metadata.
The **final** comparison failed whole-DB equality: one more limiter row appeared,
12→13, in the22:15 UTC bucket with one attempt. Its key matches the source-defined
loopback login action. This is a bucket/action classification, not an insertion
timestamp or proof of writer. All 12 pre-existing limiter rows still match the
before hash as an ordered subset; the other 15 whole tables, revision and private
storage bytes/metadata are identical. The three historical intents are intact.
Only the investigator's current connection was visible; no development API/worker
was found in the final host/Docker name inventory. Historical connection/statement
auditing remains unavailable. The new row's attribution is NOT VERIFIED as well.

No row was removed or rewritten. Do not claim current whole-state preservation
PASS based on the earlier result. Both [earlier PASS](evidence/m125/data-preservation.json)
and [final FAIL](evidence/m125/data-preservation-final.json) remain intact.
[Final subset/metadata analysis](evidence/m125/database-final-delta.json) proves
original-row preservation, not who made the addition or whether a transient write
was reverted. File access times are outside the comparison. Test-container cleanup
and separate URLs demonstrate the tested boundaries but cannot alone prove the
writer of this development record. Development service roles/settings were not
changed and processes were not killed to force a pass.

The original four normalized evidence streams were separately recovered and matched
to the preserved manifest. See [recovery](evidence/m125/historical-recovery.json)
and the [verified 69-file content snapshot](evidence/m125/historical-snapshot-recovery.json).
The historical normalized files/manifest were not overwritten; complete historical
custody timestamps remain NOT VERIFIED. [Fixture guide](../infra/testing/README.md).

Further attribution requires authorized, existing redacted access/audit evidence
from the relevant host/process owner. Preserve the eleven records and restrict any
future audit to request IDs, time, operation and application identity; exclude
recipients, credentials, verification tokens and SQL payloads. No destructive
cleanup, fabricated attribution or release exception is justified.
