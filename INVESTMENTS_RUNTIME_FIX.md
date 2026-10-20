# Investment Planner runtime fix

## Confirmed root cause

`plan.funding_ledger` was undefined at `investments-view.tsx:78`, where the component called `.map()`.

The running API at `http://localhost:8000/api/investment/plan/1` returned HTTP 200 but served an older Phase 4 contract. Its live OpenAPI schema was also old. It omitted:

- `funding_ledger`
- `allocation_total`
- `goal_contributions`
- `emergency_fund_contribution`
- `scheduled_goal_contributions`
- `funded_existing_goal_contributions`
- `savings_goal_overlap`

The on-disk Pydantic response model and TypeScript `InvestmentPlan` interface already agreed that these fields are required. This was a stale running backend, not a nullable ledger, incorrect property name, loading-state problem, or a Phase 3 endpoint being used. The old Uvicorn command did not enable reload and retained its previously imported code. TypeScript could not detect the discrepancy because the generic API helper cast fetched JSON to `T` without runtime validation.

A real headless browser reproduced `Cannot read properties of undefined (reading 'map')` before the fix. The Next development log identified the exact `plan.funding_ledger.map(...)` expression in the stack.

## Root fix and defensive handling

Identified the actual FinPilot backend launcher/worker command lines, stopped only those confirmed processes, and restarted the same project on port 8000 with `--reload`. Windows required execution permission for Uvicorn's worker pipe. The current live response now validates against the source Pydantic model and returns a real ledger (three rows for the current demo data). The existing frontend dev server on port 3000 was preserved.

Added runtime checks in `frontend/services/investment-contract.ts`, used by the centralized finance API client:

- Mandatory financial fields, ledger, allocations, priorities and goal analysis are checked before reaching React state. Missing/malformed mandatory data produces a visible, retryable API contract error naming the field and advising a backend restart. No financial amounts or ledger entries are fabricated to conceal a stale backend.
- Optional display-only arrays (warnings, methodology and explanatory category metadata) safely normalize absent/null values to empty lists. Malformed non-array values still produce an error.
- Goal-list, category-list, comparison and nested allocation/category rows are checked before mapping them. Empty list endpoint results are safe, while incompatible objects are rejected.
- The page now displays suitable messages for empty ledger, goal, priority, relevance and category collections. Existing page styling/layout remains intact.

No backend financial formula, response schema or TypeScript interface needed changing. The live backend was brought into agreement with the existing source contract. No Phase 5/OpenAI work was performed.

## Every mapped value reviewed

| Component input | Guarantee |
|---|---|
| `capacity` | Local six-element array |
| `chartData` mapping of filtered `plan.allocations` | Required allocation list; row amount/percentage checked |
| `plan.funding_ledger` | Required list; each row purpose, amount and reason code checked |
| `plan.goal_analysis` | Required list; funded values and displayed string fields checked |
| `plan.financial_priorities` | Required list; displayed strings checked before `.toLowerCase()` |
| `plan.allocations` | Required list with valid rows |
| `allocation.categories_to_explore` | Explanatory list normalizes to empty if absent/null; rows checked |
| `plan.warnings` | Optional display string list normalized to empty |
| `goals` | Initialized empty; API list/row checks before assignment |
| `comparison.categories_to_explore` | Required comparison list with explained, bounded relevance scores |
| `categories` | Initialized empty; API list/metadata row checks before assignment |

The methodology `.join()` and array `.filter()`/`.length` accesses are covered by the same validation. Required financial collections have not simply been hidden behind optional chaining.

## Verification performed

- Relevant Phase 4/backend contract tests: **84 passed**.
- Frontend contract regressions: **9 passed**, including the exact missing-ledger response, missing accounting fields, empty collections, malformed nested rows, optional metadata and stale comparison goal schemas.
- Frontend TypeScript: **PASS**.
- Full frontend ESLint: **PASS**, no warnings/errors.
- Frontend production build: **PASS**, all 14 static pages generated.
- Browser: **PASS** at `http://localhost:3000/investments` with the actual API at port 8000. Hydration completed without page errors or browser console errors. Switching goals works.
- Browser compared all six displayed capacity amounts to the live API, and checked ledger/goal-analysis rows, priorities, purpose allocations, categories, SIP/RD/FD comparison content, warnings and the unallocated-buffer display.
- Browser regression cases: missing mandatory ledger produces a controlled error; empty financial lists render safely; missing optional display metadata renders safely. No uncaught page errors in these cases.
- Inspected the Next dev-server log: it records the original line-78 crash before the restart; the subsequent verification entries show no new runtime errors. An informational development cache-bypass warning is unrelated to this crash.

Browser evidence is in `INVESTMENTS_BROWSER_RESULTS.json`. Reusable checks:

```powershell
cd frontend
node --test tests/investment-contract.test.mjs
```

`scripts/verify_investments_browser.py` uses an installed Playwright Python runtime and browser against the two local servers; it was executed with the already installed Anaconda Playwright environment. It reads existing data and intercepts responses in isolated browser contexts for regression cases; it does not edit financial records.

## Files changed

- `frontend/services/investment-contract.ts` — new runtime response validation/normalization.
- `frontend/services/finance.ts` — apply validation before returning planner API data.
- `frontend/components/investments/investments-view.tsx` — explicit empty-collection messages and empty goal selection handling.
- `frontend/tests/investment-contract.test.mjs` — frontend contract regression tests.
- `tests/test_investment_planner_contract.py` — backend response/OpenAPI contract regression.
- `scripts/verify_investments_browser.py` — real browser and hostile/empty response checks.
- `INVESTMENTS_BROWSER_RESULTS.json` — browser results.
- `INVESTMENTS_RUNTIME_FIX.md` — this report.

The updated backend and existing frontend development server remain running for manual retesting. Refresh `/investments` in any previously errored browser tab.
