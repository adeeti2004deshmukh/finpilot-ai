# FinPilot AI: Phase 4 audit and bounded repair

Historical audit: the stabilization pass below has since been completed. Use [PHASE4_FINAL_VERIFICATION.md](PHASE4_FINAL_VERIFICATION.md) for the current status and closure of each remaining item. The original before/after classifications are preserved here as history.

Date: 17 October 2026. Phase 4 remains PARTIAL. Work stopped after a coherent regression-repair subset. Phase 5 and OpenAI integration were not started.

## Repository and attribution limits

The supplied workspace has no `.git` directory. `git` is also absent from PATH. Git status, diff, historical README changes, dependency changes, and exact Copilot authorship therefore cannot be established. “Already present” below means observed before Codex edits, not proven authorship. No repository was initialized and no existing work was reset.

Inspected backend routes, services, calculation engine, schemas, ORM models, migration, tests, frontend pages/components, API client/types, manifests, lockfile, configuration, and README. Architecture is FastAPI routes → services → deterministic Decimal calculations → SQLAlchemy/database; frontend uses the typed centralized API client. No LLM dependency or invocation was found in the inspected Phase 4 implementation.

Models remain the existing users, profiles, categories, transactions, merchant rules, budgets, goals, investment preferences, alerts, subscriptions, and AI-insight tables. The existing AI-insight table does not itself indicate an AI integration. One initial Phase 2 migration exists. No Phase 4 schema migration is needed for the in-memory calculations inspected. Alembic current/head is `bf8c5f1a4a74`; local SQLite metadata check detects no new upgrade operations. PostgreSQL execution was not tested; the initial migration contains repeated enum/check declarations that deserve a separate PostgreSQL migration check.

Backend requirements contain FastAPI, Pydantic settings, Uvicorn, pytest, httpx, SQLAlchemy, Alembic, psycopg and email validation. Frontend package/lockfile root declarations agree: Next 16.4.2, React/React DOM 19.3.0, TypeScript, ESLint, Recharts, Lucide, Manrope and Tailwind tooling. Codex changed no dependency manifests or lockfiles. Historical dependency changes cannot be reconstructed.

## 1. What was already implemented

All 17 requested feature areas had at least some code. Existing services included planning context, priorities, goal analysis, category metadata/relevance, purpose allocation, affordability, health breakdown, monthly plan, what-if and insights. Thin routes expose investment plan/categories/comparison, affordability, financial health, monthly plan, what-if and financial insights. Frontend investment, affordability and what-if pages and dashboard additions already existed. README already documented them. Initial backend suite: 41 passing tests.

## 2. Initial feature classification and current status

COMPLETE means the inspected feature exists with no specific outstanding implementation gap identified in this audit; it does not imply browser or production certification. PARTIAL means usable implementation with named remaining gaps. BROKEN means a reproduced or directly identifiable incorrect supported case. No feature was NOT STARTED.

| # | Expected Phase 4 feature | Before repairs | After repairs | Evidence / outstanding scope |
|---|---|---|---|---|
| 1 | Savings / surplus / investable separation | PARTIAL | PARTIAL | Distinct calculations exist; legacy goal top-ups were double-counted. Fixed that and exposed contribution fields. Savings-to-goal overlap is assumed because transfers have no goal links. |
| 2 | Safety buffer | COMPLETE | COMPLETE | Configurable rate/minimum and available-cash cap; currency rounding corrected. |
| 3 | Financial Priority Engine | PARTIAL | PARTIAL | Deterministic cash-flow, debt, emergency and goal priorities exist. Priority severity ordering and allocation funding order are not one unified policy. |
| 4 | Goal horizon / feasibility | BROKEN | PARTIAL | Horizon boundaries exist; elapsed deadline incorrectly could be ON_TRACK. Deadline fixed; shared-capacity and missing-date semantics remain. |
| 5 | Investment category knowledge model | COMPLETE | COMPLETE | Eight categories with risk, liquidity, horizons, advantages, limitations and uncertainty explanations. |
| 6 | Personalized purpose allocation | PARTIAL | PARTIAL | Uses user debt, reserves, goals and risk; only very-short/short goals get incremental funding before the generic long-term residual. |
| 7 | Deterministic allocation reason codes | COMPLETE | COMPLETE | Allocations and priorities carry stable rule codes and explanations. |
| 8 | Investment Plan API | COMPLETE | COMPLETE | Typed `/api/investment/plan/{user_id}` response and frontend client exist; underlying planning limitations remain listed separately. |
| 9 | Improved Investment Planner frontend | PARTIAL | PARTIAL | Capacity, priorities, allocations, why-details and goal category comparison exist; expense hint fixed. Goal feasibility and full contribution ledger still need UI exposure. |
| 10 | Goal-based SIP/RD/FD relevance | COMPLETE | COMPLETE | Deterministic horizon/risk/emergency/goal-type scoring with category explanations. Scores are heuristics, not forecasts. |
| 11 | Can I Afford This backend/frontend | PARTIAL | PARTIAL | Cash/EMI input and results exist; unfunded cash fixed and displayed. Broader goal-protection/future-date modeling remains limited. |
| 12 | Affordability score and alternatives | BROKEN | PARTIAL | Unavailable upfront cash could receive a reassuring score; inconsistent payment schedules accepted. Fixed. Wait/save alternatives still show targets rather than fully re-evaluated feasible plans. |
| 13 | Financial Health breakdown | COMPLETE | COMPLETE | Existing 30/30/20/20 formula exposed with components, explanations and actions; score unchanged. |
| 14 | Monthly Action Plan | PARTIAL | PARTIAL | Service/API exist; paise over-allocation fixed. Dashboard shows one action, not a complete monthly ledger. |
| 15 | What-If Engine | BROKEN | PARTIAL | Five scenario types exist. Food reduction used wrong bucket/fell back to unrelated spend; fixed. Food recognition still depends on category naming. |
| 16 | Deterministic Financial Insights | PARTIAL | PARTIAL | Reason-coded category, savings, emergency, goal and capacity insights exist. Current incomplete month vs previous full-month comparisons need clearer coverage context. |
| 17 | Structured service functions | PARTIAL | PARTIAL | Structured Pydantic/context service outputs exist. Consistent user-scoped function facade is unfinished. |

## 3. What Codex changed

- Overdue unfunded goals cannot be ON_TRACK merely because the planned contribution exceeds their gap. Completed goals remain ON_TRACK.
- Unfunded upfront cash, negative post-purchase monthly cash flow or zero income forces affordability components/score to zero. An explicit upfront shortfall and warnings explain the result. Cash rejects EMI fields; EMI payments plus down payment must cover price.
- Food scenarios reduce only recorded `food` categories, respecting essential/discretionary classification and capping reductions at their spending. They do not persist changes.
- Debt, emergency, safety and extra-buffer reserves are rounded before subtraction; five paise cannot become six paise of suggested allocations.
- Removed short-term top-up double-counting from the legacy available-surplus endpoint.
- Added explicit `goal_contributions` and `emergency_fund_contribution`. `unallocated_buffer` now excludes the separately reported safety buffer. These API semantics are documented in README. Contribution fields represent scheduled plus proposed funding, not completed transfers. Emergency-goal contributions overlap the goal total and must not be added again.
- Removed the duplicate dashboard expense donut and misplaced action fragment; kept the existing layout and used the already calculated actionable monthly-plan line in its action strip.
- Corrected the planner expense explanation; added the unfunded upfront amount to affordability results.
- Added seven regression tests and this audit report.

## 4. Files added or modified

Added: `PHASE4_AUDIT.md`.

Modified:

- `app/services/goal_analysis_service.py`
- `app/services/affordability_service.py`
- `app/services/finance.py`
- `app/services/what_if_service.py`
- `app/services/investment_allocation_service.py`
- `app/schemas/planning.py`
- `frontend/types/api.ts`
- `frontend/components/dashboard/dashboard-view.tsx`
- `frontend/components/investments/investments-view.tsx`
- `frontend/components/affordability/affordability-view.tsx`
- `tests/test_phase4_financial_intelligence.py`
- `README.md`

Validation also regenerates ignored `.next` outputs and may update `frontend/tsconfig.tsbuildinfo`; these are not source changes. No database records, models, migrations, dependency files or Phase 1 engine formulas were intentionally changed.

## 5–13. Engine and feature status

The table above gives individual status for Financial Priority Engine, Investment Planner, goal analysis, SIP/RD/FD relevance, Can I Afford This, Financial Health, Monthly Action Plan, What-If and Financial Insights. Category guidance remains educational: no individual stocks, named funds or guaranteed returns. Allocation retains a safety buffer and additional unallocated cash rather than treating all leftovers as investable.

## 14. Backend validation

- Before edits: 41 passed.
- Final: 48 passed, including existing Phase 1 engine/API and Phase 2 persistence/API tests and Phase 4 tests.
- Command: `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`.
- One existing Starlette/httpx TestClient deprecation warning. No dependency change made for it.
- Alembic heads/current/check pass on the existing local SQLite database; no new upgrade operations detected. No migration upgrade or seed was run against user data.
- Existing tests provide automated Phase 1–3 regression evidence; they do not replace live browser checks or a PostgreSQL migration run.

## 15. Frontend validation

- Baseline TypeScript: PASS. Baseline full ESLint: PASS.
- Final TypeScript `tsc --noEmit`: PASS.
- Final ESLint across app, components, services, types, utils and config: PASS, no warnings/errors.
- Final production `next build`: PASS; all 14 static pages generated, including existing pages plus affordability/what-if.
- The first sandboxed build compiled but Windows denied worker spawn (`EPERM`); the approved execution completed successfully. Node/npm were absent from PATH; used installed Node 24.20.0 under WinGet, without installing dependencies.
- No interactive browser or responsive visual certification was performed.

## 16. Exact remaining Phase 4 work

1. Make one explicit funding ledger for recorded savings, scheduled contributions and funded contributions. Preserve or expose the current overlap assumption until savings can be linked to goals; scheduled contributions must not be presented as cash actually funded.
2. Allocate medium-term needs before a generic long-term residual, reconcile priority severity with actual allocation order, and attribute longer-term allocations to goals where appropriate. Existing emergency-goal top-ups should also flow through effective goal analysis.
3. Evaluate multiple goals against shared available capacity. A large stored contribution can still make a goal look ON_TRACK despite insufficient household funding. Missing-date goals currently use the stored contribution as their required amount, which is not a dated feasibility result. Harmonize comparison/health/investment-plan goal analysis.
4. Expand the planner's ledger and feasibility display and expose the full monthly action plan in the existing design. Avoid changing the Phase 3 dashboard layout.
5. Protect dated goal capital and all priority reserves consistently in affordability. Its current goal-impact calculation only uses incremental short-term reserve and does not model each goal's full future cash flow. Evaluate each wait/save alternative against available capacity instead of returning only a principal target; clarify the buy-now label when a future date is supplied.
6. Define food categories independent of English naming and return a useful no-matching-spend warning. Consider explicit scenario affordability warnings when extra savings exceed available capacity.
7. Add partial-month/data-coverage context to insight comparisons. Keep insights deterministic.
8. Finish the consistent structured service facade: `get_financial_summary`, `get_financial_health`, `get_financial_priorities`, `get_monthly_plan`, `get_investment_plan`, `analyze_goal(user_id, goal_id)`, `compare_investment_categories`, `analyze_affordability(user_id, purchase)`, `run_what_if_scenario`. Existing context/ORM functions should be reused with an explicit injected database session and ownership checks. This prepares service interfaces only; no AI integration is authorized.
9. Run PostgreSQL migration checks and interactive browser checks. Recover the real Git checkout for historical diff/attribution if needed; do not overwrite this workspace.

## 17. Manual test checklist

Use existing local backend/frontend startup instructions. Test against disposable/demo records where changing data.

- `/`: one expense donut, debt separate, existing chart layout intact; financial-health components sum to displayed score; action strip, emergency progress, goals, budgets and deterministic insights load.
- `/transactions`: create/edit/delete an expense and a SAVINGS transfer; filters and pagination; confirm savings changes without equating savings with surplus.
- `/budget`: create/edit/delete a budget and check warning/over-budget totals against transactions.
- `/goals`: create/edit/delete a dated goal; test overdue, fully funded, missing-date and multiple competing goals. Compare with planner and note the shared-capacity limitations above.
- `/investments`: check income − displayed expenses − debt = monthly surplus; recorded savings, safety reserve and investable capacity are distinct; inspect Why this, warnings and goal selection. Compare short vs long horizons and low vs high risk. Read `goal_contributions`, emergency contribution and unallocated reserve via `/docs` until the full ledger is surfaced.
- `/affordability`: cash within savings, cash above all savings (HIGH_RISK + upfront shortfall), valid EMI, installment exceeding surplus, missing/invalid EMI terms. Compare wait/save targets; these are not yet fully scored alternatives.
- `/what-if`: exercise all five scenario types; income/rent changes, recorded essential and discretionary food, no food category, extra savings, and goal delay. Refresh real data afterward to verify scenarios were not saved.
- `/simulator`: SIP/RD/FD including zero-rate case and selected time horizons; values remain educational projections.
- `/settings`: edit/save and reload profile/user values; verify downstream dashboard/planner refresh.
- `/ai-coach` and `/alerts`: existing placeholders remain placeholders; no AI request is made.
- Check small-screen navigation, loading/error/empty states, backend-unavailable retries and production-server rendering. These have not been browser-verified in this run.
