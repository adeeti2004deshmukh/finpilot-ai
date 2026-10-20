"""Exercise the hydrated Investment Planner and its API contract failure states."""
import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--expect-crash", action="store_true")
    args = parser.parse_args()
    results = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        login = context.request.post("http://localhost:8000/api/auth/demo", headers={"X-FinPilot-Request": "1"})
        assert login.status == 200
        page = context.new_page()
        errors, console_errors = [], []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.goto("http://localhost:3000/investments", wait_until="networkidle")
        if args.expect_crash:
            page.wait_for_timeout(1500)
            assert any("map" in error and "undefined" in error for error in errors), errors
            print(json.dumps({"reproduced": True, "page_errors": errors, "console_errors": console_errors}, indent=2))
            browser.close()
            return
        page.locator(".investment-capacity").wait_for()
        page.locator(".relevance-table").wait_for()
        page.get_by_text("Monthly funding ledger and goal feasibility", exact=True).click()
        plan = page.request.get("http://localhost:8000/api/me/investment-plan").json()
        assert page.locator(".capacity-item").count() == 6
        assert page.locator(".why-details table").count() == 2
        for index, field in enumerate(("monthly_income", "monthly_expenses", "actual_monthly_savings", "monthly_surplus", "safety_buffer", "investable_surplus")):
            expected = page.evaluate("value => new Intl.NumberFormat('en-IN', {style: 'currency', currency: 'INR', maximumFractionDigits: 0}).format(Number(value))", plan[field])
            assert page.locator(".capacity-item").nth(index).locator("strong").inner_text() == expected
        assert page.locator(".why-details table").nth(0).locator("tbody tr").count() == len(plan["funding_ledger"])
        assert page.locator(".why-details table").nth(1).locator("tbody tr").count() == len(plan["goal_analysis"])
        assert page.locator(".priority-row").count() == len(plan["financial_priorities"])
        assert page.locator(".allocation-row").count() == len(plan["allocations"])
        assert page.locator(".planner-warnings p").count() == len(plan["warnings"])
        categories = page.request.get("http://localhost:8000/api/investment/categories").json()
        assert page.locator(".category-knowledge-row").count() == len(categories)
        assert "Recurring Deposit (RD)" in page.locator(".relevance-table").inner_text()
        assert "Fixed Deposit (FD)" in page.locator(".relevance-table").inner_text()
        assert "Mutual Fund SIP" in page.locator(".relevance-table").inner_text()
        expected_buffer = page.evaluate("value => new Intl.NumberFormat('en-IN', {style: 'currency', currency: 'INR', maximumFractionDigits: 0}).format(Number(value))", plan["unallocated_buffer"])
        assert f"Unallocated buffer: {expected_buffer}" in page.locator(".panel.section-block").first.inner_text()
        select = page.locator("#compare-goal")
        for option in select.locator("option").all():
            if option.get_attribute("value") == select.input_value():
                continue
            select.select_option(option.get_attribute("value"))
            page.locator(".relevance-table").wait_for()
        assert not errors, errors
        assert not console_errors, console_errors
        results.append({"case": "live API and hydrated planner", "page_errors": errors[:], "console_errors": console_errors[:]})
        context.close()

        def exercise(name, transform, expected_error=None):
            context = browser.new_context()
            login = context.request.post("http://localhost:8000/api/auth/demo", headers={"X-FinPilot-Request": "1"})
            assert login.status == 200
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))

            def intercept(route):
                response = route.fetch()
                route.fulfill(response=response, json=transform(response.json()))

            page.route("**/api/me/investment-plan", intercept)
            page.goto("http://localhost:3000/investments", wait_until="networkidle")
            if expected_error:
                alert = page.locator(".error-state[role=alert]")
                alert.wait_for()
                assert expected_error in alert.inner_text(), alert.inner_text()
            else:
                page.locator(".investment-capacity").wait_for()
            assert not errors, errors
            results.append({"case": name, "page_errors": errors})
            context.close()

        def legacy(plan):
            plan.pop("funding_ledger")
            return plan

        def empty(plan):
            for field in ("funding_ledger", "goal_analysis", "financial_priorities", "allocations", "warnings", "methodology"):
                plan[field] = []
            return plan

        def sparse_metadata(plan):
            plan.pop("warnings")
            plan["methodology"] = None
            for allocation in plan["allocations"]:
                allocation.pop("categories_to_explore")
            return plan

        exercise("old backend missing required ledger", legacy, "funding_ledger")
        exercise("empty financial collections", empty)
        exercise("missing optional display metadata", sparse_metadata)
        browser.close()
    Path("INVESTMENTS_BROWSER_RESULTS.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
