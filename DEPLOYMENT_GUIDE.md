# FinPilot Deployment Guide

This guide prepares a **manual** Vercel + Render + managed PostgreSQL deployment. Nothing here has been provisioned or deployed by the agent. Do not create paid resources until you have reviewed current provider terms and the Phase 6 report. No OpenAI account/key or API billing is needed for Demo AI Coach.

## 1. Review and prepare the repository

1. Review [PHASE6_PRODUCTION_READINESS_REPORT.md](PHASE6_PRODUCTION_READINESS_REPORT.md), run the documented tests, and review the diff locally.
2. Keep `.env`, local databases, backups, dumps, virtual environments, `node_modules`, `.next`, logs and test artifacts out of Git. The ignore rules cover them; they cannot remove files already committed.
3. This supplied workspace has no Git metadata and Git is unavailable in its shell. On your own machine, initialize/review Git and use `git status --short`, `git ls-files`, and `git check-ignore .env finpilot_dev.db frontend/.env.local` before staging. Run a dedicated Git-history secret scan before public publishing; the included candidate-source scan does not scan history. If a real secret was previously committed, rotate it and clean the history before publishing.
4. Only you should create/push the GitHub repository after review. This phase does not push anything.

Local verification:

```powershell
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m scripts.scan_repository_secrets
cd frontend
npm ci
npm run typecheck
npm run lint
npm run build
cd ..
.venv/Scripts/python -m scripts.verify_phase5_assets
```

## 2. Choose the architecture

Recommended browser route:

```text
Browser -> https://YOUR-FRONTEND/api/*
        -> Next.js external rewrite
        -> https://YOUR-BACKEND/api/*
        -> managed PostgreSQL
```

Vercel supports external-origin proxy rewrites; FinPilot uses the installed Next.js `rewrites()` configuration. See [Vercel rewrites](https://vercel.com/docs/routing/rewrites). This keeps cookies first-party without purchasing a shared custom domain. `Cache-Control: no-store` applies to API responses and the frontend proxy path. Do not add CDN caching to `/api/*`.

Alternative: call the backend directly with `NEXT_PUBLIC_API_URL=https://YOUR-BACKEND`. See the cross-origin section below before choosing that option. The frontend always uses `credentials: include`; the backend remains authoritative for authentication.

## 3. Create accounts and a managed PostgreSQL database manually

1. Review the current Vercel, Render and managed database plans, retention/expiry rules, quotas, region choices and pricing. Do not assume a service is free or that a trial lasts indefinitely. This guide makes no free-tier claim.
2. Create the accounts you choose and enable account security features.
3. Create a dedicated managed PostgreSQL database in an appropriate region, ideally near the backend. Use a separate database/role for this application. Do not reuse personal/production databases from other projects.
4. Save its connection string in the backend provider's secret environment configuration. FinPilot accepts `postgres://...`, `postgresql://...` and `postgresql+psycopg://...`; it normalizes the first two for the installed psycopg driver.
5. Apply the database provider's required TLS configuration. For a provider using encrypted PostgreSQL connections, preserve its TLS query parameters (for example `sslmode=require`); prefer CA verification/`verify-full` when the provider supplies the necessary certificate configuration. Do not assume a URI conversion adds TLS. URL-encode reserved password characters.
6. Enable/review backups and retention. Record how to restore a backup into a separate database and test that procedure before storing important data publicly.

SQLAlchemy's supported psycopg URL format is documented in its [PostgreSQL dialect documentation](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg). There is no SQLite-to-production data copy in this phase.

## 4. Prepare the Render backend manually

Use repository root as the backend root. The recommended route is a Docker web service using the existing `Dockerfile`; this pins the Python minor version to 3.12 and uses a non-root user. Review the generated service settings before starting it. Native Python hosting is also portable: build with `pip install -r requirements.txt` and start with `python -m app.serve`, using a supported Python 3.12 runtime.

The Render [FastAPI deployment guide](https://render.com/docs/deploy-fastapi) describes its web-service creation/build/start workflow. FinPilot's entry point binds `0.0.0.0`, reads the platform's `PORT`, runs one Uvicorn worker without reload and disables application access logs in production. Do not copy a generic multi-worker command yet: coach context and coarse rate limits are process-local.

Configure these backend variables (replace placeholders; never commit actual values):

```dotenv
APP_ENV=production
DATABASE_URL=postgresql+psycopg://USER:URL_ENCODED_PASSWORD@db.example.test:5432/DB_NAME?sslmode=require
FRONTEND_URL=https://YOUR-FRONTEND.vercel.app
BACKEND_URL=https://YOUR-BACKEND.onrender.com
AI_PROVIDER=demo
OPENAI_API_KEY=
OPENAI_MODEL=gpt-6-sol
SESSION_COOKIE_NAME=finpilot_session
SESSION_COOKIE_SAMESITE=lax
SESSION_TTL_SECONDS=86400
MAX_REQUEST_BYTES=65536
AI_TIMEOUT_SECONDS=30
AI_MAX_OUTPUT_TOKENS=1800
AI_MAX_TOOL_ROUNDS=4
SAFETY_BUFFER_RATE=0.08
SAFETY_BUFFER_MINIMUM=5000
```

The platform supplies `PORT`. Set `FRONTEND_URL` to the exact stable frontend production origin once known, without a path or trailing slash. Never use `*`. If the frontend project name changes, update this origin before testing login.

If your host requires trusted forwarded client-IP handling, configure `FORWARDED_ALLOW_IPS` with only the host's documented trusted proxy IPs/CIDRs. Do not set `*` just to fix a rate-limit issue: untrusted forwarding headers could then alter the apparent client. Until configured, requests forwarded through shared proxies can share coarse IP limits. Account/session authorization is independent of these IPs.

Docker does not run migrations or seed users on startup. Configure the host's health-check path as `/health`. `/ready` separately checks DB connectivity. An initial backend may need database initialization before private endpoints are usable; that is expected.

## 5. Initialize the new production database once

Back up any pre-existing database before applying migrations. On a fresh managed database, use the hosting release/pre-deploy command or an authenticated service shell with its backend environment already configured:

```sh
python -m scripts.initialize_database
```

This runs `alembic upgrade head` and inserts the shared category/merchant-rule catalog idempotently. It creates no user, profile, transaction, budget or goal. Alternatively run `python -m alembic upgrade head` and initialize the catalog through the provided initialization command afterward. Do not run multiple initializers concurrently.

For an **intentional read-only synthetic demo account**, run separately:

```sh
python -m scripts.initialize_database --demo
```

This explicitly opts into Aarav's synthetic demo account; it does not seed registered users. The seeder refuses to convert a non-demo account that already owns the demo email. The demo login is read-only and separate from personal registrations. Without this optional step, ordinary registration/onboarding still works, while Explore Demo reports unavailable.

Check:

```sh
python -m alembic current
python -m alembic check
```

Do not run migration downgrades on a populated production database to experiment. The authentication migration deliberately blocks destructive downgrades when they would discard real account credentials/private data.

## 6. Configure and deploy the Vercel frontend manually

1. Import the reviewed repository as a Next.js project with **Root Directory `frontend`**. Do not use the Python repository root as the frontend root.
2. Use `npm ci` for install and `npm run build` for build; keep the normal Next.js output configuration.
3. Configure frontend environment variables:

   ```dotenv
   BACKEND_URL=https://YOUR-BACKEND.onrender.com
   SESSION_COOKIE_NAME=finpilot_session
   ```

4. **Leave `NEXT_PUBLIC_API_URL` unset or explicitly empty** for the recommended same-origin proxy. Remove an old localhost value from Vercel project settings. Local `frontend/.env.local` is ignored and must not be uploaded. `BACKEND_URL` is a backend HTTP origin, not a database URL or a credential-bearing URL.
5. Do not configure backend secrets on Vercel. `DATABASE_URL`, `OPENAI_API_KEY`, session tokens and any future signing keys must never use `NEXT_PUBLIC_*`.
6. Deploy manually when configuration and backend initialization are reviewed. Rewrites and public variables are build-time configuration: changing the backend origin/API mode requires rebuilding/redeploying the frontend.
7. Copy the exact stable frontend production origin into the backend's `FRONTEND_URL`, redeploy/restart the backend after environment changes, and verify both sides refer to the intended production environment. Do not authorize all preview domains with a wildcard. Test a preview environment with its own explicit backend origin configuration if needed.

## 7. Cookie, CORS and CSRF choices

### Recommended frontend proxy

- Browser API URL: `/api/...` on the frontend origin.
- Cookie: host-only on the frontend host, HttpOnly, Secure in production, `SameSite=lax`, path `/`.
- No broad cookie Domain is set. The same attributes are used when clearing it on logout.
- `SESSION_COOKIE_NAME` must match frontend/backend.
- Backend `FRONTEND_URL` must match the page's actual Origin. Backend CORS allows that exact origin with credentials, and CSRF checks verify present Origins against configured origins.
- Mutation fetches send `X-FinPilot-Request: 1`. Rewrites must preserve that header, the Origin, cookies and Set-Cookie responses.
- Keep `/api/*` uncached at the proxy/CDN; verify `Cache-Control: no-store` on login and personal endpoints.

### Direct cross-origin API (optional)

Set `NEXT_PUBLIC_API_URL` to the backend's HTTPS origin instead of using the frontend rewrite. If origins are cross-site, configure `SESSION_COOKIE_SAMESITE=none` and `APP_ENV=production`; Secure is automatic. Browsers can still reject third-party cookies. Do not disable browser security or weaken CSRF. Prefer the same-origin proxy if auth fails under those restrictions.

For custom sibling subdomains under the same site, `lax` may be sufficient, but test real browser behavior. Host-only backend cookies are invisible to Next.js's frontend-host cookie check; the proxy file skips that advisory check for direct cross-origin APIs, and AuthProvider still gates all private UI against authenticated `/api/auth/me`. The backend always validates the actual session.

Cookie behavior is described in [MDN Set-Cookie](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie). Real HTTPS cookie forwarding on the selected live hosts remains a manual verification item, even though local proxy round trips passed.

## 8. Health and public-demo checks

- `GET https://YOUR-BACKEND/health`: app liveness; no DB query or credentials.
- `GET https://YOUR-BACKEND/ready`: DB connectivity only, not schema-version verification. Failure returns 503 without connection details.
- Open the frontend, register a disposable account, onboard and use the full [production smoke checklist](PRODUCTION_SMOKE_TEST_CHECKLIST.md).
- Check demo labels and financial disclaimers. Demo AI Coach must work with an empty `OPENAI_API_KEY`, using the signed-in account's own data.
- Check a second account cannot access the first account's IDs or conversation UUIDs. Do not place real bank/card credentials in any test.
- Inspect provider logs without pasting credentials into screenshots. Application production logs omit exception payloads/access logs, but hosting/CDN logs may still retain URLs/headers. Configure those separately and never put tokens in query strings.

## 9. Rate-limit and runtime limitations

The portfolio baseline is one backend worker/instance. Persistent authentication throttles include a 15-minute window; production middleware also limits auth mutation requests to 30/minute per apparent IP, AI chat to 20/minute per apparent IP, public calculations to 60/minute per apparent IP, planning mutations to 30/minute and general API requests to 240/minute. Existing coach user limits remain 10/minute. Request bodies are capped at 64 KiB by default.

Coarse limits are process-local, bounded and best-effort. They reset on restart and do not provide distributed DDoS protection. Shared proxy addresses can cause false positives. Conversations are bounded process memory and disappear on restart. Add shared storage/distributed limits before multiple workers or instances. Review expired auth-session/throttle row retention for long-running public operation; no scheduled maintenance service was provisioned.

The stateless public Phase 1 demo and simulation endpoints remain public educational tools. They do not query personal accounts, and production limits apply. User-backed financial endpoints remain authenticated.

## 10. Rollback and operations

1. Record the deployed frontend/backend revisions and the current Alembic revision before each release.
2. Back up the managed database and confirm restore access. Keep backups outside the repository with restricted access.
3. Prefer rolling back application code only when it is compatible with the current schema. Do not automatically downgrade financial/auth tables.
4. If a schema restore is necessary, restore into a separate database, verify it, and explicitly change the backend URL/configuration to that database. Reconcile any writes made after the backup before switching traffic.
5. Changing database credentials requires backend restart; changing the API origin requires a frontend rebuild. Rotate exposed keys/passwords rather than merely deleting files.
6. Stop a broken release or disable optional OpenAI usage by setting `AI_PROVIDER=demo`, then restart the backend. No API key or billing is needed for that mode.

## 11. Future OpenAI activation (not needed now)

Only after a separate decision, set `AI_PROVIDER=openai` and the backend-only `OPENAI_API_KEY`, keep a compatible `OPENAI_MODEL`, and restart. Review API costs, project access and data controls first. The existing model integration is retained; no redesign is required. Missing provider credentials affect only the coach endpoint. This phase makes no live paid API call.

## Verification boundary

VERIFIED locally: automated security/isolation/configuration tests, PostgreSQL-dialect SQL generation, SQLite migrations/initialization, frontend typecheck/lint/build, real local browser-to-Next.js-to-FastAPI proxy flows, and candidate-source/client-asset secret scans.

NOT TESTED / REQUIRES LIVE HOST: a fresh managed PostgreSQL migration/runtime, Vercel/Render provisioning, provider-specific TLS/proxy headers, HTTPS cookies on those live domains, backup/restore, real cross-site browser restrictions, cold starts and paid OpenAI responses. Docker configuration was inspected but no Docker build/runtime was performed because the tooling is unavailable in this workspace.
