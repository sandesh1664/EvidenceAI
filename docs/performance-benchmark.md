# Milestone 12 performance benchmark

**PASS for the bounded local workload only.** Tested source: baseline
`02462040fec9eea53c596618c32b09cb694d60ee` plus the uncommitted
[source manifest](evidence/m12/source-manifest.json). Date: 2026-10-19 UTC.
[Raw final measurements](evidence/m12/performance.json) retain request counters,
latencies, database statistics and container samples. The workload is implemented
in `infra/load/locustfile.py`, using Locust 2.43.1.

## Acceptance defined before measurement

`infra/load/thresholds.json` defines five users, one user/second ramp, 30 seconds,
0.5–1 second waits between task groups; at least 100 requests, error ratio ≤1%,
p95 ≤2,000 ms, p99 ≤5,000 ms and queue drain ≤60 seconds. Proposed local recovery
limit is 120 seconds. No threshold was loosened after a failure.

The final run observed **326 requests, 0 errors,
10.946 requests/second**, p50 **8 ms**, p95
**27 ms**, p99 **65 ms**. Runner duration including teardown:
30.422 seconds. Queue-drain check: 0.895 seconds;
zero queued/running or failed document/embedding jobs at the final sample.

| Endpoint group | Requests | Errors | p50 ms | p95 ms | p99 ms | Requests/s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| authentication/login | 5 | 0 | 77 | 79 | 79 | 0.168 |
| vector/search | 50 | 0 | 10 | 20 | 30 | 1.679 |
| authentication/me | 62 | 0 | 9 | 13 | 14 | 2.082 |
| document/upload | 25 | 0 | 19 | 35 | 38 | 0.839 |
| workspace/list | 33 | 0 | 8 | 14 | 14 | 1.108 |
| workspace/create | 33 | 0 | 6 | 9 | 11 | 1.108 |
| workspace/read | 33 | 0 | 4 | 10 | 11 | 1.108 |
| workspace/update | 33 | 0 | 5 | 12 | 13 | 1.108 |
| workspace/delete | 33 | 0 | 5 | 9 | 9 | 1.108 |
| rag/mock-answer | 19 | 0 | 23 | 36 | 36 | 0.638 |
| Aggregated | 326 | 0 | 8 | 27 | 65 | 10.946 |

Percentiles use Locust's rounded response-time histogram. Endpoint samples are
small (login has only five observations); high-percentile estimates do not
establish population tail latency. Aggregate has over 100 requests. A shutdown
hook exports final in-memory counters because periodic CSV may lag the last
requests. [Final counters](evidence/m12/load-final-stats.json) are authoritative.

## Environment and measured resources

Host: macOS 26.5.1, ARM64; Docker Desktop Linux/ARM64, Docker server 29.9.1.
Docker VM advertises 10 CPUs and
8,319,504,384 bytes memory. The exact physical CPU model
was unavailable through the sandbox. Locust ran on the host, outside containers.
PostgreSQL is 17.11 with pgvector 0.8.7. API/worker Python is 3.14.6; source/runtime
identifiers are in [container evidence](evidence/m12/container-summary.json).

Production resource limits used by the fixture: DB 1.5 CPUs/1 GiB; API and worker
1.5 CPUs/1 GiB each; web 1 CPU/512 MiB; proxy 0.5 CPU/256 MiB; Prometheus 512 MiB,
Grafana 384 MiB, exporter 64 MiB. API/worker pools are five connections plus three
overflow each; PostgreSQL max_connections is 80. Queue/DB/storage belong only to
the unique staging project. Database storage uses bounded tmpfs and originals
use disposable host bind mounts. This is not a physical production disk benchmark.

7 Docker stats/database samples were collected during load. CPU below
is the highest **observed sample**, not an instrumented peak. Memory is the
concurrent sample; block I/O is the last cumulative container snapshot, not a
benchmark-only delta. Docker CPU percentage can exceed 100% for multicore use.

| Service | Highest sampled CPU | Memory at that sample | Last cumulative block I/O |
| --- | ---: | --- | --- |
| api | 15.76% | 89.32MiB / 1GiB | 2.33MB / 0B |
| db | 4.38% | 82.95MiB / 1GiB | 0B / 0B |
| grafana | 1.03% | 247.5MiB / 384MiB | 733kB / 0B |
| prometheus | 0.39% | 44.43MiB / 512MiB | 11.6MB / 0B |
| proxy | 1.42% | 15.25MiB / 256MiB | 0B / 0B |
| web | 13.62% | 50.89MiB / 512MiB | 0B / 0B |
| worker | 23.08% | 76.28MiB / 1GiB | 0B / 0B |
| worker-exporter | 0.96% | 5.551MiB / 64MiB | 8.19kB / 0B |

Sampled total PostgreSQL connections peaked at **10 of 80**, including
fixture application, worker, monitoring and diagnostic connections. Sampling does
not establish an absolute peak. Before/after/drained `pg_stat_database` counters
in the JSON record block reads/cache hits, tuples and temporary I/O; no temporary
files/bytes were recorded at the drained sample. OS page cache and tmpfs prevent
interpreting these as physical storage throughput.

## Scope and retained failures

The mixed workload measured authenticated reads, five real password logins,
workspace create/read/update/delete, multipart uploads, real background extraction
and indexing, pgvector search and offline mock RAG. It used a small synthetic text
corpus with fake 128-dimensional embeddings and the deterministic mock LLM.
Worker recovery is separately measured in the recovery drill. Provider timeout,
wall-clock cancellation and backpressure are deterministic backend fixture tests;
no hosted-provider timeout rate or token-generation throughput was measured.

The initial workload reused identical upload bytes and received the API's intended
409 duplicate-content responses. Its failed error threshold is retained in
[failed fixture measurements](evidence/m12/load-duplicate-fixture-failure.json).
Unique synthetic content corrected the workload; duplicate protection was not
removed. Subsequent runs were needed to validate final counters, recovery guards
and rollback; the final run is reported here.

## Reproduce and next capacity work

From the repository root, build `evidenceai-{api,web,backup,proxy}:m12` using the
four Dockerfiles, then:

```sh
python3 -m venv /tmp/evidenceai-m12-load
/tmp/evidenceai-m12-load/bin/pip install -r infra/load/requirements.txt
EVIDENCEAI_ACCEPTANCE=1 python3 infra/scripts/smoke.py
```

The harness provisions its own DB/tmpfs, secrets and private CA, verifies TLS and
runs the guarded loopback workload. It refuses arbitrary public targets. It
cleans only its generated project and bind directories, never development data.
Detailed commands are in [release acceptance](release-acceptance.md).

No performance optimization or vector-index change was justified by this tiny
workload, and no migration was added. Sustained login pressure, large documents,
large vector corpora, varied languages, hosted-model generation, soak tests,
saturation/failure envelopes, real disk/offsite I/O and Linux AMD64 production
capacity are **NOT VERIFIED**. Run those on an isolated representative deployment
before sizing or promising user concurrency. These results support only the
specific five-user experiment above.
