"""Real browser flow with a uniquely identified disposable local account.

Uses the installed Playwright runtime. Only the generated account is removed
afterward; canonical demo and pre-existing user records are never modified.
"""
from datetime import date, timedelta
import json
from pathlib import Path
import secrets
import sqlite3
from uuid import uuid4

from playwright.sync_api import sync_playwright

ROOT = "http://localhost:3000"
API = "http://localhost:8000"


def main():
    email = "phase45-browser-" + uuid4().hex + "@example.com"
    password = secrets.token_urlsafe(20) + "A9"
    created_id = None
    results, errors, console_errors = [], [], []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context()
            context.set_default_timeout(45000)
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" and "/api/auth/me" not in message.location.get("url", "") else None)
            page.goto(ROOT + "/investments")
            page.wait_for_url(ROOT + "/login")
            page.get_by_role("heading", name="Welcome back").wait_for()
            results.append("Unauthenticated private route redirects to login")
            page.get_by_role("link", name="Create one").click()
            page.locator("form[data-hydrated=true]").wait_for()
            page.locator("#register-name").fill("Browser Verification")
            page.locator("#register-email").fill(email)
            page.locator("#register-password").fill(password)
            page.locator("#register-confirm").fill(password)
            page.get_by_role("button", name="Create Account", exact=True).click()
            page.wait_for_url(ROOT + "/onboarding")
            me = context.request.get(API + "/api/auth/me").json()
            created_id = me["id"]
            assert not me["is_demo"] and not me["onboarding_completed"]
            cookie = next(c for c in context.cookies() if c["name"] == "finpilot_session")
            assert cookie["httpOnly"] and cookie["sameSite"] == "Lax"
            results.append("Registration and HTTP-only session")
            page.locator("#onboard-name").fill("Browser Verification")
            page.get_by_role("button", name="Continue", exact=True).click()
            for field, value in (("income", "65000"), ("essential", "30000"), ("savings", "120000"), ("emergency", "55000")):
                page.locator("#onboard-" + field).fill(value)
            page.get_by_role("button", name="Continue", exact=True).click()
            page.locator("#onboard-months").select_option("custom")
            page.locator("#onboard-custom").fill("7")
            page.get_by_role("button", name="Continue", exact=True).click()
            page.get_by_label("Skip for now").check()
            page.get_by_role("button", name="Continue", exact=True).click()
            page.get_by_role("button", name="Go to my dashboard", exact=True).click()
            page.wait_for_url(ROOT + "/")
            page.get_by_role("link", name="Add your first transaction", exact=True).wait_for()
            assert "Aarav" not in page.locator(".page-content").inner_text()
            dashboard = context.request.get(API + "/api/me/dashboard").json()
            assert dashboard["monthly_expenses_excluding_debt"] == "0.00" and dashboard["monthly_savings"] == "0.00"
            assert dashboard["goals"] == []
            results.append("Five-step onboarding and personal empty dashboard")

            page.goto(ROOT + "/transactions")
            page.get_by_role("button", name="Add transaction", exact=True).wait_for()

            def transaction(merchant, description, amount, kind, category):
                page.get_by_role("button", name="Add transaction", exact=True).click()
                dialog = page.get_by_role("dialog")
                dialog.locator("#transaction-type").select_option(kind)
                dialog.locator("#transaction-merchant").fill(merchant)
                dialog.locator("#transaction-description").fill(description)
                dialog.locator("#transaction-amount").fill(amount)
                dialog.locator("#transaction-category").select_option(label=category)
                dialog.get_by_role("button", name="Add transaction", exact=True).click()
                dialog.wait_for(state="hidden")
                page.get_by_role("cell", name=description, exact=True).wait_for()

            transaction("Employer", "Verification salary", "65000", "INCOME", "Salary")
            transaction("Landlord", "Verification rent", "35000", "EXPENSE", "Housing")
            page.get_by_role("button", name="Edit Verification rent", exact=True).click()
            page.locator("#transaction-amount").fill("34000")
            page.get_by_role("button", name="Save changes", exact=True).click()
            page.get_by_role("dialog").wait_for(state="hidden")
            dashboard = context.request.get(API + "/api/me/dashboard").json()
            assert dashboard["monthly_income"] == "65000.00" and dashboard["monthly_expenses_excluding_debt"] == "34000.00"
            transaction("Verification", "Disposable expense", "10", "EXPENSE", "Other")
            page.get_by_role("button", name="Delete Disposable expense", exact=True).click()
            page.get_by_role("alertdialog").get_by_role("button", name="Delete", exact=True).click()
            page.get_by_role("alertdialog").wait_for(state="hidden")
            page.locator("#merchant-search").fill("Landlord")
            page.get_by_role("cell", name="Verification rent", exact=True).wait_for()
            page.get_by_role("cell", name="Verification salary", exact=True).wait_for(state="hidden")
            results.append("Transaction create/edit/delete/search and salary assumption replacement")

            page.goto(ROOT + "/budget")
            page.get_by_role("button", name="Add budget", exact=True).click()
            page.locator("#budget-category").select_option(label="Housing")
            page.locator("#budget-limit").fill("40000")
            page.get_by_role("dialog").get_by_role("button", name="Create budget", exact=True).click()
            page.get_by_role("dialog").wait_for(state="hidden")
            assert len(context.request.get(API + "/api/me/budgets").json()) == 1
            results.append("Personal budget creation")

            page.goto(ROOT + "/goals")
            page.get_by_role("button", name="Create goal", exact=True).click()
            page.locator("#goal-name").fill("Verification education")
            page.locator("#goal-target").fill("100000")
            page.locator("#goal-date").fill((date.today() + timedelta(days=730)).isoformat())
            page.get_by_role("dialog").get_by_role("button", name="Create goal", exact=True).click()
            page.get_by_role("dialog").wait_for(state="hidden")
            assert len(context.request.get(API + "/api/me/goals").json()) == 1
            results.append("Personal goal creation")

            page.goto(ROOT + "/investments")
            page.locator(".investment-capacity").wait_for()
            page.locator(".relevance-table").wait_for()
            assert context.request.get(API + "/api/me/investment-plan").json()["user_id"] == created_id
            assert "Aarav" not in page.locator(".page-content").inner_text()
            results.append("Authenticated Investment Planner and relevance")
            page.goto(ROOT + "/affordability")
            page.locator("#purchase-item").fill("Verification phone")
            page.locator("#purchase-price").fill("80000")
            page.get_by_role("button", name="Analyze affordability", exact=True).click()
            page.locator(".afford-score-card").wait_for()
            results.append("Authenticated affordability")
            page.goto(ROOT + "/what-if")
            page.locator("#scenario-amount").fill("1000")
            page.get_by_role("button", name="Compare scenario", exact=True).click()
            page.locator(".what-if-compare-grid").wait_for()
            results.append("Authenticated what-if")

            page.goto(ROOT + "/settings")
            page.locator("#settings-name").wait_for()
            assert page.locator("#settings-email").input_value() == email
            assert page.locator("#profile-emergency-target").input_value() == "7"
            page.get_by_role("button", name="Save profile", exact=True).click()
            page.get_by_text("Your profile has been updated.", exact=True).wait_for()
            results.append("Personal Settings and custom emergency target")
            page.get_by_role("button", name="Sign Out", exact=True).click()
            page.wait_for_url(ROOT + "/login")
            assert context.request.get(API + "/api/me/dashboard").status == 401
            page.locator("#login-email").fill(email)
            page.locator("#login-password").fill(password)
            page.get_by_role("button", name="Sign In", exact=True).click()
            page.wait_for_url(ROOT + "/")
            page.locator(".dashboard-page").wait_for()
            assert context.request.get(API + "/api/me/transactions").json()["total"] == 2
            assert len(context.request.get(API + "/api/me/goals").json()) == 1
            assert page.evaluate("Object.keys(localStorage)") == []
            results.append("Logout, login, persisted personal data; no localStorage authentication")

            other = browser.new_context()
            other_page = other.new_page()
            other_page.goto(ROOT + "/login")
            other_page.get_by_role("button", name="Explore Demo", exact=True).click()
            other_page.wait_for_url(ROOT + "/")
            other_page.locator(".demo-banner").wait_for()
            assert "DEMO ACCOUNT" in other_page.locator(".demo-banner").inner_text()
            assert other.request.get(API + "/api/me/dashboard").json()["user_id"] != created_id
            assert other.request.get(API + f"/api/users/{created_id}").status == 404
            assert other.request.put(API + "/api/me/user", data={"name": "Do not modify"}, headers={"X-FinPilot-Request": "1"}).status == 403
            other.close()
            results.append("Separate read-only Aarav demo and cross-user denial")
            context.close()
            browser.close()
        assert not errors, errors
        assert not console_errors, console_errors
        output = {"result": "PASS", "checks": results, "page_errors": errors, "unexpected_console_errors": console_errors}
        Path("PHASE45_BROWSER_RESULTS.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(output, indent=2))
    except Exception:
        print(json.dumps({"completed_checks": results, "page_errors": errors, "console_errors": console_errors}, indent=2))
        raise
    finally:
        if created_id:
            # Delete only the account generated by this invocation, after all
            # browser contexts close. FK cascades cover its financial records.
            assert email.startswith("phase45-browser-") and len(email.split("@")[0]) == len("phase45-browser-") + 32
            with sqlite3.connect("finpilot_dev.db") as db:
                db.execute("PRAGMA foreign_keys=ON")
                db.execute("DELETE FROM users WHERE id=? AND normalized_email=? AND is_demo=0", (created_id, email))


if __name__ == "__main__":
    main()
