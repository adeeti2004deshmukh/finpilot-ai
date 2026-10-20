"""Defense in depth; these checks reduce risk, not a proof of semantic accuracy."""
import json
import re
from decimal import Decimal

REFUSAL = "FinPilot provides educational planning and simulations. I cannot access another person's data, execute financial transactions, recommend individual securities, or guarantee returns. Never share passwords, UPI PINs, CVVs or OTPs."
UNVERIFIED = "I could not verify that explanation against FinPilot's results. Please rephrase your question or open the relevant planning page to review the verified figures."


def unsafe_request(text):
    patterns = [
        r"\b(?:buy|sell|trade|purchase)\b.{0,60}\b(?:stock|shares?|fund|securities)\b.{0,30}\b(?:for me|now)\b",
        r"\b(?:transfer|send|pay)\b.{0,40}(?:₹|\brupees\b|\bmoney\b|\b\d[\d,]*)",
        r"\bguarantee(?:d)?\b.{0,35}\breturns?\b",
        r"\b(?:another|other|all)\s+user(?:s|'s|s')?\b",
        r"\b(?:password|upi\s*pin|cvv|otp|api[_ ]?key|session[_ ]?token)\s*(?:is|:|=)\s*\S+",
        r"\b(?:recommend|pick|choose|buy)\b.{0,35}\b(?:stocks?|mutual funds?|ticker)\b",
    ]
    return any(re.search(pattern, text, re.I) for pattern in patterns)


def numbers(text):
    return {Decimal(match.replace(",", "")) for match in re.findall(r"(?<![\w])\d[\d,]*(?:\.\d+)?", text)}


def safe_answer(answer, results):
    text = " ".join([answer.message, *answer.suggested_followups, *answer.warnings])
    # Numeric statements must appear in actual successful tool outputs, never just the prompt.
    verified = numbers(json.dumps(results, ensure_ascii=False, default=str))
    if not numbers(text).issubset(verified):
        return False
    banned = [r"\b(?:I|we|FinPilot)\s+(?:(?:have|has)\s+)?(?:transferred|paid|purchased|bought|executed|sold)\b",
              r"\b(?:guaranteed|guarantee|definitely|certainly)\b.{0,35}\b(?:return|earn|profit|grow)\b",
              r"\b(?:buy|recommend|invest in|purchase)\b.{0,60}\b(?:stock|shares|mutual fund|ticker|AAPL|TSLA|NVDA)\b",
              r"\b(?:give|share|provide|enter|send)\b.{0,35}\b(?:password|pin|cvv|otp|credentials)\b"]
    return not any(re.search(pattern, text, re.I) for pattern in banned)


def validate_assumptions(name, arguments, user_text):
    """Do not allow a tool call to turn guessed model inputs into verified facts.

    Conservative on purpose: unsupported date phrasing prompts a clarification.
    Identity and record IDs are validated separately by the scoped executor.
    """
    from datetime import date
    from app.services.what_if_service import _date_after_months
    text = user_text.casefold()
    for word, value in {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
                        "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
                        "ten": 10, "twelve": 12}.items():
        text = re.sub(r"\b" + word + r"\b", str(value), text)
    text = re.sub(r"(\d+(?:\.\d+)?)\s*(lakh|lac|crore|k)\b",
                  lambda m: str(Decimal(m[1]) * {"lakh": 100000, "lac": 100000, "crore": 10000000, "k": 1000}[m[2]]), text)
    known = numbers(text)
    durations = [int(m[1]) * (12 if m[2].startswith("year") else 1)
                 for m in re.finditer(r"\b(\d+)\s*(months?|years?)\b", text)]
    known.update(Decimal(n) for n in durations)
    numeric_fields = {"price", "down_payment", "monthly_emi", "tenure_months", "monthly_contribution",
                      "principal", "annual_rate_percent", "months", "amount", "delay_months", "target_amount", "current_amount"}
    for key in numeric_fields.intersection(arguments):
        if arguments[key] is not None and Decimal(str(arguments[key])) not in known:
            # What-if goal delay has an unused zero amount; it is not an assumption.
            if name == "run_what_if_scenario" and key == "amount" and arguments.get("scenario_type") == "GOAL_DELAY" and Decimal(str(arguments[key])) == 0:
                continue
            raise ValueError("Ask the user for missing numeric inputs")
    if name.startswith("simulate_") and "annual_rate_percent" in arguments:
        rates = numbers(" ".join(re.findall(r"\d+(?:\.\d+)?\s*(?:%|percent)", text)))
        if Decimal(str(arguments["annual_rate_percent"])) not in rates:
            raise ValueError("Ask for an explicit assumed percentage rate")
    valid_dates = set(re.findall(r"\d{4}-\d{2}-\d{2}", text))
    if re.search(r"\b(today|now)\b", text):
        valid_dates.add(date.today().isoformat())
    valid_dates.update(_date_after_months(date.today(), n).isoformat() for n in durations if 0 < n <= 1200)
    for key in ("purchase_date", "target_date"):
        if key in arguments and arguments[key] not in valid_dates:
            raise ValueError("Ask for an explicit date or relative month/year duration")
    if name == "analyze_affordability":
        method = arguments.get("payment_method")
        if method == "CASH" and not re.search(r"\b(cash|outright)\b", text):
            raise ValueError("Ask for payment method")
        if method == "EMI" and not re.search(r"\b(emi|instalments?|installments?)\b", text):
            raise ValueError("Ask for payment method")
