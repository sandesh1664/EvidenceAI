# EvidenceAI web application — Milestone 09

The existing Next.js 16.4.2 / React 19.3 / strict TypeScript app now connects to the existing
FastAPI APIs. No backend source, authentication system, migration, provider configuration or
application records were replaced. The implementation uses the installed Next.js App Router,
client-component, testing and CSP guides in `apps/web/node_modules/next/dist/docs/`, as required
by `apps/web/AGENTS.md`. Sites guidance was applied in local-only mode; nothing was published.

## Routes and design

| Route                            | Workflow                                                                                                                                                          |
| -------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| /                                | Redirect to /workspaces                                                                                                                                           |
| /register, /login                | Validated account forms; registration followed by existing login/session flow                                                                                     |
| /workspaces                      | Paginated accessible projects, create workspace, switch projects                                                                                                  |
| /workspaces/[workspaceId]        | Workspace overview, loaded-document extraction counts, latest-created saved conversations, research/upload shortcuts, permitted rename/delete                     |
| …/members                        | Paginated UUID-based member directory; add registered users, permitted role changes/removals, owner-only transfer confirmation                                    |
| …/documents                      | Drag/drop or file picker, paginated library, loaded-page filename filter, extraction/index state refresh, original download, permitted retry/index/rebuild/delete |
| …/research                       | Stateless /ask, current document filters/retrieval cap, validated answer states and source quotations                                                             |
| …/search                         | Current workspace semantic retrieval, document filters, ranked passages and explicit cosine similarity scores                                                     |
| …/conversations                  | Private cursor-paginated history, create conversation, include archived                                                                                           |
| …/conversations/[conversationId] | Ordered paginated messages, contextual follow-ups, idempotent retries, snapshots, rename/archive/restore/delete                                                   |
| /settings                        | Existing profile fields/account UUID, theme, authenticated API connectivity, honest provider-configuration limitations                                            |

The visual system uses a deep-green navigation rail, pale neutral surfaces and a restrained
lime action color. System fonts keep builds offline and avoid external font requests. CSS
variables implement light/dark/system themes; mobile navigation uses an overlay, desktop
navigation can collapse, and shorter sidebars scroll within their dark background. Cards,
forms, badges and states share primitives. Responsive layouts cover desktop/tablet/mobile,
visible focus, skip navigation, semantic forms, native modal confirmation dialogs with unique
label IDs, reduced motion and plain-text excerpts. Decorative source graphics use CSS, not
fabricated charts or operational data. No copied third-party product assets are used.

## Components and state

`src/types/api.ts` mirrors current Pydantic contracts. `src/lib/api/client.ts` owns typed calls,
CSRF/cookie/cache options, safe errors, downloads and mutation invalidation. `src/lib/auth/`
owns current-user/session lifecycle, not tokens. Feature modules live in components/auth,
layout, workspaces, documents, chat and citations. App Router pages compose these components;
workspace layouts scope content and permissions. Native React state and a small resource hook
are sufficient; no extra authentication/data framework or parallel API was introduced.

Private data is fetched **in the browser**, after the real `/api/v1/auth/me` check. Private
server HTML contains only generic loading UI, no workspace names, messages or source text.
Next.js server components never fetch authenticated user data. A request-specific nonce and
`headers()` make document responses dynamic, with private/no-store headers. No `use cache`,
static generation of private payloads, service worker or persistent offline data cache is used.

The resource hook keeps a 15-second in-memory cache keyed by account ID and full API path,
which includes workspace ID and pagination. Successful mutations invalidate active reads;
manual refresh bypasses cached results. Explicit refresh/mutation invalidation can make a one-off read while hidden; periodic polling remains paused. Changing keys immediately hides the previous payload,
aborts obsolete requests and ignores late responses. Logout/401 clears cached data and
unmounts private content. BroadcastChannel communicates account changes between tabs without
sending credentials or private data. Browser storage contains only `evidenceai:theme`.

Visible document lists refresh every 10 seconds, index statuses every 12, workspace overview
extraction counts every 15, and conversation messages every 5. Polling skips hidden pages and
stops on unmount; visibility restoration refreshes. Background requests are not left running
for inactive routes. Existing index/result states are shown without invented percentages.

## API integration and permissions

The browser uses exact existing paths, including trailing slashes for workspace/document
collections, to avoid redirects. Core API families:

- `/api/v1/auth/{register,login,logout,me}`
- `/api/v1/workspaces/` and `/{id}`; `/members`, `/members/{user_id}`, `/transfer-ownership`
- `/api/v1/workspaces/{id}/documents/`, `/{document_id}`, `/download`, `/retry`, `/index`, `/index/retry`
- `/api/v1/workspaces/{id}/ask`, `/search`
- `/api/v1/workspaces/{id}/conversations`, `/{conversation_id}`, `/messages`

The backend remains the authorization boundary. Workspace owner/admin/member UI actions
mirror the services: only managers upload/delete/retry/index; admins manage ordinary members;
owners manage admins and transfer/delete. Own-role lookup uses workspace owner metadata or
pages the existing member API until the current user is found. Revocation/stale UI still fails
through backend checks. Conversation routes stay private to their creator, regardless of a
workspace administrative role. No UI-only protection substitutes for server authorization.

Member APIs expose UUIDs/roles, not names/emails or a lookup directory. Adding a registered
user therefore takes their account UUID (shown in Settings); no invitation/email-search UI is
invented. Profile is read-only because no account-update API exists. Provider configuration
is also not exposed; Settings says so rather than guessing availability or offering fake
model controls. Connectivity uses the authenticated `/auth/me` endpoint: the existing public
health endpoint lacks cross-origin CORS headers, and its liveness would not prove worker or
provider readiness anyway. The backend is unchanged.

Workspaces/documents/members use supported limit/offset pagination. Lists without a total can
show an empty final page when the preceding page exactly fills the limit; Previous remains
available. The switcher shows the first 100 accessible workspaces; the full Workspaces page
is paginated. Filename filtering affects only the loaded library page; full-text passage
lookup uses semantic search. Dashboard counts explicitly describe the first 100 loaded
documents and extraction state, not global totals or indexed-document counts. Conversation
lists say latest-created; last_activity is displayed separately, matching the actual API
ordering. Document selection pages retain selections across pages, capped at 50; null means
all permitted documents and [] explicitly means no evidence.

## Sessions, CSRF, production and errors

Direct browser-to-API requests were chosen because the backend already implements credentialed
CORS and trusted-Origin CSRF. Every API call uses credentials=include and cache=no-store;
mutations include X-CSRF-Protection: 1. JSON bodies set Content-Type; multipart requests let
the browser choose a boundary. The browser supplies Origin; JavaScript does not forge it.
Redirects are rejected. Downloads fetch with cookies, create a temporary Blob download URL,
and revoke it; there is no public document proxy or unauthenticated link.

Development uses http://localhost:3000 and http://localhost:8000, backend APP_ENV=development,
AUTH_ALLOW_INSECURE_HTTP=true and TRUSTED_FRONTEND_ORIGINS=["http://localhost:3000"]. Use the
same hostname consistently; localhost and 127.0.0.1 have different cookie/site behavior.

Production must use HTTPS on the app and API, preferably same-site hosts such as
app.example.com/api.example.com (or an explicitly routed same-origin API). Set the exact
frontend HTTPS origin in backend TRUSTED_FRONTEND_ORIGINS and leave insecure cookies disabled.
The backend then sets its existing HttpOnly/Secure/__Host- session cookie. Tokens never enter
JavaScript, localStorage or a separate Next session system. Unrelated cross-site deployments
are not supported by the backend's SameSite=Lax contract; do not weaken cookies to work around
that. Configure the existing backend/ingress to report HTTPS accurately behind trusted proxies;
this implementation does not blindly trust forwarded headers. Set HSTS/TLS policy at ingress.

Central API errors handle 400/401/403/404/409/413/422/429/5xx. Safe backend string details are
shown for client errors; validation structures are not stringified because they can contain
submitted inputs. Server/network errors use generic text; payloads are never logged. A 401
clears private data and opens login. Normal failures show retry affordances where safe.
Research displays actual RAG error envelopes (including provider disabled/timeout) even on
HTTP 503/504. No model is called automatically for demonstration or test data.

## Documents, answers and history

| API state                                  | Presentation                                                                   |
| ------------------------------------------ | ------------------------------------------------------------------------------ |
| Document pending / processing              | Pending extraction / Processing                                                |
| Document completed / failed                | Extraction complete / Extraction failed with safe actionable error             |
| Index not_indexed / queued / running       | Not indexed / Pending indexing / Indexing                                      |
| Index done                                 | Indexed only when indexed_chunks == total_chunks; otherwise Index job finished |
| Index failed                               | Indexing failed, safe reason and server-enforced retry/rebuild actions         |
| Ask insufficient_evidence                  | Explicit abstention, guidance to refine question/check indexing                |
| Ask retrieval_unavailable / provider_error | Explicit failure; disabled reason explains operator configuration              |
| Assistant pending / completed / failed     | No draft shown; terminal outcomes use the saved status, not only HTTP success  |

Client upload prechecks accept .pdf/.txt/.md, nonempty files and default <=20 MiB. The optional
public upload limit only adjusts the client precheck; actual backend limits/content validation
win. Multipart uploads are sequential; a partial batch failure tells the user earlier files
may exist. The backend returns 202, then real workers handle extraction/indexing. No percentage
or completion estimate is fabricated. Retry budgets are not exposed; controls request a retry
for eligible states and show backend conflicts when the deployment's attempt limit is exhausted.
The default-three-attempt hint is explicitly qualified as a default, not an API guarantee.

Answer claims render as escaped plain text with clickable server citation IDs and filename
chips. Source panels show quote, filename, page/section and an authorized download action.
Saved snapshots label deleted originals or unavailable chunks; historical quotation remains
readable and is not presented as renewed evidence. Nothing uses dangerouslySetInnerHTML or
untrusted Markdown/HTML. Scores are labeled similarity, not confidence. Mock LLM and fake
embedding profiles are labeled offline; an observed model identifier is not a provider
readiness claim. Lexical validation is never described as semantic proof. No SSE endpoint is
claimed or requested; answers are shown only after validation.

Conversation POST returns HTTP 201 even for a saved failed/insufficient answer; the UI reads
answer_status/generation_status/reason. New submissions create a UUID idempotency key and freeze
the exact question, filters and retrieval limit for retry. Duplicate clicks are locked out.
On ambiguous transport/storage failure, the composer stays frozen with **Retry same submission**;
it reuses the same key/body instead of generating another intended turn. Pending 202 replays
show pending history, disable new turns and use GET polling. This recovery state is in memory,
not browser storage; navigating away loses the local retry key, while server history remains.
Inspect history after returning before creating another copy. A server pending lease recovers
through normal message reads/submissions. Current-turn filters are explicit and not inherited.

History pages order by sequence ascending and use after_sequence; previous-page positions are
kept in memory. The latest submitted turn can also be displayed after the current history page
so it is visible immediately, with an explicit gap/page notice when older pages remain. Rename,
archive/restore and confirmed deletion use real APIs. Deleting a source does not erase saved
quotations; the document confirmation explains this. Conversation deletion confirmation explains
that its messages/snapshots/idempotency records are erased while original documents remain.

## Security headers

`src/proxy.ts` generates a fresh nonce, forwards the CSP to SSR and adds it to the response.
Next attaches nonces to its scripts. Production script-src uses nonce + strict-dynamic with
no unsafe-inline/eval; development permits unsafe-eval for Next's debugger. Styles currently
allow unsafe-inline for framework/CSS interoperability; scripts do not. Other directives
restrict connect-src to self/configured API, object-src none, base-uri self, form-action self,
frame-ancestors none, local fonts/images. No external analytics, fonts or user-directed URL
fetcher is added. next.config adds nosniff, frame denial, restrictive referrer and device-feature
policies. Private document responses are no-store; static public bundles contain no private
payloads or backend secrets. A nonce policy is defense in depth, not independent XSS verification.

## Development and test commands

```sh
# Existing backend setup, after reviewing/applying its existing migration:
cd apps/api
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-proxy-headers
# In separate terminals, when document/embedding work is enabled:
.venv/bin/python -m app.document_worker

# Frontend (use Node 26 as verified here):
cd apps/web
npm ci
# For a new checkout only, copy .env.example to .env.local; edit the origin as needed.
npm run dev
# http://localhost:3000
npm run lint
npx tsc --noEmit
npm run build
npm test
npx playwright install chromium
npm run test:e2e
npm audit
npm audit --omit=dev
```

Check the worker's actual CLI in `docs/document-processing.md`; one worker services its
configured document/embedding profiles. Provider defaults remain disabled. For offline local
research, deliberately configure the existing backend fake embeddings/mock LLM as described in
the RAG/retrieval guides; tests do that only inside isolated configuration. This milestone does
not edit apps/api/.env. Browser-visible variables are NEXT_PUBLIC_API_BASE_URL (origin only)
and NEXT_PUBLIC_UPLOAD_MAX_BYTES (client precheck). Never put any secret in NEXT_PUBLIC_.

Vitest/Testing Library/jsdom tests use deterministic mocked fetch, covering forms, session
expiry, CSRF/credentials, permissions, uploads/failures/status mapping, filters/search, sources,
RAG failure/abstention, conversation history/idempotent retry/pagination, themes, account-scoped
cache invalidation, cancellation, hidden polling and late-response isolation.

Playwright starts **the real existing FastAPI app and workers** on 127.0.0.1:18000 using
`e2e/server.py`, plus a production Next build/start on localhost:3100. EVIDENCEAI_E2E=1 is
required; the harness rejects non-loopback or production/staging database configurations.
It creates a generated `e2e_web_<UUID>` schema via schema_translate_map, a resolved private
temporary storage directory, fresh registered accounts and explicit fake/mock providers with
no API key. Live outbound httpx transports are blocked. Existing public rows are never used
as fixtures or cleaned up. On normal teardown the schema/storage are removed and owned servers
stop. Existing servers are not reused. Abrupt SIGKILL can leave isolated resources needing
reviewed cleanup. Do not point tests at a deployed API or change them to use developer records.

Browser tests cover full upload→worker→index→search→RAG→conversation/follow-up/snapshot flow,
real cookie/CSRF/origin failures, session expiry, private server HTML, role controls/ownership
transfer/deletion, mobile navigation, theme reload, cross-user denial, keyboard focus and axe
WCAG 2 A/AA/2.1 AA scans of representative desktop/mobile pages. Automated accessibility scans
are not a complete screen-reader/user audit. Chromium is the executed browser; other engines
remain unverified. Reports/screenshots/traces are gitignored and contain synthetic test data.
E2E builds use localhost:18000 in .next; run a normal build with your actual API origin after
E2E before manually running npm start. Never run another dev/build against the same .next
while a browser suite is running.

## Dependency assessment

On 2026-10-19, npm audit reports **5 high, 0 moderate/low/critical**, all in the development
lint chain: eslint-config-next → @next/eslint-plugin-next → fast-glob → micromatch → braces
3.0.3. The underlying advisory is
[GHSA-vfj7-8cjw-p6xm / CVE-2026-93687](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm):
recursive pattern processing can exhaust the stack; affected versions <=3.0.3 and no patch
was listed. Registry checks confirmed 3.0.3 is currently the latest braces version. The five
entries describe the propagation of that dependency issue, not five independently demonstrated
runtime exploits. Full audit consequently exits nonzero. Production-only audit reports **0**.

No force/downgrade/opaque override or audit suppression was used: npm suggested eslint-config-next
14.2.35, which would break alignment with installed Next 16.4.2 rather than establish a safe
compatible upgrade. Keep lint globs/configuration trusted and run tooling with bounded resources;
monitor the upstream patch and reassess before release. Zero production audit findings is not a
security guarantee. Test tools were added as dev dependencies; Node types were aligned to the
installed Node 26 runtime to satisfy Vitest peers. Next/React versions remain unchanged.

## Manual review checklist and limits

1. Register/login on localhost:3000 with the backend at localhost:8000; confirm logout and a
   cleared/expired cookie return to sign-in without revealing private workspace content.
2. Create/select a project; add another registered account by UUID and check member/admin/owner
   controls. Confirm ownership transfer and server rejection of ineligible workspace deletion.
3. Upload PDF/TXT/MD with the real worker running, check extraction/index transitions, download
   originals, test retry failure messages and confirmed deletion. No worker means jobs stay queued.
4. Search with all/specific/no documents; ask a supported and unsupported question. Inspect
   citations/offline labels. Provider-disabled deployments should show explicit errors.
5. Save/follow up/reopen/rename/archive/restore a conversation. Delete a source and inspect its
   saved quote; then delete the conversation to remove that history.
6. Review keyboard focus, native confirmations, collapsed/mobile navigation and both themes;
   change accounts/tabs/workspaces and verify stale private data is never shown.

No live hosted-provider calls, cross-site-cookie workaround, provider configuration/profile
edit API, document-text editor, streaming, automatic source-wide history purge, frontend
sharing system, optimistic drafted answers, full-text filename API or fabricated global metrics
were added. Pagination/loaded-count limits and synchronous backend cancellation/retention limits
are explicit above. Production TLS/proxy configuration, rate/storage quotas, other browser
engines and a full accessibility/security review remain deployment work.

## File inventory

This milestone creates 43 files and modifies 12 existing files.
The backend, database migrations, infra and local API .env remain unchanged.

### Created

- `apps/web/.env.example`
- `apps/web/e2e/research.spec.ts`
- `apps/web/e2e/server.py`
- `apps/web/playwright.config.ts`
- `apps/web/src/app/(private)/layout.tsx`
- `apps/web/src/app/(private)/settings/page.tsx`
- `apps/web/src/app/(private)/workspaces/[workspaceId]/conversations/[conversationId]/page.tsx`
- `apps/web/src/app/(private)/workspaces/[workspaceId]/conversations/page.tsx`
- `apps/web/src/app/(private)/workspaces/[workspaceId]/documents/page.tsx`
- `apps/web/src/app/(private)/workspaces/[workspaceId]/layout.tsx`
- `apps/web/src/app/(private)/workspaces/[workspaceId]/members/page.tsx`
- `apps/web/src/app/(private)/workspaces/[workspaceId]/page.tsx`
- `apps/web/src/app/(private)/workspaces/[workspaceId]/research/page.tsx`
- `apps/web/src/app/(private)/workspaces/[workspaceId]/search/page.tsx`
- `apps/web/src/app/(private)/workspaces/page.tsx`
- `apps/web/src/app/error.tsx`
- `apps/web/src/app/login/page.tsx`
- `apps/web/src/app/not-found.tsx`
- `apps/web/src/app/register/page.tsx`
- `apps/web/src/components/auth/auth-form.tsx`
- `apps/web/src/components/chat/conversations.tsx`
- `apps/web/src/components/chat/research.tsx`
- `apps/web/src/components/chat/search.tsx`
- `apps/web/src/components/citations/answer.tsx`
- `apps/web/src/components/documents/filter.tsx`
- `apps/web/src/components/documents/library.tsx`
- `apps/web/src/components/layout/settings.tsx`
- `apps/web/src/components/layout/shell.tsx`
- `apps/web/src/components/layout/theme-init.tsx`
- `apps/web/src/components/ui.tsx`
- `apps/web/src/components/workspaces/context.tsx`
- `apps/web/src/components/workspaces/dashboard.tsx`
- `apps/web/src/components/workspaces/workspaces.tsx`
- `apps/web/src/hooks/use-resource.ts`
- `apps/web/src/lib/api/client.ts`
- `apps/web/src/lib/auth/session.tsx`
- `apps/web/src/proxy.ts`
- `apps/web/src/test/application.test.tsx`
- `apps/web/src/test/resources.test.tsx`
- `apps/web/src/test/setup.ts`
- `apps/web/src/types/api.ts`
- `apps/web/vitest.config.mts`
- `docs/frontend-architecture.md`

### Modified

- `README.md`
- `apps/web/.gitignore`
- `apps/web/README.md`
- `apps/web/next.config.ts`
- `apps/web/package-lock.json`
- `apps/web/package.json`
- `apps/web/src/app/globals.css`
- `apps/web/src/app/layout.tsx`
- `apps/web/src/app/page.tsx`
- `docs/api-specification.md`
- `docs/architecture.md`
- `docs/security.md`


## Completed verification

Executed on 2026-10-19:

| Check | Actual result |
| --- | --- |
| npm run lint | Pass, no findings |
| npx tsc --noEmit | Pass, strict mode |
| npm run build | Pass, Next.js 16.4.2; all app documents dynamically rendered for nonce/private-cache handling |
| npm test | 49 passed across two component/resource test files |
| npm run test:e2e | 4 Chromium production-build flows passed in 20.7 seconds, real isolated API/workers; representative desktop/mobile axe scans found no violations |
| python -m pytest -q | 595 preserved backend tests passed in 19.21 seconds; one existing Starlette/httpx deprecation warning |
| python -m alembic current | 6f22cc4c46ad (head), unchanged |
| python -m alembic check | No new upgrade operations detected |
| git diff --check | Pass |
| npm audit | Nonzero: 5 high development dependency-chain findings, no available braces patch |
| npm audit --omit=dev | Zero reported vulnerabilities |

Read-only hash/count comparisons preserved all fifteen original public tables (empty at the
comparison baseline) and the migration revision. The final browser run left zero e2e_web_
schemas and zero test storage directories. Graceful test-server shutdown explicitly handles
Uvicorn's signal re-raise so Python resource contexts unwind; verified remnants from earlier
failed runs were removed only after their exact synthetic-account/empty-data checks. Backend
source, migrations, infra and local .env were not changed. No commit, push or deployment was made.

The final normal build was restored to the usual local API origin after E2E. Synthetic
desktop/mobile screenshots were visually inspected; browser artifacts stay outside tracked
source. There was no paid AI, production TLS/cookie, Firefox/WebKit, manual screen-reader or
independent security verification. See the manual checklist and deployment requirements above.
