from dataclasses import asdict

from fastapi import APIRouter

from app.calculations.compound_growth import simulate_compound_growth
from app.financial_engine import simulate_fd, simulate_rd, simulate_sip
from app.schemas.simulations import (
    CompoundGrowthRequest,
    ContributionSimulationRequest,
    FixedDepositSimulationRequest,
    SimulationResponse,
)

router = APIRouter(prefix="/api/simulate", tags=["Simulations"])
MARKET_SCENARIO_DISCLAIMER = (
    "Illustrative scenario. Actual market returns may be higher or lower and are not guaranteed."
)


@router.post("/sip", response_model=SimulationResponse, summary="Run an illustrative SIP projection")
def sip_projection(payload: ContributionSimulationRequest) -> SimulationResponse:
    result = simulate_sip(payload.monthly_contribution, payload.annual_rate_percent, payload.months)
    return SimulationResponse(**asdict(result), disclaimer=MARKET_SCENARIO_DISCLAIMER)


@router.post("/rd", response_model=SimulationResponse, summary="Run a recurring deposit projection")
def rd_projection(payload: ContributionSimulationRequest) -> SimulationResponse:
    result = simulate_rd(payload.monthly_contribution, payload.annual_rate_percent, payload.months)
    return SimulationResponse(**asdict(result))


@router.post("/fd", response_model=SimulationResponse, summary="Run a fixed deposit projection")
def fd_projection(payload: FixedDepositSimulationRequest) -> SimulationResponse:
    result = simulate_fd(
        payload.principal,
        payload.annual_rate_percent,
        payload.months,
        payload.compounds_per_year,
    )
    return SimulationResponse(**asdict(result))


@router.post("/compound-growth", response_model=SimulationResponse, summary="Run an illustrative compound-growth scenario")
def compound_growth(payload: CompoundGrowthRequest) -> SimulationResponse:
    result = simulate_compound_growth(payload.principal, payload.annual_rate_percent, payload.months)
    return SimulationResponse(**result, disclaimer=MARKET_SCENARIO_DISCLAIMER)