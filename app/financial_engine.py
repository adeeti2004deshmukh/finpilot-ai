"""Deterministic financial calculations using Decimal arithmetic."""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")
ZERO = Decimal("0")
ONE_HUNDRED = Decimal("100")
MAX_MONTHS = 1200


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _validate_nonnegative(name: str, value: Decimal) -> None:
    if not value.is_finite() or value < ZERO:
        raise ValueError(f"{name} must be a finite, non-negative amount")


def _validate_months(months: int) -> None:
    if isinstance(months, bool) or not isinstance(months, int) or not 1 <= months <= MAX_MONTHS:
        raise ValueError(f"months must be an integer between 1 and {MAX_MONTHS}")


@dataclass(frozen=True)
class FinancialProfile:
    monthly_take_home_income: Decimal
    monthly_other_income: Decimal
    essential_expenses: Decimal
    discretionary_expenses: Decimal
    debt_payments: Decimal
    monthly_savings: Decimal
    current_emergency_fund: Decimal
    emergency_fund_target_months: int = 6
    emergency_expense_baseline: Decimal | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "monthly_take_home_income",
            "monthly_other_income",
            "essential_expenses",
            "discretionary_expenses",
            "debt_payments",
            "monthly_savings",
            "current_emergency_fund",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, Decimal):
                raise TypeError(f"{field_name} must be a Decimal")
            _validate_nonnegative(field_name, value)
        if self.emergency_expense_baseline is not None:
            _validate_nonnegative("emergency_expense_baseline", self.emergency_expense_baseline)
        _validate_months(self.emergency_fund_target_months)


@dataclass(frozen=True)
class FinancialSummary:
    monthly_income: Decimal
    monthly_expenses: Decimal
    monthly_savings: Decimal
    savings_rate_percent: Decimal
    monthly_surplus: Decimal
    emergency_fund_target: Decimal
    emergency_fund_gap: Decimal
    emergency_fund_coverage_percent: Decimal
    financial_health_score: int
    investable_surplus: Decimal


@dataclass(frozen=True)
class FinancialHealthBreakdown:
    score: int
    savings_points: int
    emergency_fund_points: int
    expense_discipline_points: int
    debt_points: int


@dataclass(frozen=True)
class SimulationResult:
    invested_amount: Decimal
    estimated_interest: Decimal
    maturity_value: Decimal


def calculate_financial_summary(profile: FinancialProfile) -> FinancialSummary:
    """Calculate monthly totals, savings metrics, emergency fund, and a 0-100 score.

    Monthly surplus is income minus expenses, before monthly savings commitments.
    Investable surplus is the positive remainder after those commitments.
    """
    monthly_income = profile.monthly_take_home_income + profile.monthly_other_income
    monthly_expenses = (
        profile.essential_expenses + profile.discretionary_expenses + profile.debt_payments
    )
    monthly_surplus = monthly_income - monthly_expenses
    savings_rate = (
        profile.monthly_savings / monthly_income * ONE_HUNDRED
        if monthly_income > ZERO
        else ZERO
    )
    emergency_target = (profile.emergency_expense_baseline if profile.emergency_expense_baseline is not None else profile.essential_expenses) * profile.emergency_fund_target_months
    if emergency_target > ZERO:
        emergency_coverage = min(profile.current_emergency_fund / emergency_target, Decimal("1"))
    else:
        emergency_coverage = Decimal("1")
    emergency_gap = max(ZERO, emergency_target - profile.current_emergency_fund)

    health_score = calculate_financial_health_breakdown(profile).score

    return FinancialSummary(
        monthly_income=_money(monthly_income),
        monthly_expenses=_money(monthly_expenses),
        monthly_savings=_money(profile.monthly_savings),
        savings_rate_percent=_money(savings_rate),
        monthly_surplus=_money(monthly_surplus),
        emergency_fund_target=_money(emergency_target),
        emergency_fund_gap=_money(emergency_gap),
        emergency_fund_coverage_percent=_money(emergency_coverage * ONE_HUNDRED),
        financial_health_score=max(0, min(100, health_score)),
        investable_surplus=_money(max(ZERO, monthly_surplus - profile.monthly_savings)),
    )


def calculate_financial_health_breakdown(profile: FinancialProfile) -> FinancialHealthBreakdown:
    """Expose the existing 30/30/20/20 score formula as whole-point factors.

    Expense discipline is based on the expense-to-income ratio; goal progress is
    reported separately because goals are not inputs to the Phase 1 score.
    """
    monthly_income = profile.monthly_take_home_income + profile.monthly_other_income
    monthly_expenses = profile.essential_expenses + profile.discretionary_expenses + profile.debt_payments
    monthly_savings = profile.monthly_savings
    savings_rate = monthly_savings / monthly_income * ONE_HUNDRED if monthly_income > ZERO else ZERO
    target = (profile.emergency_expense_baseline if profile.emergency_expense_baseline is not None else profile.essential_expenses) * profile.emergency_fund_target_months
    emergency_coverage = min(profile.current_emergency_fund / target, Decimal("1")) if target > ZERO else Decimal("1")
    expense_ratio = monthly_expenses / monthly_income if monthly_income > ZERO else Decimal("1")
    debt_ratio = profile.debt_payments / monthly_income if monthly_income > ZERO else Decimal("1")

    raw_points = [
        min(savings_rate / Decimal("20"), Decimal("1")) * Decimal("30"),
        emergency_coverage * Decimal("30"),
        max(ZERO, min(Decimal("1"), (Decimal("0.9") - expense_ratio) / Decimal("0.4"))) * Decimal("20"),
        max(ZERO, min(Decimal("1"), (Decimal("0.4") - debt_ratio) / Decimal("0.3"))) * Decimal("20"),
    ]
    score = int(sum(raw_points, ZERO).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    rounded = [int(points.quantize(Decimal("1"), rounding=ROUND_HALF_UP)) for points in raw_points]
    remainder = score - sum(rounded)
    if remainder:
        fractional = [points - Decimal(value) for points, value in zip(raw_points, rounded)]
        adjust_index = max(range(len(fractional)), key=fractional.__getitem__) if remainder > 0 else min(range(len(fractional)), key=fractional.__getitem__)
        rounded[adjust_index] += remainder
    return FinancialHealthBreakdown(
        score=max(0, min(100, score)),
        savings_points=rounded[0],
        emergency_fund_points=rounded[1],
        expense_discipline_points=rounded[2],
        debt_points=rounded[3],
    )


def _validate_simulation_inputs(monthly_amount: Decimal, annual_rate_percent: Decimal, months: int) -> None:
    _validate_nonnegative("monthly_amount", monthly_amount)
    _validate_nonnegative("annual_rate_percent", annual_rate_percent)
    _validate_months(months)


def simulate_sip(monthly_contribution: Decimal, annual_rate_percent: Decimal, months: int) -> SimulationResult:
    """Project month-end SIP contributions with nominal annual rate compounded monthly."""
    _validate_simulation_inputs(monthly_contribution, annual_rate_percent, months)
    monthly_rate = annual_rate_percent / ONE_HUNDRED / Decimal("12")
    if monthly_rate == ZERO:
        maturity_value = monthly_contribution * months
    else:
        maturity_value = monthly_contribution * (
            ((Decimal("1") + monthly_rate) ** months - 1) / monthly_rate
        )
    invested = monthly_contribution * months
    return SimulationResult(_money(invested), _money(maturity_value - invested), _money(maturity_value))


def simulate_rd(monthly_deposit: Decimal, annual_rate_percent: Decimal, months: int) -> SimulationResult:
    """Project beginning-of-month RD deposits with interest credited quarterly."""
    _validate_simulation_inputs(monthly_deposit, annual_rate_percent, months)
    quarterly_rate = annual_rate_percent / ONE_HUNDRED / Decimal("4")
    monthly_rate = annual_rate_percent / ONE_HUNDRED / Decimal("12")
    balance = ZERO
    accrued_interest = ZERO
    for month in range(1, months + 1):
        balance += monthly_deposit
        accrued_interest += balance * monthly_rate
        if month % 3 == 0:
            balance += accrued_interest
            accrued_interest = ZERO
    invested = monthly_deposit * months
    return SimulationResult(_money(invested), _money(balance - invested), _money(balance))


def simulate_fd(
    principal: Decimal,
    annual_rate_percent: Decimal,
    months: int,
    compounds_per_year: int = 4,
) -> SimulationResult:
    """Project an FD with periodic compounding and simple interest for leftover months."""
    _validate_nonnegative("principal", principal)
    _validate_nonnegative("annual_rate_percent", annual_rate_percent)
    _validate_months(months)
    if compounds_per_year not in (1, 2, 4, 12):
        raise ValueError("compounds_per_year must be one of 1, 2, 4, or 12")
    period_months = 12 // compounds_per_year
    full_periods, remaining_months = divmod(months, period_months)
    periodic_rate = annual_rate_percent / ONE_HUNDRED / compounds_per_year
    maturity_value = principal * (Decimal("1") + periodic_rate) ** full_periods
    if remaining_months:
        maturity_value *= Decimal("1") + annual_rate_percent / ONE_HUNDRED * remaining_months / 12
    return SimulationResult(_money(principal), _money(maturity_value - principal), _money(maturity_value))