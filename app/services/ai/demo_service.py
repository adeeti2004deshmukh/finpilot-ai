"""Local intent routing and result templates. No model, network or financial engine."""
import logging
import re
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from pydantic import ValidationError

from app.services.ai.schemas import ChatResponse
from app.services.ai.tool_executor import ToolExecutor
from app.services.what_if_service import _date_after_months

logger = logging.getLogger(__name__)
EDUCATION = "Demo AI Coach uses deterministic FinPilot tools, not OpenAI. Educational guidance only; returns are not guaranteed and no transactions are executed."
NUMBER = r"\d[\d,]*(?:\.\d+)?(?:\s*(?:lakh|lac|crore|k)\b)?"


def amount(value):
    match = re.fullmatch(r"([\d,.]+)\s*(lakh|lac|crore|k)?", value.strip(), re.I)
    return str(Decimal(match[1].replace(",", "")) * {None: 1, "lakh": 100000, "lac": 100000, "crore": 10000000, "k": 1000}[match[2].lower() if match[2] else None])


def money(value):
    return f"₹{Decimal(str(value)):,.2f}"


def normal(text):
    text = text.casefold()
    for word, value in {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "twelve": 12}.items():
        text = re.sub(r"\b" + word + r"\b", str(value), text)
    return text


def duration(text):
    match = re.search(r"\b(\d+)\s*(months?|years?)\b", text)
    return int(match[1]) * (12 if match[2].startswith("year") else 1) if match else None


def demo_chat(db, user_id, request, cid, conversation):
    executor = ToolExecutor(db, user_id, conversation.purchase)
    used, warnings = [], [EDUCATION]
    def tool(name, **args):
        result = executor.execute(name, args)
        used.append(name)
        return result
    text = normal(request.message)
    pending = dict(conversation.demo_pending)
    kind = None
    # Explicit new topics replace pending input collection. Otherwise continue it.
    if re.search(r"\b(afford|purchase|buy)\b", text): kind = "purchase"
    elif re.search(r"\bsip\b", text): kind = "sip"
    elif re.search(r"\brd\b", text): kind = "rd"
    elif re.search(r"\bfd\b", text): kind = "fd"
    elif "what if" in text or "what-if" in text: kind = "whatif"
    elif re.search(r"overspend|spending|budget|money go", text): kind = "spending"
    elif re.search(r"health|score", text): kind = "health"
    elif re.search(r"prioriti|monthly plan|extra.*month", text): kind = "priorities"
    elif "emergency" in text: kind = "emergency"
    elif re.search(r"invest|allocation|categor", text): kind = "investment"
    elif re.search(r"goal|wedding", text): kind = "goals"
    elif re.search(r"summary|income|expenses|savings|surplus", text): kind = "summary"
    if kind and kind != pending.get("kind"):
        pending = {"kind": kind, "text": ""}
    kind = kind or pending.get("kind")
    combined = (pending.get("text", "") + " " + text).strip()[-4000:]
    keep_pending = False
    try:
        if kind == "spending":
            spending, budgets = tool("get_spending_analysis"), tool("get_budget_status")
            lines = [f"Your recorded spending this month is {money(spending['monthly_spending'])}."]
            lines += [f"{row['category']}: {money(row['amount'])}." for row in spending["top_categories"][:5]]
            over = [row for row in budgets["budgets"] if row["status"] == "OVER_BUDGET"]
            lines += [f"Over budget — {row['category']}: spent {money(row['amount_spent'])} against {money(row['monthly_limit'])}." for row in over[:5]]
            if not over: lines.append("No recorded current-month budgets are over their limits." if budgets["budgets"] else "No current-month budgets are set; large categories alone do not establish overspending.")
            if not spending["top_categories"]: lines.append("No category spending is recorded for this month.")
            lines.append(spending["coverage_note"])
        elif kind == "health":
            result = tool("get_financial_health")
            lines = [f"Your financial health score is {result['score']} out of {result['maximum_score']}."]
            lines += [f"{c['name']}: {c['points']}/{c['maximum_points']}. {c['reason']}" for c in result["components"]]
            lines += result["deterministic_actions"][:3]
        elif kind == "priorities":
            priorities, plan = tool("get_financial_priorities"), tool("get_monthly_plan")
            lines = [f"Your monthly plan has a surplus of {money(plan['monthly_surplus'])} and a safety buffer of {money(plan['safety_buffer'])}."]
            lines += [f"{p['priority_level']}: {p['action']} {p['reason']}" for p in priorities[:5]]
            lines += [f"{row['purpose']}: {money(row['amount'])}." for row in plan["allocations"][:6]]
            warnings += plan["warnings"][:3]
        elif kind == "emergency":
            result = tool("get_emergency_fund_status")
            lines = [f"Your emergency fund is {money(result['current_amount'])}, against a target of {money(result['target_amount'])}.",
                     f"It covers {result['months_covered']} months. The remaining gap is {money(result['remaining_amount'])}."]
            lines += [p["action"] for p in result["priorities"] if "emergency" in (p["purpose"] + p["reason"]).casefold()][:2]
        elif kind in {"goals", "investment"}:
            goals = tool("get_goals")
            # Only select saved goals from this user's scoped result, never a supplied owner ID.
            selected = next((g for g in goals["analysis"] if g["name"].casefold() in text), None)
            goal_id = re.search(r"\bgoal\s*(?:id\s*|#)(\d+)", text)
            if goal_id:
                selected = next((g for g in goals["analysis"] if g["goal_id"] == int(goal_id[1])), None)
                if selected is None:
                    return ChatResponse(provider="demo", message="That goal is unavailable in your account. Ask about one of your saved goals.", conversation_id=cid, tools_used=used, warnings=warnings)
            if kind == "goals":
                rows = [tool("analyze_goal", goal_id=selected["goal_id"])] if selected else goals["analysis"]
                lines = [f"{g['name']}: target {money(g['target_amount'])}, current {money(g['current_amount'])}; " +
                         ("set a deadline before calculating a monthly contribution" if g['remaining_months'] is None else
                          f"{g['remaining_months']} months remaining, required monthly contribution {money(g['required_monthly_contribution'])}") +
                         f"; {g['funding_status']}." for g in rows[:8]]
                if not lines: lines = ["You have no saved goals. Add a goal and deadline in Goals to calculate its required contribution."]
            else:
                plan = tool("get_investment_plan")
                lines = [f"Your monthly surplus is {money(plan['monthly_surplus'])}; recorded savings are {money(plan['actual_monthly_savings'])}; investable surplus after the plan is {money(plan['investable_surplus'])}."]
                lines += [f"{a['purpose']}: {money(a['amount'])}. Categories to explore: {', '.join(c['name'] for c in a['categories_to_explore'])}." for a in plan["allocations"][:6]]
                if selected:
                    comparison = tool("compare_investment_categories", goal_id=selected["goal_id"])
                    lines += [f"{c['name']}: {c['relevance_reason']}" for c in comparison["categories_to_explore"][:5]]
                lines.append("SIP is a method, not an asset class. Risk depends on the underlying investment. Consider professional advice for major decisions.")
                warnings += plan["warnings"][:3]
        elif kind == "purchase":
            args = dict(pending.get("args", {}))
            price = re.search(r"(?:₹|rs\.?\s*|inr\s*|price\s*(?:is\s*)?)\s*(" + NUMBER + r")", text) if "price" not in args or "price" in text else None
            if not price:
                price = re.search(r"\b(" + NUMBER + r")\s+(?:phone|laptop|car|purchase)\b", text)
            if price: args["price"] = amount(price[1])
            item = re.search(r"\b(phone|laptop|car|bike|television|tv)\b", combined)
            args["item_name"] = item[1] if item else "Purchase"
            iso = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", text)
            if iso: args["purchase_date"] = iso[-1]
            elif re.search(r"\b(today|now)\b", text): args["purchase_date"] = date.today().isoformat()
            else:
                when = re.search(r"\b(?:in|after|wait)\s+(\d+)\s*(months?|years?)\b", text)
                if when:
                    months = int(when[1]) * (12 if when[2].startswith("year") else 1)
                    if 1 <= months <= 1200: args["purchase_date"] = _date_after_months(date.today(), months).isoformat()
            if re.search(r"\b(cash|outright)\b", text): args["payment_method"] = "CASH"
            elif re.search(r"\bemi\b", text): args["payment_method"] = "EMI"
            for key, label in (("down_payment", "down payment"), ("monthly_emi", "monthly emi")):
                match = re.search(label + r"\s*(?:of|is|=|:)?\s*(?:₹|rs\.?|inr)?\s*(" + NUMBER + r")", combined)
                if match: args[key] = amount(match[1])
            tenure = re.search(r"tenure\s*(?:of|is|=|:)?\s*(\d+)\s*months?", combined)
            if tenure: args["tenure_months"] = int(tenure[1])
            required = ["price", "purchase_date", "payment_method"]
            if args.get("payment_method") == "EMI": required += ["down_payment", "monthly_emi", "tenure_months"]
            missing = [key.replace("_", " ") for key in required if key not in args]
            if missing:
                lines = ["To analyze this purchase, please provide: " + ", ".join(missing) + ". Use an ISO date or 'today', and specify CASH or EMI."]
                keep_pending = True
                pending["args"] = args
            else:
                if args["payment_method"] == "CASH":
                    args = {key: value for key, value in args.items() if key not in {"down_payment", "monthly_emi", "tenure_months"}}
                result = tool("analyze_affordability", **args)["analysis"]
                lines = purchase_lines(result)
                warnings += result["warnings"][:3]
        elif kind in {"sip", "rd", "fd"}:
            rate = re.search(r"(\d+(?:\.\d+)?)\s*(?:%|percent)", combined)
            principal = re.search(r"(?:₹|rs\.?\s*|inr\s*)\s*(" + NUMBER + r")", combined)
            if not principal:
                principal = re.search(r"\b(?:contribution|principal|deposit|amount)\s*(?:of|is|:|=)?\s*(" + NUMBER + r")", combined)
            months = duration(combined)
            if not (rate and principal and months):
                missing = [label for label, present in (("amount (with ₹ or 'amount')", principal), ("duration in months/years", months), ("assumed annual rate (%)", rate)) if not present]
                lines = ["For this illustration, provide " + ", ".join(missing) + ". I will not assume returns."]
                keep_pending = True
            else:
                args = {"annual_rate_percent": rate[1], "months": months, "principal" if kind == "fd" else "monthly_contribution": amount(principal[1])}
                if kind == "fd":
                    comp = re.search(r"\b(annually|semiannually|quarterly|monthly)\s+compound", combined)
                    args["compounds_per_year"] = {"annually": 1, "semiannually": 2, "quarterly": 4, "monthly": 12}[comp[1]] if comp else 4
                result = tool("simulate_" + kind, **args)
                lines = [f"{kind.upper()} illustration at your assumed annual rate of {result['assumptions']['annual_rate_percent']}% for {result['assumptions']['months']} months:",
                         f"Invested amount: {money(result['invested_amount'])}. Estimated interest: {money(result['estimated_interest'])}. Maturity value: {money(result['maturity_value'])}.", result["warning"]]
                if kind == "fd": lines.append(f"Compounding periods per year: {result['assumptions']['compounds_per_year']} (quarterly is the existing simulator default).")
        elif kind == "whatif":
            if re.search(r"wait|delay", combined) and conversation.purchase and duration(combined):
                result = tool("delay_purchase", delay_months=duration(combined))["analysis"]
                lines = purchase_lines(result)
                warnings += result["warnings"][:3]
            else:
                scenario = None
                for pattern, value in ((r"income.*(?:increas|rise|rises|up|extra)", "INCOME_INCREASE"), (r"rent.*(?:increas|rise|rises|up)", "RENT_INCREASE"),
                                       (r"(?:food|spending).*(?:reduc|cut|less)", "FOOD_SPENDING_REDUCTION"), (r"savings?.*(?:increas|rise|up|more)", "SAVINGS_INCREASE")):
                    if re.search(pattern, combined): scenario = value; break
                change = re.search(r"(?:by\s*|₹|rs\.?\s*|inr\s*)(" + NUMBER + r")", combined)
                if not scenario or not change:
                    lines = ["Local demo supports income increases, rent increases, food spending reductions and savings increases. Specify the change, for example: 'What if my monthly income increases by ₹5,000?' For purchase waiting, first analyze a purchase."]
                    keep_pending = True
                else:
                    result = tool("run_what_if_scenario", scenario_type=scenario, amount=amount(change[1]))
                    lines = [f"{key.replace('_', ' ').capitalize()}: current {money(result['current'][key])}; projected {money(result['projected'][key])}." for key in ("monthly_income", "monthly_expenses", "actual_monthly_savings", "monthly_surplus", "investable_surplus")]
                    warnings += result["warnings"][:3]
        elif kind == "summary":
            result = tool("get_financial_summary")
            lines = [f"Monthly income: {money(result['monthly_income'])}. Expenses: {money(result['monthly_expenses'])}.",
                     f"Recorded savings: {money(result['monthly_savings'])}. Savings rate: {result['savings_rate']}%.",
                     f"Monthly surplus: {money(result['monthly_surplus'])}. Investable surplus: {money(result['investable_surplus'])}."]
        else:
            lines = ["Local demo recognizes spending, health, priorities, emergency fund, saved goals, investment allocation, purchase affordability, SIP/RD/FD illustrations and simple What-If changes. Try one of the suggested questions. It cannot interpret every free-form question."]
        conversation.demo_pending = {**pending, "kind": kind, "text": combined} if keep_pending else {}
        conversation.purchase = executor.purchase
        return ChatResponse(provider="demo", message="Based on your current FinPilot data:\n\n" + "\n".join(lines) if used else "\n".join(lines),
                            conversation_id=cid, tools_used=used, warnings=warnings[:5],
                            suggested_followups=["Where am I overspending?", "What should I prioritize this month?"])
    except (ValueError, ValidationError, HTTPException, ArithmeticError):
        conversation.demo_pending = {}
        return ChatResponse(provider="demo", conversation_id=cid, tools_used=used, warnings=warnings,
                            message="That analysis is unavailable or its inputs are invalid. Please check amounts, dates and payment details, or complete your financial profile. No financial records were changed.")
    except Exception as exc:
        logger.warning("Demo coach failed (%s)", type(exc).__name__)
        raise HTTPException(503, "Local demo analysis is temporarily unavailable. Other FinPilot features remain available.") from None


def purchase_lines(result):
    return [f"{result['item_name']}: {money(result['price'])}; status {result['affordability_status']}, score {result['affordability_score']}.",
            f"Cash-flow impact: {money(result['cash_flow_impact'])}. Monthly surplus after purchase: {money(result['monthly_surplus_after'])}.",
            f"Emergency fund before: {money(result['emergency_fund_before'])}; after: {money(result['emergency_fund_after'])}.",
            f"Goal impact: {money(result['goal_impact'])}.",
            *[f"Alternative — {s['name']}: date {s['purchase_date']}, required monthly saving {money(s['required_monthly_saving'])}; {s['status']}." for s in result['alternative_scenarios'][:3]],
            "Consider professional advice for major financial decisions."]
