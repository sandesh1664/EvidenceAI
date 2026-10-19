# Evaluation framework

From `apps/api`, with the local PostgreSQL/pgvector database available:

```sh
.venv/bin/python -m app.evaluate --repeat 3
.venv/bin/python -m app.evaluate --compare evaluation/reports/PRIOR.json --repeat 3
.venv/bin/python -m app.evaluate --thresholds evaluation/thresholds.json --output-dir evaluation/reports
```

The v2 runner creates exclusively named timestamp/UUID JSON files; it never overwrites
history. It exits 1 on configured regression failures and records their details. Comparison
requires identical evaluation version, provider list and dataset/evaluator fingerprints.
Metric deltas are current minus previous, with absolute minima/maxima and optional
maximum quality drops. Missing or nonfinite required metrics fail closed. The legacy
`evaluate_retrieval` / `evaluate_rag` commands retain their original explicit-output
behavior for compatibility; use the v2 runner for historical tracking and CI.

## Data and scope

Only generated scratch schemas (`eval_retrieval_*`, `eval_rag_*`) contain fixtures; they
are dropped in finally blocks. The runner never loads customer documents or requires
hosted-provider credentials. Fake/mock provider configuration is explicit regardless of
the developer .env. Keep evaluation separate from normal API traffic and do not run it
against production. Hard process termination can leave a scratch schema: inspect ownership
before removing only the exact generated schema. Never drop public or use broad wildcard
cleanup. The test suite separately owns a `test_suite_*` schema so global worker queries
cannot select development records.

The retrieval dataset has eight labeled queries and synthetic evidence labels in
`evaluation/retrieval.json`. Each case reports expected and returned document labels,
latency, K and profile settings. The runner indexes the same corpus with real PostgreSQL
vectors using fake-hash-v1 at 128 and 256 dimensions. It measures recall@2, precision@2,
MRR, binary nDCG@2, empty-result rate, cross-workspace/foreign-filter rejection and exact
single-document filtering. Positive filter checks query the selected document's text and
require a nonempty result exclusively from that document. Repetitions recreate isolated
schemas; their identical labels are repeated timing observations, not new independent
quality examples or hosted-model comparisons.

The original RAG dataset has 13 cases; extended v2 evaluation adds a misleading
planned-versus-approved numerical passage, provider outage, provider timeout, retrieval
outage and unsupported generated numerical claim. Two additional guards exercise real
foreign-workspace access rejection and a source deleted through the document service.
Existing cases cover injection, invented citation IDs, unsupported quoted claims,
contradictions, missing/ambiguous evidence and absent numeric qualifiers. Generation
fault engines intentionally bypass the normal adapter to test RAG error/validation
boundaries; provider-attempt metrics are tested separately with actual adapters.

Exact expected status/claim matching is deterministic correctness against hand-authored
gold labels. Citation-reference validity checks actual source membership, workspace,
allowed document filters and exact quote presence. Gold support quality compares emitted
claims to the labeled source. Unsupported frequency checks emitted quoted claims only.
A refused answer emits no claim and does not inflate citation quality; denominators and
claim/citation counts are reported separately. Semantic entailment, paraphrase correctness
and general truth are **unverified**. These small lexical test-double fixtures provide no
hosted-model accuracy, representative security coverage or independent certification.

## Report contract and observed run

Reports contain evaluation version, dataset/evaluator SHA256 fingerprints, UTC timestamp,
provider identifiers, scored sample count, per-case outcomes, aggregate metrics, known
failure cases, latency sample counts, regression failures and optional comparison deltas.
`sample_count` counts retrieval queries, RAG cases and the two RAG authorization/deletion
guards. Separate retrieval isolation/filter assertions are counted inside profile reports.
`semantic_judgment` stays `unverified`.

The committed Milestone 10 sample (`milestone-10-evaluation.json`) used three repetitions:
48 retrieval timings (eight queries × two profiles × three runs), 18 RAG cases and two
guards: **68 scored units**. Both profiles produced recall/precision@2 **0.9375**, MRR
**1.0**, nDCG@2 **0.951643**, empty rate **0**, isolation/filter correctness **1.0**.
RAG matched **17/18** exact labels, emitted **five** claims/citations with valid references
and gold-source matches, and detected **6/6** insufficiency cases. Both guards passed.
The backup-region case remains a known false abstention. Every configured threshold passed.

The report's top-level latency summaries gate p95 at 20 observations and p99 at 100.
Each retrieval profile has 24 observations, so p95 is available; 18 RAG timings do not
justify p95, and no group justifies p99. Legacy embedded reports retain earlier percentile
fields for compatibility; use the sample-gated top-level summaries when reporting results.
All timings are sequential local synthetic measurements, not production SLOs or load tests.

Keep full local history in ignored `evaluation/reports/`; retain CI artifacts for 30 days
as an operator policy and intentionally select release baseline artifacts for Git. The
application does not automatically delete reports. Do not place real questions, source
excerpts or customer data into fixtures or evaluation artifacts. Introduce an explicitly
consented, access-controlled corpus and qualified human/semantic review in a later milestone.
