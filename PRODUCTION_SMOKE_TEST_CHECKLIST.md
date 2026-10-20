# Production Smoke Test Checklist

Run manually after reviewing the Phase 6 report and deploying. Use disposable accounts and synthetic figures, not real financial credentials. Record the tested release, date, browser, frontend URL and backend URL privately. Do not include tokens, connection strings or passwords in screenshots/reports.

## Hosting and configuration

- [ ] Frontend homepage loads over HTTPS and redirects unauthenticated users to login.
- [ ] Backend `/health` reports app status, and `/ready` confirms database connectivity without connection details.
- [ ] `alembic current` is at the intended head; initialization/catalog succeeded.
- [ ] Frontend `/api/*` proxy targets the intended backend; no browser request goes to localhost.
- [ ] Backend `FRONTEND_URL` matches the stable frontend origin; unapproved origins fail CORS/CSRF.
- [ ] Session cookie is HttpOnly, Secure, host-only and has the configured SameSite/expiry.
- [ ] Private API responses and login/logout use `Cache-Control: no-store`; CDN/proxy does not cache personal data.

## Personal account flow

- [ ] Register Account A; duplicate registration and malformed credentials fail safely.
- [ ] Complete onboarding; new account has no seeded demo transactions/budgets/goals.
- [ ] Dashboard shows Account A's income, savings, expenses, goals and health.
- [ ] Create a transaction and check dashboard/category totals.
- [ ] Edit the transaction and check updated totals; delete a disposable transaction and confirm deletion.
- [ ] Create a category budget; verify actual spending, remaining amount and status.
- [ ] Create a goal; verify target/date/progress/monthly requirement.
- [ ] Affordability runs with explicit price/date/payment details and returns warnings/alternatives.
- [ ] What-If displays current/projected deterministic values without modifying saved finances.
- [ ] Investment Planner shows priorities, safety buffer, goal allocations, warnings and educational categories.
- [ ] SIP/RD/FD simulator works with explicit rate/duration assumptions and labels projections as estimates.
- [ ] Alerts and Settings load; save an allowed profile update and verify it persists.
- [ ] Demo AI Coach label appears and states no external AI API calls.
- [ ] Coach uses Account A's real spending, health, emergency reserve, goals and priorities.
- [ ] Purchase question asks for missing inputs; 'Cash, today' and 'wait six months' retain the right purchase.
- [ ] Unsupported questions receive clarification/capability limits rather than invented values.
- [ ] Transfers, trades, guaranteed-return requests and requests for another user's data are safely redirected.

## Isolation, demo account and session behavior

- [ ] Register Account B with different synthetic data in a separate browser context.
- [ ] Account B cannot read/change Account A's transactions, budgets, goals, profile, preferences, alerts, plans or account IDs.
- [ ] Account B cannot reuse Account A's coach conversation UUID; browser cannot select a user via tool arguments.
- [ ] Log out A; a replay of its old cookie cannot access private endpoints.
- [ ] Login again; correct account/data returns without prior-account UI state or localStorage credentials.
- [ ] If explicitly seeded, Explore Demo opens the separate synthetic account with a visible read-only banner.
- [ ] Demo account saves remain blocked; safe read/simulation and Demo AI Coach still work.

## UX and failure checks

- [ ] Mobile widths show readable navigation/forms/chat and no horizontal overflow.
- [ ] Keyboard focus, Enter-to-send, loading states, empty states and retry states are usable.
- [ ] New conversation resets chat; expired context gives a clear recovery message.
- [ ] Missing/unreachable backend displays a safe error instead of stale private data.
- [ ] Expected rate-limit response is 429 with retry guidance; oversized/malformed input fails safely.
- [ ] Unexpected server errors expose no stack trace, financial payload, cookie or credential to clients/logs.
- [ ] Educational disclaimer remains visible; no claim of guaranteed returns or transaction execution.
- [ ] Production JavaScript contains no database URL, real OpenAI key or authentication secret.

## Operations

- [ ] Verify provider-specific cookie forwarding and third-party-cookie behavior on real HTTPS domains.
- [ ] Verify trusted proxy IP configuration without trusting arbitrary forwarding headers.
- [ ] Confirm hosting/database plans, retention, monitoring and backup settings match the intended public portfolio scope.
- [ ] Test backup restore into a separate database and document a safe rollback path.
- [ ] Confirm one worker/instance until shared conversation/rate storage is implemented.

Do not mark live-host, managed-PostgreSQL or restore checks complete based solely on local SQLite/unit-test results.
