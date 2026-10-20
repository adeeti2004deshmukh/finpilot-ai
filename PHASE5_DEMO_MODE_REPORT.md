# Phase 5 Local/Demo AI Coach Mode

Date: 20 October 2026.

## Audit and scope

The existing Phase 5 endpoint already derived identity from authentication, used a validated read/simulation-only `ToolExecutor`, retained bounded owned conversation state, and separated the OpenAI Responses loop from financial services. The only provider gate was an unconditional API-key check, and the frontend disclosure assumed every answer came from OpenAI.

The change adds a provider branch and one local routing/template module. It reuses the existing executor, registry, deterministic services, authentication, CSRF protection, safety refusals, conversation ownership/locks, expiry and request limits. The OpenAI SDK integration and Responses loop remain intact. There are no migrations, new financial calculations, dependency changes, deployments or Phase 6 work.

## Configuration

`AI_PROVIDER` accepts exactly `demo` or `openai`. Its default is `demo`, including when omitted. There is no automatic provider fallback.

```dotenv
AI_PROVIDER=demo
OPENAI_API_KEY=
OPENAI_MODEL=gpt-6-sol
```

Demo mode does not validate or require an API key and does not instantiate an OpenAI client, invoke a model or make any external API request. An existing API key does not enable external calls while the provider is `demo`. The model setting is unused in demo mode.

The local ignored `.env` was updated only to select `AI_PROVIDER=demo`. Other settings were preserved and no secrets were displayed or added to tracked files. Restart the backend to load the setting, start the frontend normally, sign in and open `/ai-coach`. No billing setup is needed.

To switch later:

```dotenv
AI_PROVIDER=openai
OPENAI_API_KEY=your_actual_key
OPENAI_MODEL=gpt-6-sol
```

Set the real key only in the backend's ignored `.env` and restart the backend. Keep it out of frontend variables, repository files and screenshots. The existing OpenAI implementation then runs through the same endpoint. OpenAI mode without a key returns the existing clear configuration error; it does not crash the application or silently substitute demo output.

## Local routing and supported questions

The server recognizes a bounded set of intents using deterministic text patterns. It calls `ToolExecutor(db, authenticated_user.id)` and renders fixed explanations from returned fields. Monetary formatting changes presentation only; it does not recompute financial values. No user's financial figures are hard-coded.

| Example | Existing tools used |
| --- | --- |
| Where am I overspending? | `get_spending_analysis`, `get_budget_status` |
| Why is my financial health score low? | `get_financial_health` |
| What should I prioritize this month? | `get_financial_priorities`, `get_monthly_plan` |
| How is my emergency fund? | `get_emergency_fund_status` |
| How are my goals doing? | `get_goals` |
| Analyze my Study goal / Analyze goal #ID | `get_goals`, then `analyze_goal` for an owned goal |
| What investment categories fit my goals? | `get_goals`, `get_investment_plan` |
| What investment categories fit my Study goal? | Also `compare_investment_categories` for the owned goal |
| Can I afford an ₹80,000 phone? | Asks for missing date/payment details before `analyze_affordability` |
| Cash, today. (after that question) | Completes purchase inputs and runs `analyze_affordability` |
| What if I wait six months? (after a completed purchase analysis) | `delay_purchase`, which reruns the existing affordability service |
| Simulate SIP of ₹1,000 for 12 months at 5% annual rate | `simulate_sip` |
| Simulate RD of ₹1,000 for 12 months at 5% annual rate | `simulate_rd` |
| Simulate FD of ₹10,000 for 1 year at 5% annual rate | `simulate_fd` |
| What if my income increases by ₹5,000? | `run_what_if_scenario`: income increase |
| What if my rent increases by ₹1,000? | `run_what_if_scenario`: rent increase |
| What if my food spending reduces by ₹1,000? | `run_what_if_scenario`: food spending reduction |
| What if my savings increase by ₹1,000? | `run_what_if_scenario`: savings increase |
| Show my financial summary | `get_financial_summary` |

The income/expense/savings/surplus fields, health scores and components, emergency reserve coverage, goal contributions, budget status, investment allocations, projections and scenario outcomes all come from tool results. Saved goals with no deadline explicitly request a deadline instead of presenting the engine's placeholder zero as a valid monthly contribution.

Simulation rates are explicitly supplied by the user, not assumed by the coach. FD uses the existing quarterly compounding default unless a supported compounding phrase is supplied, and displays the frequency used. Currency inputs support ₹, INR, Rs and common lakh/lac/crore/k suffixes. Use explicit ISO dates, `today`, or relative month/year durations. For EMI, provide down payment, monthly EMI and tenure, for example `monthly EMI 3000, down payment 10000, tenure 24 months`.

The local router is deliberately limited; it is not a local LLM. Arbitrary paraphrases, multi-intent questions, unsaved goal scenarios, saved-goal-delay What-If requests and general conversation are not fully supported in this branch. Unsupported inputs receive a capability explanation or a clarification prompt. The original OpenAI tools remain available in OpenAI mode.

## Safety, privacy and frontend

- Backend authentication establishes the user; the client cannot choose a user ID or provider. Tool queries and saved-goal lookups stay scoped to that user. Foreign goal IDs and conversation UUIDs cannot expose another user's data.
- Both providers share the existing unsafe-request checks. Local responses have no generative path that could execute a transfer/trade, recommend a named security, promise returns or request credentials. Existing tools cannot mutate financial records.
- Questions asking for money movement, guaranteed returns or another user's data are safely refused. Passwords, UPI PINs, OTPs, CVVs and full card credentials are never needed or requested.
- Demo mode never uploads questions or results to OpenAI. It uses the same bounded process-local conversation store and retains only bounded pending clarification text/arguments and the existing last verified purchase context. No transcript is written to browser storage or financial tables.
- Demo error logs record exception class names, not submitted data, result bodies or secrets. Missing profiles, invalid inputs and tool errors produce safe messages.
- Authenticated `GET /api/ai/config` exposes only the selected provider. Chat replies include `provider`. The frontend uses these values to show **Demo AI Coach · Local mode**, with a local-only disclosure, while retaining the existing loading/error/follow-up UI. It never claims demo answers are generated by OpenAI.
- Existing expiry, concurrency protection and per-user request limits still apply. Storage remains process-local; use a single backend worker for consistent local conversations.

## Verification

| Check | Result |
| --- | --- |
| Complete backend suite | PASS — 206 passed, 1 skipped |
| New demo tests | PASS — 33 tests using real deterministic services |
| Existing OpenAI coach tests | PASS — 48 tests, explicitly configured to exercise OpenAI mode with mocks |
| Demo without API key | PASS |
| External OpenAI/HTTP calls blocked during demo tests | PASS |
| Current-user values and refreshed data | PASS |
| Two-user data/conversation isolation and real cookie sessions | PASS |
| Budget/spending and projection values match services | PASS |
| Missing purchase/rate inputs and purchase-delay follow-up | PASS |
| Safe refusals, CSRF, unauthenticated requests and supplied user-ID rejection | PASS |
| OpenAI missing-key configuration error | PASS |
| Frontend typecheck | PASS |
| Frontend lint | PASS |
| Frontend production build | PASS — all 17 pages generated |
| Production UI browser checks | PASS — including demo label/disclosure, no page errors |
| Client credential scan | PASS — 35 production client assets scanned |

Demo tests fail if the code attempts to create an OpenAI client or use external HTTP transport. They exercise the actual service layer rather than canned financial results. Tests also verify distinct values for two real authenticated accounts, rejection of cross-account conversations, ignored prompt-injected income and unchanged financial table counts after chat.

The one skipped test is the existing opt-in real PostgreSQL integration test; `FINPILOT_TEST_DATABASE_URL` was not supplied. Existing Starlette/httpx and Alembic deprecation warnings remain. No paid/live OpenAI request was made. Browser checks use synthetic API responses to test presentation; authenticated backend/service behavior is verified separately by backend tests.

Commands:

```powershell
.venv/Scripts/python -m pytest -q --basetemp=.pytest-phase5-demo-final-tmp -o cache_dir=.pytest-phase5-demo-cache
cd frontend
npm run typecheck
npm run lint
npm run build
# Optional production browser check, in separate terminals:
npm run start -- --port 3015
# Repository root:
.venv/Scripts/python scripts/verify_phase5_browser.py
.venv/Scripts/python -m scripts.verify_phase5_assets
```

The browser driver/Chrome were already installed from the prior Phase 5 verification. Browser evidence is in `PHASE5_BROWSER_RESULTS.json`. The temporary production test server is stopped after verification.

## Files changed

Added:

- `app/services/ai/demo_service.py` — local routing, clarification and result templates.
- `tests/test_ai_demo.py` — demo/provider/isolation/no-network coverage.
- `PHASE5_DEMO_MODE_REPORT.md` — this report.

Modified:

- `app/config.py` — validated safe provider default.
- `app/services/ai/coach_service.py` — provider dispatch and bounded demo clarification state; existing OpenAI loop retained.
- `app/services/ai/schemas.py` — response provider metadata.
- `app/api/routes/ai.py` — authenticated provider metadata endpoint.
- `frontend/components/ai/coach-view.tsx` — provider-aware label/disclosure.
- `tests/test_ai_coach.py` — select OpenAI explicitly in the existing test fixture.
- `.env.example` — safe demo default and unchanged existing model setting.
- `.env` — ignored local configuration; provider selection only, other values preserved.
- `README.md` — local demo instructions and explicit optional OpenAI setup.
- `scripts/verify_phase5_browser.py` — provider metadata and demo-label assertions.
- `PHASE5_BROWSER_RESULTS.json` — regenerated UI evidence.

No existing financial service, tool registry/executor, calculation engine, authentication implementation or database schema was changed. Phase 6 has not started and nothing has been deployed.
