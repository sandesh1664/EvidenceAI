# Disposable database tests

Pytest, the browser fixture and offline evaluation functions refuse to inherit the development database from
`.env`. Use the API virtualenv with `run_isolated.py`, which creates a unique
loopback PostgreSQL/pgvector container using tmpfs, migrates its empty database,
sets `EVIDENCEAI_TEST_DATABASE_URL` only for the child process, checks cleanup, and
removes only the container bearing its generated ownership label. The locally
reviewed `evidenceai-database:m121` image must exist; its immutable ID is resolved
before startup. The runner uses no development volumes or private-storage mounts.

```sh
apps/api/.venv/bin/python infra/testing/run_isolated.py -- apps/api/.venv/bin/python -m pytest apps/api/tests -q
apps/api/.venv/bin/python infra/testing/run_isolated.py -- npm --prefix apps/web run test:e2e
```

Playwright additionally requires its installed browser binaries; set
`PLAYWRIGHT_BROWSERS_PATH` to their installation directory when necessary.
Generated database names must match `evidenceai_test_` plus32 hexadecimal digits,
use a loopback host and explicit port, and contain no connection query options.
Manually setting the variable is reserved for a separately provisioned disposable
service. Name validation is a guard, not proof that an arbitrary external database
is owned or empty. CI uses its job-owned PostgreSQL service and an explicit
synthetic test database name. Credentials in that workflow are synthetic only.

All test schemas live inside the disposable database. `public` contains pgvector
and the empty migration baseline; scratch connections set both ORM translation
and SQL search path. The runner fails if scratch schemas remain or users,
registration intents or limiter rows leaked into the empty public baseline.
Tests must not run concurrently against a manually shared service unless each run
has its own database. The runner gives each invocation its own container/database.

Read-only development comparisons are available separately:

```sh
PYTHONPATH=apps/api apps/api/.venv/bin/python infra/testing/preservation.py --snapshot /tmp/owned-private-before.json
# Run isolated tests; never point their explicit URL at development.
PYTHONPATH=apps/api apps/api/.venv/bin/python infra/testing/preservation.py --compare /tmp/owned-private-before.json --report /tmp/preservation-result.json
```

Snapshots include private storage paths and hashes: keep them outside Git, mode
0600, and do not upload them. Snapshot creation refuses to overwrite an existing
file. Comparison reports expose aggregate results only. A fresh comparison cannot
retroactively attribute historical changes or restore missing original log bytes.

The shared guard policy is in `apps/api/app/db/disposable_database.py`; offline evaluation
also checks the configured and cached-engine URL against the explicit test URL.
Run `python -m app.evaluate --repeat 3` inside an owned runner command, never
against development. Cleanup includes `eval_rag_` and `eval_retrieval_` schemas.
