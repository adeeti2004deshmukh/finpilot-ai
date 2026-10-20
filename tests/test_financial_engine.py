from decimal import Decimal

import pytest

from app.financial_engine import (
    FinancialProfile,
    calculate_financial_summary,
    simulate_fd,
    simulate_rd,
    simulate_sip,
)

D = Decimal


@pytest.fixture
def sample_profile() -> FinancialProfile:
    return FinancialProfile(
        monthly_take_home_income=D("95000"),
        monthly_other_income=D("5000"),
        essential_expenses=D("30000"),
        discretionary_expenses=D("15000"),
        debt_payments=D("8000"),
        monthly_savings=D("12000"),
        current_emergency_fund=D("180000"),
    )


def test_income_expenses_savings_rate_and_surplus(sample_profile: FinancialProfile) -> None:
    summary = calculate_financial_summary(sample_profile)
    assert summary.monthly_income == D("100000.00")
    assert summary.monthly_expenses == D("53000.00")
    assert summary.monthly_savings == D("12000.00")
    assert summary.savings_rate_percent == D("12.00")
    assert summary.monthly_surplus == D("47000.00")
    assert summary.investable_surplus == D("35000.00")


def test_emergency_fund_metrics(sample_profile: FinancialProfile) -> None:
    summary = calculate_financial_summary(sample_profile)
    assert summary.emergency_fund_target == D("180000.00")
    assert summary.emergency_fund_gap == D("0.00")
    assert summary.emergency_fund_coverage_percent == D("100.00")


def test_health_score_for_demo_profile_is_deterministic(sample_profile: FinancialProfile) -> None:
    assert calculate_financial_summary(sample_profile).financial_health_score == 87
    assert calculate_financial_summary(sample_profile) == calculate_financial_summary(sample_profile)


def test_zero_income_and_zero_essential_expenses_are_handled() -> None:
    profile = FinancialProfile(D("0"), D("0"), D("0"), D("0"), D("0"), D("0"), D("0"))
    summary = calculate_financial_summary(profile)
    assert summary.savings_rate_percent == D("0.00")
    assert summary.emergency_fund_coverage_percent == D("100.00")
    assert summary.investable_surplus == D("0.00")
    assert summary.financial_health_score == 30


def test_deficit_produces_negative_surplus_and_no_investable_surplus() -> None:
    profile = FinancialProfile(D("40000"), D("0"), D("35000"), D("10000"), D("0"), D("0"), D("0"))
    summary = calculate_financial_summary(profile)
    assert summary.monthly_surplus == D("-5000.00")
    assert summary.investable_surplus == D("0.00")
    assert summary.emergency_fund_gap == D("210000.00")


def test_profile_rejects_negative_money_values() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        FinancialProfile(D("-1"), D("0"), D("0"), D("0"), D("0"), D("0"), D("0"))


def test_sip_zero_rate_and_positive_rate() -> None:
    zero_rate = simulate_sip(D("1000"), D("0"), 12)
    assert zero_rate.invested_amount == D("12000.00")
    assert zero_rate.estimated_interest == D("0.00")
    assert zero_rate.maturity_value == D("12000.00")

    result = simulate_sip(D("10000"), D("12"), 12)
    assert result.invested_amount == D("120000.00")
    assert result.maturity_value == D("126825.03")
    assert result.estimated_interest == D("6825.03")


def test_rd_zero_rate_and_quarterly_compounding() -> None:
    zero_rate = simulate_rd(D("1000"), D("0"), 6)
    assert zero_rate.maturity_value == D("6000.00")

    result = simulate_rd(D("1000"), D("12"), 12)
    assert result.invested_amount == D("12000.00")
    assert result.maturity_value == D("12801.90")
    assert result.estimated_interest == D("801.90")


def test_fd_zero_rate_and_quarterly_compounding() -> None:
    zero_rate = simulate_fd(D("100000"), D("0"), 12)
    assert zero_rate.maturity_value == D("100000.00")

    result = simulate_fd(D("100000"), D("8"), 12)
    assert result.invested_amount == D("100000.00")
    assert result.maturity_value == D("108243.22")
    assert result.estimated_interest == D("8243.22")


@pytest.mark.parametrize("months", [0, 1201, 1.5])
def test_simulations_reject_invalid_tenor(months: int | float) -> None:
    with pytest.raises(ValueError, match="months"):
        simulate_sip(D("1000"), D("8"), months)  # type: ignore[arg-type]


def test_fd_rejects_unsupported_compounding_frequency() -> None:
    with pytest.raises(ValueError, match="compounds_per_year"):
        simulate_fd(D("1000"), D("8"), 12, 3)