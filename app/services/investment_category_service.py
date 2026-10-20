from decimal import Decimal

from app.models.enums import RiskTolerance
from app.schemas.planning import GoalAnalysisResponse, InvestmentCategoryGuidance

_CATEGORY_DATA = [
    {
        "name": "Savings Account",
        "description": "A deposit account for liquid reserves and day-to-day access.",
        "risk_level": "LOW",
        "liquidity": "HIGH",
        "typical_time_horizon": "Immediate to 1 year",
        "return_type": "Deposit rate set by provider; variable terms may apply",
        "market_linked": False,
        "capital_guarantee_explanation": "Not market-linked, but protection depends on institution, account eligibility, and applicable deposit-insurance rules.",
        "best_used_for": "Emergency reserves and near-term cash needs",
        "advantages": ["High access to funds", "Simple to understand"],
        "limitations": ["Rates and terms vary", "Purchasing power may be affected by inflation"],
        "risk_rank": 1,
        "horizon_scores": [96, 78, 54, 34],
    },
    {
        "name": "Recurring Deposit (RD)",
        "description": "A scheduled periodic deposit with institution-specific rate and withdrawal terms.",
        "risk_level": "LOW",
        "liquidity": "MEDIUM",
        "typical_time_horizon": "6 months to 3 years",
        "return_type": "Stated deposit rate subject to product terms",
        "market_linked": False,
        "capital_guarantee_explanation": "Not market-linked; principal protection depends on the provider and applicable deposit-protection rules.",
        "best_used_for": "Disciplined saving toward a dated near-term goal",
        "advantages": ["Regular deposit schedule", "Stated terms"],
        "limitations": ["Early closure may have conditions or penalties", "Inflation can reduce real returns"],
        "risk_rank": 1,
        "horizon_scores": [91, 89, 67, 47],
    },
    {
        "name": "Fixed Deposit (FD)",
        "description": "A lump-sum deposit held for a selected term under provider-specific conditions.",
        "risk_level": "LOW",
        "liquidity": "LOW_TO_MEDIUM",
        "typical_time_horizon": "3 months to 5 years",
        "return_type": "Stated deposit rate subject to product terms",
        "market_linked": False,
        "capital_guarantee_explanation": "Not market-linked; repayment depends on the institution and applicable deposit-protection rules and limits.",
        "best_used_for": "A known lump sum with a date-aligned deposit term",
        "advantages": ["Defined term and stated rate", "Can match a known date"],
        "limitations": ["Early withdrawal terms apply", "Rates can lag inflation"],
        "risk_rank": 1,
        "horizon_scores": [84, 86, 74, 56],
    },
    {
        "name": "Mutual Fund SIP",
        "description": "SIP is a method of investing a fixed amount periodically, commonly used with mutual funds. Risk depends on the underlying investment.",
        "risk_level": "VARIES_BY_UNDERLYING_ASSET",
        "liquidity": "VARIES_BY_SCHEME",
        "typical_time_horizon": "Depends on underlying assets; often 3+ years for market exposure",
        "return_type": "Market-linked when underlying assets are market-linked",
        "market_linked": True,
        "capital_guarantee_explanation": "No return or capital guarantee from the SIP method; market value can fall, based on underlying holdings.",
        "best_used_for": "A regular contribution approach when the underlying risk and horizon are understood",
        "advantages": ["Automates periodic contributions", "Can spread purchase timing"],
        "limitations": ["SIP does not reduce underlying market risk", "Returns are not guaranteed"],
        "risk_rank": 3,
        "horizon_scores": [28, 52, 74, 85],
    },
    {
        "name": "Index-oriented SIP category",
        "description": "A periodic contribution method into an index-tracking market-linked category; exposure follows the chosen index and fund structure.",
        "risk_level": "HIGH",
        "liquidity": "MARKET_LIQUIDITY_AND_SCHEME_TERMS",
        "typical_time_horizon": "Usually considered for 5+ year goals",
        "return_type": "Market-linked; tracks an index with tracking differences",
        "market_linked": True,
        "capital_guarantee_explanation": "No capital or return guarantee; market drawdowns and tracking differences are possible.",
        "best_used_for": "Longer-horizon goals where market volatility can be tolerated",
        "advantages": ["Rules-based exposure", "Can provide broad market exposure depending on index"],
        "limitations": ["Market losses are possible", "Index concentration and tracking risks vary"],
        "risk_rank": 3,
        "horizon_scores": [18, 42, 68, 91],
    },
    {
        "name": "Debt-oriented category",
        "description": "A broad category of instruments with interest-rate, credit, and duration risks that vary by underlying holdings.",
        "risk_level": "LOW_TO_MODERATE; VARIES_BY_HOLDINGS",
        "liquidity": "VARIES_BY_INSTRUMENT",
        "typical_time_horizon": "Varies; align duration and liquidity to the goal",
        "return_type": "Interest or market value changes; not necessarily fixed",
        "market_linked": True,
        "capital_guarantee_explanation": "Debt-oriented does not mean capital-guaranteed; credit and interest-rate risks remain.",
        "best_used_for": "A goal where the underlying duration and credit risk are understood",
        "advantages": ["May diversify a portfolio", "Multiple duration profiles exist"],
        "limitations": ["Credit and interest-rate losses are possible", "Liquidity depends on instrument"],
        "risk_rank": 2,
        "horizon_scores": [60, 72, 79, 70],
    },
    {
        "name": "Gold category",
        "description": "Gold exposure can be held through different structures, each with price, liquidity, and product-specific risks.",
        "risk_level": "MODERATE_TO_HIGH",
        "liquidity": "VARIES_BY_FORM",
        "typical_time_horizon": "Medium to long term; prices can be volatile",
        "return_type": "Market-linked to gold prices and structure-specific costs",
        "market_linked": True,
        "capital_guarantee_explanation": "No general capital guarantee; price and structure risks apply.",
        "best_used_for": "Learning about diversification exposure, not as a guaranteed return source",
        "advantages": ["Different exposure formats exist", "Can behave differently from other assets"],
        "limitations": ["Price can be volatile", "Costs, spreads, and liquidity vary by form"],
        "risk_rank": 2,
        "horizon_scores": [36, 53, 67, 65],
    },
    {
        "name": "Retirement-oriented category",
        "description": "A broad label for long-horizon retirement savings structures with scheme-specific investment and withdrawal rules.",
        "risk_level": "VARIES_BY_ALLOCATION",
        "liquidity": "LOW_TO_MEDIUM; RULES_APPLY",
        "typical_time_horizon": "Long term",
        "return_type": "Varies by allocation and scheme",
        "market_linked": True,
        "capital_guarantee_explanation": "Guarantees, if any, depend on the specific legally defined scheme; this category label makes no guarantee claim.",
        "best_used_for": "Long-horizon retirement planning and learning about scheme rules",
        "advantages": ["Designed around long-term objectives", "Some structures have defined contribution rules"],
        "limitations": ["Withdrawal and tax rules vary", "Underlying allocation risk remains"],
        "risk_rank": 2,
        "horizon_scores": [12, 30, 58, 88],
    },
]

_HORIZON_INDEX = {
    "VERY_SHORT_TERM": 0,
    "SHORT_TERM": 1,
    "MEDIUM_TERM": 2,
    "LONG_TERM": 3,
    "UNSPECIFIED": 2,
}


def list_investment_categories() -> list[InvestmentCategoryGuidance]:
    return [InvestmentCategoryGuidance(**{key: value for key, value in data.items() if key not in {"risk_rank", "horizon_scores"}}) for data in _CATEGORY_DATA]


def _relevance_reason(category: dict, goal: GoalAnalysisResponse, emergency_coverage: Decimal, risk_tolerance: RiskTolerance) -> str:
    if goal.goal_horizon in ("VERY_SHORT_TERM", "SHORT_TERM"):
        if category["name"] in ("Savings Account", "Recurring Deposit (RD)", "Fixed Deposit (FD)"):
            return "Shorter goal timelines generally place more weight on access, date alignment, and limiting market volatility."
        return "Market-linked values can fluctuate near a short goal date, so the fit is lower for this horizon."
    if emergency_coverage < Decimal("50") and category["market_linked"]:
        return "The emergency reserve is below half of target; strengthening liquidity takes precedence in this relevance comparison."
    if risk_tolerance == RiskTolerance.LOW and category["risk_rank"] >= 3:
        return "This category's underlying market risk may exceed the selected low risk tolerance."
    if goal.goal_horizon == "LONG_TERM" and category["market_linked"]:
        return "The longer horizon may provide more time to manage market volatility, but returns remain uncertain."
    return "This category's general horizon and liquidity characteristics are a partial match; suitability depends on product terms and personal circumstances."


def score_category_relevance(
    goal: GoalAnalysisResponse,
    risk_tolerance: RiskTolerance,
    emergency_coverage_percent: Decimal,
) -> list[InvestmentCategoryGuidance]:
    horizon_index = _HORIZON_INDEX[goal.goal_horizon]
    result: list[InvestmentCategoryGuidance] = []
    for data in _CATEGORY_DATA:
        score = data["horizon_scores"][horizon_index]
        if risk_tolerance == RiskTolerance.LOW:
            score += 5 if data["risk_rank"] == 1 else -18 if data["risk_rank"] == 3 else -6
        elif risk_tolerance == RiskTolerance.HIGH:
            score += 5 if data["risk_rank"] == 3 else -3 if data["risk_rank"] == 1 else 0
        if emergency_coverage_percent < Decimal("50"):
            score += 10 if data["risk_rank"] == 1 else -18 if data["market_linked"] else 0
        if goal.goal_type == "EMERGENCY_FUND":
            score += 16 if data["name"] == "Savings Account" else 10 if data["name"] in ("Recurring Deposit (RD)", "Fixed Deposit (FD)") else -20
        score = max(0, min(100, score))
        level = "HIGH RELEVANCE" if score >= 80 else "MEDIUM RELEVANCE" if score >= 60 else "LOW RELEVANCE"
        payload = {key: value for key, value in data.items() if key not in {"risk_rank", "horizon_scores"}}
        payload.update(
            relevance_score=score,
            relevance_level=level,
            relevance_reason=_relevance_reason(data, goal, emergency_coverage_percent, risk_tolerance),
        )
        result.append(InvestmentCategoryGuidance(**payload))
    return sorted(result, key=lambda item: item.relevance_score or 0, reverse=True)


def category_guidance_by_name(name: str) -> InvestmentCategoryGuidance:
    for category in list_investment_categories():
        if category.name == name:
            return category
    raise ValueError(f"Unknown educational investment category: {name}")