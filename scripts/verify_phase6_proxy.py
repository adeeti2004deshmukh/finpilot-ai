"""Real local same-origin browser flow, disposable SQLite DB, no external AI calls.

Build frontend with BACKEND_URL=http://127.0.0.1:8016 and NEXT_PUBLIC_API_URL=''
first. Requires optional installed Playwright/Chrome. Does not deploy or touch
the application's existing database. Artifacts remain in an ignored directory.
"""
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
from uuid import uuid4

import httpx
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
UI = "http://localhost:3016"
API = "http://127.0.0.1:8016"


def wait(url, process):
    for _ in range(120):
        if process.poll() is not None:
            raise RuntimeError("Local test server exited; inspect ignored test logs")
        try:
            if httpx.get(url, timeout=1).status_code < 500:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.25)
    raise RuntimeError("Local test server did not become ready")


def main():
    directory = ROOT / ".pytest-phase6-proxy-artifacts" / uuid4().hex
    assert directory.resolve().is_relative_to(ROOT.resolve())
    directory.mkdir(parents=True)
    env = dict(os.environ, APP_ENV="development", DATABASE_URL="sqlite:///" + (directory / "test.db").as_posix(),
               FRONTEND_URL=UI, BACKEND_URL=API, NEXT_PUBLIC_API_URL="", AI_PROVIDER="demo", OPENAI_API_KEY="",
               SESSION_COOKIE_NAME="finpilot_session", SESSION_COOKIE_SAMESITE="lax")
    children, logs, checks, errors = [], [], [], []
    try:
        log = (directory / "initialization.log").open("w")
        logs.append(log)
        subprocess.run([sys.executable, "-m", "scripts.initialize_database", "--demo"], cwd=ROOT, env=env, stdout=log, stderr=log, check=True)
        for name, command, cwd in (
            ("backend", [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8016", "--no-access-log"], ROOT),
            ("frontend", ["node", "node_modules/next/dist/bin/next", "start", "--port", "3016"], ROOT / "frontend"),
        ):
            log = (directory / (name + ".log")).open("w")
            logs.append(log)
            process = subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=log)
            children.append(process)
            wait(API + "/health" if name == "backend" else UI + "/login", process)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, channel="chrome")
            try:
                context = browser.new_context()
                context.set_default_timeout(30000)
                page = context.new_page()
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(UI + "/")
                page.wait_for_url(UI + "/login")
                checks.append("Unauthenticated homepage redirects to login")
                password = secrets.token_urlsafe(24) + "A9"
                email = "phase6-" + uuid4().hex + "@example.com"
                headers = {"X-FinPilot-Request": "1", "Origin": UI}
                response = context.request.post(UI + "/api/auth/register", data={"name": "Proxy Verification", "email": email, "password": password, "confirm_password": password}, headers=headers)
                assert response.status == 201
                user_id = response.json()["id"]
                assert context.request.post(UI + "/api/auth/onboarding", data={"name": "Proxy Verification", "monthly_income": "73127.43", "typical_essential_expenses": "30000", "risk_tolerance": "MODERATE"}, headers=headers).status == 200
                cookie = next(c for c in context.cookies() if c["name"] == "finpilot_session")
                assert cookie["domain"] == "localhost" and cookie["httpOnly"] and cookie["sameSite"] == "Lax"
                assert context.request.get(UI + "/api/auth/me").json()["id"] == user_id
                checks.append("Real registration/onboarding through Next.js rewrite; host-only HttpOnly first-party cookie round trip")
                for path in ("/", "/transactions", "/budget", "/goals", "/investments", "/simulator", "/alerts", "/settings"):
                    page.goto(UI + path)
                    page.locator(".page-content").wait_for()
                    assert "Proxy Verification" in page.locator(".topbar").inner_text()
                checks.append("Dashboard, transactions, budgets, goals, investments, simulator, alerts and settings load")
                page.goto(UI + "/affordability")
                page.locator("#purchase-item").fill("Test phone")
                page.locator("#purchase-price").fill("1000")
                page.get_by_role("button", name="Analyze affordability", exact=True).click()
                page.locator(".afford-score-card").wait_for()
                page.goto(UI + "/what-if")
                page.locator("#scenario-amount").fill("1000")
                page.get_by_role("button", name="Compare scenario", exact=True).click()
                page.locator(".what-if-compare-grid").wait_for()
                checks.append("Affordability and What-If use real deterministic services through proxy")
                page.goto(UI + "/ai-coach")
                page.get_by_text("Demo AI Coach", exact=True).wait_for()
                assert "No external AI API calls" in page.locator(".coach-privacy").inner_text()
                page.locator("#coach-prompt").fill("Show my financial summary")
                page.get_by_role("button", name="Send question", exact=True).click()
                page.locator(".coach-message-assistant").wait_for()
                assert "73,127.43" in page.locator(".coach-message-assistant").inner_text()
                checks.append("Demo AI Coach uses newly registered account's actual financial values without an API key")
                assert context.request.get(UI + "/api/me/dashboard").headers["cache-control"] == "no-store"
                checks.append("Private proxied API response preserves no-store")
                other = browser.new_context()
                other.request.post(UI + "/api/auth/register", data={"name": "Other", "email": "other-" + uuid4().hex + "@example.com", "password": password, "confirm_password": password}, headers=headers)
                assert other.request.get(UI + f"/api/users/{user_id}").status == 404
                other.close()
                checks.append("Second real session cannot read first user's account")
                page.get_by_role("button", name="Sign Out", exact=True).click()
                page.wait_for_url(UI + "/login")
                assert context.request.get(UI + "/api/me/dashboard").status == 401
                page.locator("form[data-hydrated=true]").wait_for()
                page.locator("#login-email").fill(email)
                page.locator("#login-password").fill(password)
                page.get_by_role("button", name="Sign In", exact=True).click()
                page.wait_for_url(UI + "/")
                page.locator(".dashboard-page").wait_for()
                checks.append("UI logout invalidates session; UI login restores correct account through proxy")
                page.set_viewport_size({"width": 390, "height": 844})
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                assert not errors
                checks.append("Mobile dashboard has no horizontal overflow; no browser page errors")
            finally:
                browser.close()
        result = {"scope": "Real local Next.js production server -> FastAPI -> disposable SQLite. HTTP/local cookies; NOT a live HTTPS/Vercel/PostgreSQL test.", "result": "PASS", "checks": checks, "page_errors": errors}
        (ROOT / "PHASE6_PROXY_BROWSER_RESULTS.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
    finally:
        for child in reversed(children):
            child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        for log in logs:
            log.close()


if __name__ == "__main__":
    main()
