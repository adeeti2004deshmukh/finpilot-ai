from decimal import Decimal, ROUND_HALF_UP


def simulate_compound_growth(principal: Decimal, annual_rate_percent: Decimal, months: int) -> dict[str, Decimal]:
    monthly_rate = annual_rate_percent / Decimal("100") / Decimal("12")
    maturity = principal * (Decimal("1") + monthly_rate) ** months
    invested = principal
    return {
        "invested_amount": invested.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "estimated_interest": (maturity - invested).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "maturity_value": maturity.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
    }