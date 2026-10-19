# EvidenceAI web

The integrated Next.js App Router application for the existing FastAPI backend.

```sh
npm ci
# New checkout only: copy .env.example to .env.local and set the API origin.
npm run dev
```

Open http://localhost:3000 with FastAPI on http://localhost:8000. Backend development
settings must trust that exact frontend origin and explicitly allow insecure local HTTP.
The backend retains its existing cookie sessions, CSRF, workspace permissions and workers.
No session token or API key belongs in frontend storage or NEXT_PUBLIC_ variables.

```sh
npm run lint
npx tsc --noEmit
npm run build
npm test
npx playwright install chromium
npm run test:e2e
npm audit
npm audit --omit=dev
```

Playwright runs a production frontend and the real API/workers with a generated local
PostgreSQL schema and temporary private storage. It requires the existing backend .venv
and local PostgreSQL/pgvector; it never uses public data as fixtures. It refuses production
or remote database configurations, blocks paid providers, and cleans up on normal shutdown.
Tests use ports 3100/18000; keep them free. Run a normal build with your actual API origin
after E2E before npm start, because test builds embed their isolated API origin.

See [frontend architecture](../../docs/frontend-architecture.md) for routes, test coverage,
cookie/CSP/cache integration, known dependency findings and manual verification.
