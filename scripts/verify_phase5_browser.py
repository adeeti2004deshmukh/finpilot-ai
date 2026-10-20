"""UI checks against the production frontend with synthetic API responses only.

Start `npm run start -- --port 3015` first. No database, real credentials or
external model calls are used. Playwright is an optional local test dependency.
"""
import asyncio
import json
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright

ROOT = "http://localhost:3015"


async def main():
    checks, requests, errors = [], [], []
    mode = "error"
    cid = "12345678-1234-4234-8234-123456789abc"
    authenticated = False
    headers = {"Access-Control-Allow-Origin": ROOT, "Access-Control-Allow-Credentials": "true",
               "Access-Control-Allow-Headers": "Content-Type, X-FinPilot-Request", "Access-Control-Allow-Methods": "GET, POST, OPTIONS"}

    async def api(route):
        request = route.request
        if request.method == "OPTIONS":
            return await route.fulfill(status=204, headers=headers)
        path = urlparse(request.url).path
        if path == "/api/ai/config":
            return await route.fulfill(headers=headers, json={"provider": "openai"})
        if path == "/api/auth/me":
            return await route.fulfill(status=200 if authenticated else 401, headers=headers, json={
                "id": 101, "name": "UI Test", "email": "ui@example.com", "age": 28,
                "is_demo": False, "onboarding_completed": True})
        if path == "/api/ai/chat":
            payload = request.post_data_json
            requests.append(payload)
            assert "user_id" not in payload
            assert request.headers.get("x-finpilot-request") == "1"
            await asyncio.sleep(0.8)
            if mode == "error":
                return await route.fulfill(status=503, headers=headers, json={"detail": "AI Coach is not configured. Set OPENAI_API_KEY in the backend .env file and restart the backend."})
            return await route.fulfill(headers=headers, json={"provider": "demo", "message": "Based on your current FinPilot data, review your food budget. <img src=x onerror=alert(1)>",
                "conversation_id": cid, "tools_used": ["get_spending_analysis", "get_budget_status"],
                "suggested_followups": ["What should I prioritize this month?"], "warnings": ["Recorded activity only; the current month may be incomplete."]})
        return await route.fulfill(status=404, headers=headers, json={"detail": "Synthetic test: endpoint unavailable"})

    async with async_playwright() as playwright:
        # Reuse installed Chrome; the script does not download or change browsers.
        browser = await playwright.chromium.launch(headless=True, channel="chrome")
        try:
            context = await browser.new_context()
            await context.route("**/api/**", api)
            page = await context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            await page.goto(ROOT + "/ai-coach")
            await page.wait_for_url(ROOT + "/login")
            checks.append("Unauthenticated coach route redirects to login")
            authenticated = True
            await context.add_cookies([{"name": "finpilot_session", "value": "synthetic-ui-session", "url": ROOT, "httpOnly": True, "sameSite": "Lax"}])
            await page.goto(ROOT + "/ai-coach")
            await page.get_by_role("heading", name="FinPilot AI Coach").wait_for()
            assert await page.locator(".nav-soon").count() == 0
            checks.append("Authenticated coach page and six suggested questions render; Soon badge removed")
            assert await page.locator(".coach-question-list button").count() == 6
            await page.get_by_role("button", name="Where am I overspending?", exact=True).click()
            await page.get_by_role("status").filter(has_text="Reviewing").wait_for()
            assert await page.get_by_role("button", name="Send question", exact=True).is_disabled()
            checks.append("Question submits with CSRF header; loading state disables duplicate submissions")
            await page.get_by_role("alert").filter(has_text="OPENAI_API_KEY").wait_for()
            assert await page.locator("#coach-prompt").input_value() == "Where am I overspending?"
            checks.append("Missing-key error renders configuration guidance and preserves question for retry")
            mode = "success"
            await page.get_by_role("button", name="Send question", exact=True).click()
            await page.locator(".coach-message-assistant").wait_for()
            assert await page.locator(".coach-message-assistant img").count() == 0
            await page.get_by_text("Analyzed your spending", exact=True).wait_for()
            await page.get_by_text("Checked your budgets", exact=True).wait_for()
            await page.get_by_text("Demo AI Coach", exact=True).wait_for()
            assert "No external AI API calls" in await page.locator(".coach-privacy").inner_text()
            checks.append("Demo provider metadata shows local label and local-only privacy disclosure")
            checks.append("Response, readable tool indicators and warning render; provider markup remains plain text")
            await page.locator(".coach-followups").get_by_role("button").click()
            await page.wait_for_function("document.querySelectorAll('.coach-message-assistant').length === 2")
            assert requests[-1]["conversation_id"] == cid
            checks.append("Suggested follow-up submits server conversation ID")
            await page.get_by_role("button", name="New conversation", exact=True).click()
            assert await page.locator(".coach-message").count() == 0
            await page.locator("#coach-prompt").fill("Review my goals")
            await page.get_by_role("button", name="Send question", exact=True).click()
            await page.locator(".coach-message-assistant").wait_for()
            assert "conversation_id" not in requests[-1]
            checks.append("New conversation clears visible history and prior conversation ID")
            await page.set_viewport_size({"width": 390, "height": 844})
            assert await page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            checks.append("Mobile viewport has no horizontal page overflow")
            assert not errors, errors
            checks.append("No browser page errors")
        finally:
            await browser.close()
    result = {"scope": "Production UI with synthetic authenticated API; no live OpenAI call", "checks": checks, "page_errors": errors}
    Path("PHASE5_BROWSER_RESULTS.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
