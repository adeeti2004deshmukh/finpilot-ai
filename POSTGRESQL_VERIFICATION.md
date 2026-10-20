# POSTGRESQL VERIFICATION

17 October 2026. This is a PostgreSQL setup inspection and offline stabilization result, not a claim of successful PostgreSQL deployment.

| Requested check | Result |
|---|---|
| PostgreSQL connection | NOT TESTABLE — no local server/runtime available |
| Docker PostgreSQL | NOT TESTABLE — Docker CLI/Desktop/service not found |
| Alembic migrations on PostgreSQL | NOT TESTABLE — offline PostgreSQL SQL checks pass, execution requires a server |
| Demo seed | NOT REQUIRED in this environment — not executed because no PostgreSQL database is available; required for a fresh local demo database |
| FastAPI with PostgreSQL | NOT TESTABLE |
| Phase 4 APIs with PostgreSQL | NOT TESTABLE |

## What was actually checked

- No `docker`, `psql`, `pg_ctl` or `postgres` executable is on PATH. No Docker/PostgreSQL service or standard installation directory was found; WinGet's installed-package directory contains Node only. Local TCP port 5432 refused the connection probe, and an explicit SQLAlchemy/psycopg connection attempt could not connect. No packages were installed and no unrelated processes were stopped.
- The psycopg driver is installed. There is no local `.env` and no DATABASE_URL environment override, so the existing application defaults to SQLite. Nothing was silently switched to PostgreSQL.
- Compose uses `postgres:16-alpine`, a named persistent volume, port 5432, a readiness check, and an API dependency on database health. The API connects to host `db` inside Compose, applies migrations, runs the existing demo seed, and starts Uvicorn. Host Python instead needs `127.0.0.1`/`localhost` in DATABASE_URL.
- SQLAlchemy uses `postgresql+psycopg`, connection pre-ping, and only applies SQLite's thread option for SQLite. Monetary columns are NUMERIC(14,2), dates/booleans/foreign keys are represented through SQLAlchemy, and financial formulas were not changed.
- Alembic overrides the fallback URL in alembic.ini with the same application settings, including escaped URL percent characters. Online migrations use that URL; offline migrations correctly select the PostgreSQL dialect.
- Offline PostgreSQL SQL generation revealed three copies of every named enum check constraint: two explicit declarations plus SQLAlchemy's automatic Enum(create_constraint=True) declaration. Removed the redundant explicit declarations in the initial migration, retaining the automatic check and all business constraints. This repairs fresh bootstrap DDL; it does not execute schema changes against an existing database or alter its revision number.
- Docker context now excludes frontend node_modules, Next build output and frontend local environment settings. These are not needed in the backend image.
- Added offline PostgreSQL DDL regression coverage, a fresh SQLite upgrade/check/downgrade/upgrade test on a disposable database, and a real-server migration/seed/API integration test.
- Final suite: **112 passed, 1 skipped**. The skipped test explicitly requires PostgreSQL. Existing TestClient and Alembic configuration deprecation warnings remain. A SQLite test pass and PostgreSQL SQL generation are not substitutes for server execution.

## Exact local commands: Docker Compose

Run these in PowerShell from `C:\Users\Adeeti\Documents\AI-Finance-project`, after installing and starting Docker Desktop with Linux containers. Commands assume the repository's default local demo credentials. If you already use different POSTGRES_* values, use matching credentials in the test URL. Do not overwrite an existing `.env`.

```powershell
Set-Location 'C:\Users\Adeeti\Documents\AI-Finance-project'
docker version
docker compose config --quiet
docker compose build api
docker compose up -d --wait db
docker compose exec -T db pg_isready -U postgres -d finpilot
docker compose exec -T db psql -U postgres -d finpilot -c 'SELECT version(), current_database();'

docker compose run --rm api python -m alembic upgrade head
docker compose run --rm api python -m alembic current
docker compose run --rm api python -m alembic check
docker compose run --rm api python seed.py
```

The seed is intended for the synthetic demo database: repeated calls avoid duplicate records but restore the demo profile/preferences/goals/budgets to their seed values. For an existing customized demo database, skip the explicit seed unless you want that reset; note that the existing Compose API startup command itself also runs the seed. No seed was executed against your current data during this inspection.

Run **real PostgreSQL integration and regression tests** inside the existing backend image:

```powershell
docker compose run --rm -e 'FINPILOT_TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@db:5432/finpilot' api python -m pytest -q -p no:cacheprovider
```

The opt-in URL must use `postgresql+psycopg`. Tests use fresh `finpilot_test_<uuid>` schemas and remove only their own generated schemas afterward; they do not drop the demo/public tables. The role requires permission to create schemas. The new live integration test runs Alembic against its isolated schema, checks schema drift, seeds twice to check duplicate prevention, and exercises Phase 4 APIs through FastAPI TestClient with real PostgreSQL-backed sessions. Existing database fixtures also switch to PostgreSQL when this variable is set. The explicitly named SQLite migration regression remains a SQLite compatibility check.

Start the actual PostgreSQL-backed API and test its HTTP routes:

```powershell
docker compose up -d api
docker compose ps
docker compose logs --tail 80 api
Invoke-RestMethod 'http://127.0.0.1:8000/health'
Invoke-RestMethod 'http://127.0.0.1:8000/api/dashboard/1'
Invoke-RestMethod 'http://127.0.0.1:8000/api/investment/plan/1'
Invoke-RestMethod 'http://127.0.0.1:8000/api/financial-health/1'
Invoke-RestMethod 'http://127.0.0.1:8000/api/financial-plan/monthly/1'
Invoke-RestMethod 'http://127.0.0.1:8000/api/financial-insights/1'
```

Use the demo ID printed by seed.py if it is not 1. Port 8000 must be free for the Compose API; stop your own earlier local backend in its terminal first if needed.

For the complete existing 41-check HTTP/page smoke script, start the frontend in another terminal:

```powershell
Set-Location 'C:\Users\Adeeti\Documents\AI-Finance-project\frontend'
npm run build
npm run start
```

Then from the project root:

```powershell
.venv\Scripts\python.exe scripts/verify_phase4_live.py --api http://127.0.0.1:8000 --frontend http://127.0.0.1:3000
```

That script checks dashboard/planner/goal comparison/health/monthly plan/insights, cash and EMI affordability (including wait alternatives), all five what-if scenarios, error responses, CORS and page HTML. It records current results in PHASE4_LIVE_RESULTS.json; the existing file currently records the earlier **SQLite** run, not PostgreSQL evidence. The backend URL in frontend/.env.local must match port 8000; the normal Compose CORS origin is localhost:3000.

To stop containers while retaining database data:

```powershell
docker compose stop
```

## Alternative: installed native PostgreSQL

Start your installed PostgreSQL service and create an empty `finpilot` database using your local credentials. Then, in a fresh PowerShell terminal at the project root:

```powershell
$env:DATABASE_URL = 'postgresql+psycopg://postgres:postgres@127.0.0.1:5432/finpilot'
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m alembic current
.venv\Scripts\python.exe -m alembic check
.venv\Scripts\python.exe seed.py
$env:FINPILOT_TEST_DATABASE_URL = $env:DATABASE_URL
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Keep this environment variable in the same terminal for migrations/seed/Uvicorn so none silently use the SQLite fallback. Use your actual password (URL-encoded when necessary); the sample is only the repository's local default. In another terminal run the HTTP commands above. No phase beyond Phase 4 was started.

## Files changed

- `alembic/versions/bf8c5f1a4a74_initial_phase_2_tables.py`: remove redundant enum check declarations.
- `tests/conftest.py`: explicit PostgreSQL opt-in with isolated schema lifecycle; SQLite remains the default.
- `tests/test_database_migrations.py`: offline PostgreSQL DDL and disposable SQLite migration tests.
- `tests/test_postgresql_integration.py`: opt-in real PostgreSQL migration/seed/API test.
- `.dockerignore`: exclude frontend dependencies/build output/local environment from the backend image.
- `POSTGRESQL_VERIFICATION.md` and documentation links: evidence, limitations and commands.

## Phase 4.5 authentication update

The latest migration is `c45_auth_onboarding`. Apply `alembic upgrade head` before running the API. The live verification script now authenticates through Explore Demo and derives the demo ID from the session; it no longer accepts `--user`. The PostgreSQL integration test also authenticates before private API calls. PostgreSQL runtime remains unverified; the Phase 4.5 browser and API results were obtained with SQLite. See [PHASE45_VERIFICATION.md](PHASE45_VERIFICATION.md).
