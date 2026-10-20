# Phase 6 — Production Readiness Report

Date: 20 October 2026.

**Phase 6 preparation is complete. Nothing was deployed, purchased, provisioned or pushed to GitHub. No paid OpenAI call was made, and no new phase was started.**

## Audit findings and resulting changes

| Finding | Resolution |
| --- | --- |
| Frontend/back-end cookie setup assumed a shared site; direct Vercel/Render domains can reject third-party cookies | Added configurable same-origin Next.js `/api/*` rewrites. Browser cookies stay first-party. Direct-origin mode remains available with explicit cookie settings and documented restrictions. |
| Frontend proxy assumed every backend cookie was visible on the frontend host | Advisory cookie-presence redirect now accounts for direct cross-origin APIs. AuthProvider and backend session validation remain authoritative. |
| Production CORS validation only rejected literal `*` | Validate exact HTTP(S) origins without credentials, paths, queries or wildcards; production requires HTTPS origins and PostgreSQL. |
| Fixed `SameSite=lax` could not intentionally support direct cross-site auth | Added `SESSION_COOKIE_SAMESITE`; default remains lax. None requires production HTTPS/Secure. Logout uses the same cookie attributes. |
| CSRF origin check also trusted a request-derived base URL | Trust only configured frontend/backend origins; Host headers cannot establish a new trusted origin. Existing custom mutation header remains required. |
| Provider PostgreSQL connection strings might select an unavailable driver | Normalize `postgres://` and `postgresql://` to installed `postgresql+psycopg://`, preserving the remainder of the URL. |
| Generic exceptions logged raw stack/error contents in all environments | Production logs only exception class names and returns generic errors. The server entry point disables production access logs. Development diagnostics remain available. |
| Programmatic Alembic configuration could disable existing application loggers | Keep existing loggers enabled; hide migration SQL parameters. |
| Existing Compose startup seeded Aarav automatically | Normal initialization migrates and adds only shared catalog entries. Demo seeding requires an explicit operator flag. |
| Seeder could overwrite an existing account occupying the demo email | Refuse non-demo/credentialed account collisions before changing anything. |
| Public simulation endpoints lacked coarse abuse controls | Bounded single-process production IP/group limits plus existing auth/AI limits; 64 KiB request body cap. |
| Liveness did not distinguish DB access | Keep `/health`; add `/ready` for a minimal DB connectivity query with a safe 503 on failure. |
| Demo label used Local terminology unsuitable for hosting | Frontend now shows Demo AI Coach and says deterministic tools/no external AI API calls. |
| Docker image copied unnecessary workspace material and ran as root | Copy backend files explicitly, use a non-root user, honor platform PORT, and omit development reload/migration/seeding from production startup. |
| Git ignore coverage was narrow | Ignore local env variants, DBs/dumps/backups, build output, dependencies, test artifacts, keys and local tool state; retain safe env examples. |

## Production architecture

Recommended: browser -> Vercel Next.js `/api` proxy over HTTPS -> Render/Railway-compatible FastAPI -> managed PostgreSQL. The practical manual guide uses Render. The portable backend command is `python -m app.serve`; the Dockerfile uses that command with one Uvicorn worker. SQLite remains supported for local development.

The OpenAI implementation is retained. `AI_PROVIDER=demo` remains the safe default, uses the authenticated user's real deterministic results and does not require any API key. There is no automatic paid-provider fallback. Explicit `AI_PROVIDER=openai` plus a backend API key enables the existing integration later; a missing key produces a clear coach-only configuration error.

## Authentication, API security and privacy

VERIFIED by code audit and automated tests:

- Argon2 password hashing, random opaque session cookies, hashed tokens in the database, expiry and logout invalidation remain intact.
- Production cookies are HttpOnly, Secure, host-only and use the selected SameSite policy. Cookie creation/deletion attributes match.
- Exact-origin credentialed CORS and the `X-FinPilot-Request` CSRF header remain enforced. Unapproved/spoofed Origins are rejected.
- Financial routes retain server-derived identity. Legacy ID routes are guarded at router inclusion and additionally authorize resource ownership. Read-only demo restrictions remain enforced.
- Existing two-user tests cover transactions, budgets, goals, profiles, preferences, alerts, subscriptions, dashboard, investment plans/categories, affordability, What-If, rules and AI conversation/tool scope. User IDs never establish identity by themselves.
- Stateless `/api/v1` educational fixtures/calculations and `/api/simulate` remain public by design; they do not read stored user accounts. Production request limits apply.
- All API responses receive no-store. The Next.js proxy path also declares no-store. No financial values are parsed from prose by the UI.
- Invalid/oversized inputs and production exceptions fail safely; tests check exception bodies and sensitive messages do not appear in client output or production application logs.
- The demo provider's existing zero-network tests still pass. Production labels do not claim OpenAI generated those responses.

NOT TESTED / REQUIRES LIVE HOST: provider cookie forwarding under actual HTTPS, cross-site browser policies, proxy IP attribution, CDN cache behavior on Vercel, platform request logging and public abuse resistance. The local browser test verifies the actual rewrite/session round trip but uses local HTTP and SQLite.

## Environment configuration

Backend required production values:

```dotenv
APP_ENV=production
DATABASE_URL=postgresql+psycopg://USER:URL_ENCODED_PASSWORD@db.example.test:5432/DB_NAME?sslmode=require
FRONTEND_URL=https://YOUR-FRONTEND.vercel.app
BACKEND_URL=https://YOUR-BACKEND.onrender.com
AI_PROVIDER=demo
SESSION_COOKIE_NAME=finpilot_session
SESSION_COOKIE_SAMESITE=lax
SESSION_TTL_SECONDS=86400
```

`BACKEND_URL` on the backend is an optional canonical CSRF origin; configure it explicitly for the documented setup. The host supplies `PORT`. Additional existing settings and the body limit are documented in README and the deployment guide. No JWT signing secret is required by the current opaque database-session design.

Frontend recommended configuration:

```dotenv
BACKEND_URL=https://YOUR-BACKEND.onrender.com
SESSION_COOKIE_NAME=finpilot_session
```

Leave `NEXT_PUBLIC_API_URL` unset/empty for the proxy. For direct-origin mode, set it to the backend HTTPS origin and follow the documented SameSite/cookie limitations. Public API URL variables are validated to reject credentials/non-HTTP origins. Vercel production configuration requires an HTTPS destination.

Database URLs, session credentials and `OPENAI_API_KEY` must never be frontend variables. Root and frontend env examples contain safe local/default or empty values. The real local `.env` was not changed by Phase 6. Backend/frontend origins are read from configuration; localhost defaults are limited to local development/testing. Rebuild the frontend after API origin changes and restart the backend after backend environment changes.

## Database readiness and initialization

VERIFIED:

- Existing SQLAlchemy/Alembic schema retains `NUMERIC(14,2)` money, timezone-aware timestamps, check/unique constraints, ownership foreign keys with cascade/restrict/set-null semantics, and relevant ownership/date indexes.
- Existing PostgreSQL-dialect migration-generation tests compile the complete migration chain and check unique enum/check names, Numeric fields and timestamp types.
- SQLite fresh migration upgrade/downgrade/upgrade and legacy data-preservation tests pass. A new temporary-database test runs catalog initialization twice and confirms there are no users or financial records.
- SQLite runtime connections now enable foreign-key enforcement; PostgreSQL connections use bounded pools, recycling and connection timeout, with hidden SQL parameters.
- `python -m scripts.initialize_database` applies `alembic upgrade head` and idempotently creates the shared catalog. `--demo` explicitly opts into the separate read-only synthetic account. Production startup does neither automatically.
- Seeding refuses to convert a non-demo account. Normal registration/onboarding does not copy demo financial records.

NOT TESTED: fresh real PostgreSQL runtime/migrations in this phase. No `FINPILOT_TEST_DATABASE_URL` was supplied and PostgreSQL/Docker tooling is unavailable here. The opt-in runtime test skipped. Offline compilation and SQLite tests are not reported as a PostgreSQL runtime pass. Historical PostgreSQL documents are preserved but are not a new Phase 6 certification.

## Executed validation

| Check | Status and evidence |
| --- | --- |
| Complete backend suite | VERIFIED: 227 passed, 1 skipped; includes 21 new production tests |
| Existing demo/OpenAI behavior and isolation | VERIFIED: existing Phase 1–5/demo suites included; no live AI network call |
| Production configuration, CORS, cookies, rate limits, body caps, safe errors, initialization and health/readiness | VERIFIED by new production tests |
| Frontend typecheck | VERIFIED: `npm run typecheck` exit 0 |
| Frontend lint | VERIFIED: `npm run lint` exit 0 |
| Frontend production build | VERIFIED: Next.js production build passed, all 17 pages generated, using an empty public API URL and configured local proxy destination for testing |
| Real local proxy/browser flow | VERIFIED: 9 checks, no page errors; evidence in ignored `PHASE6_PROXY_BROWSER_RESULTS.json` |
| Client asset secret scan | VERIFIED: 35 production client assets, no configured backend key/DSN, PostgreSQL URI, private key or test sentinel |
| Candidate-source secret scan | VERIFIED: no findings from the included scanner; values never printed |
| Compose configuration | VERIFIED: YAML parsed, no automatic demo seed command, loopback port mappings inspected |
| Docker image build/runtime | NOT TESTED: Docker tooling unavailable |
| Real managed PostgreSQL | NOT TESTED: opt-in runtime test skipped |
| Vercel/Render/Railway hosting, HTTPS domains, backups/restores | NOT TESTED / REQUIRES LIVE HOST |
| Git tracked files/history | NOT TESTED: no `.git` metadata and Git is unavailable in this workspace |

Final full-suite command:

```powershell
.venv/Scripts/python -m pytest -q --basetemp=.pytest-phase6-verified-tmp -o cache_dir=.pytest-phase6-cache
```

Existing Starlette/httpx and Alembic path-separator deprecation warnings remain. Initial findings in the new logging test led to preserving application loggers during Alembic setup; the final full suite passes.

The real browser check started temporary local frontend/backend servers, initialized a new ignored SQLite database, and used separate synthetic accounts. It verified registration/onboarding and first-party HttpOnly cookie round trips through Next.js; major pages; real affordability/What-If calculations; Demo AI Coach income from the newly registered account; no-store; cross-user denial; UI logout/login; and mobile overflow. It did not modify the existing `finpilot_dev.db`. The script stopped its own servers afterward.

The standalone frontend checks ran through package scripts. The proxy-mode production build invokes the same Next.js build entry point as `npm run build` with process-only environment overrides, avoiding changes to the user's existing frontend env file. A repeat local browser run can use `scripts/verify_phase6_proxy.py` after building for its documented test port.

## Secret and Git readiness

The candidate-source scanner checks likely OpenAI keys, private-key material, literal named secrets and credential-bearing nonlocal PostgreSQL URLs while excluding local env files, databases, dependencies, backups and generated artifacts. It reports file/line/type only, never matched values. A documentation connection-string placeholder was reviewed and changed to an explicit reserved example hostname; the final scan has no findings.

The asset scanner separately checks the actual configured backend key/DSN and high-confidence credential patterns in client build files. Neither scanner proves the absence of every possible secret. In particular, Git history and already-tracked ignored files cannot be certified without Git metadata/tooling. Before publishing, manually inspect tracked files and run a dedicated history scanner. Rotate any real exposed credential; deleting the file alone is insufficient.

No discovered real secret is reported, and no real credential was printed. Ignore rules prepare new staging but cannot untrack existing history. Test artifacts/temporary DBs are ignored, not deleted from the user's workspace.

## Remaining limitations

- One worker/instance is the supported baseline. Coach context and coarse rate limits are process-local, bounded and best-effort, reset on restart, and are not distributed DDoS protection.
- Apparent proxy IP sharing can throttle legitimate users. Trusted forwarding configuration needs real-host review; no blanket trust of user-supplied headers was added.
- Expired auth session/throttle row retention needs an operator policy for long-running public operation; no scheduled cleanup/cloud resource was provisioned.
- Direct cross-site cookies may be blocked even with SameSite=None/Secure; prefer the first-party frontend proxy.
- Managed PostgreSQL TLS, migrations, hosting health checks, public-domain cookies and backups/restores still require the manual guide/checklist.
- Demo routing remains intentionally limited. Optional OpenAI explanations still need financial grounding review; no real model response quality/billing was tested.
- Source/client scans are best-effort and cannot certify unknown Git history or provider logs.

## Files added or modified

Added:

- `DEPLOYMENT_GUIDE.md`
- `PRODUCTION_SMOKE_TEST_CHECKLIST.md`
- `PHASE6_PRODUCTION_READINESS_REPORT.md`
- `app/serve.py`
- `app/services/request_security.py`
- `scripts/initialize_database.py`
- `scripts/scan_repository_secrets.py`
- `scripts/verify_phase6_proxy.py`
- `tests/test_production_readiness.py`
- `frontend/.env.example`

Modified:

- `README.md` — portfolio README and setup/architecture/security documentation.
- `.env.example`, `.gitignore`, `.dockerignore` — safe examples and publishing/build exclusions.
- `Dockerfile`, `docker-compose.yml` — non-root portable backend, explicit initialization, no auto demo seed.
- `app/config.py` — validated production origins/database/environment and cookie/body settings.
- `app/main.py` — safe errors/headers, request protection, DB readiness.
- `app/database/session.py` — bounded PostgreSQL connections, SQLite FK enforcement.
- `app/services/auth.py`, `app/api/routes/auth.py` — configured CSRF origins, SameSite and matching logout attributes; safe malformed JSON handling.
- `alembic/env.py` — preserve loggers and hide migration parameters.
- `seed.py` — refuse real-account collisions.
- `frontend/services/api.ts`, `frontend/next.config.ts`, `frontend/proxy.ts` — production API routing, URL validation, headers and direct-origin cookie awareness.
- `frontend/components/ai/coach-view.tsx`, `app/services/ai/demo_service.py` — cloud-appropriate demo disclosure.
- `scripts/verify_phase5_browser.py`, `scripts/verify_phase5_assets.py` — updated demo label checks and broader client credential scanning.

Generated local evidence: ignored `PHASE6_PROXY_BROWSER_RESULTS.json`, build output and ignored temporary test artifacts. No new Alembic version or financial calculation change was needed. Existing authentication and AI provider implementations were retained.

## Exact next manual steps

1. Review this report/diff, install Git on the machine used to publish, inspect ignored/tracked files and run a dedicated history secret scan. Create/push a reviewed repository yourself only after that review.
2. Review current hosting/database plans before creating services; no free/trial availability is assumed. Create the accounts and dedicated managed PostgreSQL database you choose.
3. Prepare a Render Docker web service from repository root (or equivalent Railway/native Python service), set the documented production backend variables and keep `AI_PROVIDER=demo` with an empty key.
4. Run `python -m scripts.initialize_database` as the explicit database release/init step. Add `--demo` only if you intentionally want the separate synthetic account. Verify Alembic head and `/ready` against the actual managed database.
5. Configure Vercel with root `frontend`, server/build `BACKEND_URL` pointing to the HTTPS backend, matching cookie name, and no public direct API URL for the recommended proxy.
6. Deploy manually, set backend `FRONTEND_URL` to the exact stable frontend origin, restart/redeploy after env changes, and validate health/cookie/CORS behavior on the live domains.
7. Complete [PRODUCTION_SMOKE_TEST_CHECKLIST.md](PRODUCTION_SMOKE_TEST_CHECKLIST.md), including two-account isolation and logout replay, and verify a backup/restore/rollback procedure.

Detailed provider-specific steps, exact variables/commands, cross-origin alternatives and rollback considerations are in [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md).

STOP: preparation only. No cloud account/database/service creation, deployment, purchase, Git push or subsequent-phase work was performed.
